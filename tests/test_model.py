import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fixtures import Fixture, SportMonksFixtureSource, normalize_sportmonks_fixtures, save_cache
from model import PremierLeagueModel


class FixtureNormalizationTests(unittest.TestCase):
    def test_sportmonks_source_accepts_league_and_season(self):
        source = SportMonksFixtureSource(api_key="test", season_id=27965, league_id=564)
        self.assertEqual(source.season_id, 27965)
        self.assertEqual(source.league_id, 564)

    def test_empty_sportmonks_response_raises_instead_of_returning_nothing(self):
        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {"message": "No result(s) found", "data": []}

        with patch("requests.get", return_value=Response()):
            with self.assertRaisesRegex(RuntimeError, "No result"):
                SportMonksFixtureSource(api_key="test").fetch()

    def test_extracts_sportmonks_fixture(self):
        payload = {
            "data": [{
                "id": 123,
                "starting_at": "2026-08-15 14:00:00",
                "participants": [
                    {"id": 1, "name": "Arsenal", "meta": {"location": "home"}},
                    {"id": 2, "name": "Chelsea", "meta": {"location": "away"}},
                ],
                "round": {"name": "1"},
                "scores": [],
            }],
        }
        fixtures = normalize_sportmonks_fixtures(payload)
        self.assertEqual(fixtures[0].id, "123")
        self.assertEqual(fixtures[0].home, "Arsenal")
        self.assertEqual(fixtures[0].round, 1)

    def test_live_match_score_is_not_treated_as_a_result(self):
        participants = [
            {"id": 1, "name": "Arsenal", "meta": {"location": "home"}},
            {"id": 2, "name": "Chelsea", "meta": {"location": "away"}},
        ]
        scores = [
            {"participant_id": 1, "description": "CURRENT", "score": {"goals": 1}},
            {"participant_id": 2, "description": "CURRENT", "score": {"goals": 0}},
        ]
        payload = {"data": [
            {"id": 1, "starting_at": "2026-08-15 14:00:00", "participants": participants,
             "scores": scores, "state": {"developer_name": "INPLAY_1ST_HALF"}},
            {"id": 2, "starting_at": "2026-08-16 14:00:00", "participants": participants,
             "scores": scores, "state": {"developer_name": "FT"}},
        ]}
        live, finished = normalize_sportmonks_fixtures(payload)
        self.assertFalse(live.played)
        self.assertTrue(finished.played)
        self.assertEqual((finished.home_score, finished.away_score), (1, 0))

    def test_cache_preserves_unicode_team_names(self):
        fixture = Fixture("1", "Deportivo A Coru\u00f1a", "Elche", None, 1)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fixtures.json"
            save_cache([fixture], path)
            content = path.read_text(encoding="utf-8")

        self.assertIn("Deportivo A Coru\u00f1a", content)
        self.assertNotIn(r"\u00f1", content)

class PredictionTests(unittest.TestCase):
    def test_team_strengths_produce_different_scorelines(self):
        fixtures = [
            Fixture("a", "Arsenal", "Chelsea", None, 1, 4, 0),
            Fixture("b", "Chelsea", "Arsenal", None, 2, 0, 3),
            Fixture("c", "Arsenal", "Chelsea", None, 3, 3, 0),
            Fixture("next-home", "Arsenal", "Chelsea", "2026-09-20", 4),
            Fixture("next-away", "Chelsea", "Arsenal", "2026-09-21", 4),
        ]
        predictions = PremierLeagueModel(fixtures).predict_upcoming(fixtures)
        self.assertGreater(len({prediction["predicted_score"] for prediction in predictions}), 1)

    def test_predicts_a_valid_scoreline_and_probabilities(self):
        fixtures = [
            Fixture("played", "Arsenal", "Chelsea", None, 1, 2, 0),
            Fixture("next", "Arsenal", "Chelsea", "2026-08-22T14:00:00Z", 2),
        ]
        prediction = PremierLeagueModel(fixtures).predict(fixtures[-1])
        self.assertRegex(prediction.predicted_score, r"^\d+-\d+$")
        self.assertGreater(prediction.expected_home_goals, 0)
        self.assertAlmostEqual(
            prediction.home_win_probability + prediction.draw_probability + prediction.away_win_probability,
            1.0,
            delta=0.01,
        )

    def test_completed_predictions_include_backtest_and_actual_scores(self):
        fixtures = [
            Fixture("first", "Arsenal", "Chelsea", "2026-08-15", 1, 2, 0),
            Fixture("second", "Chelsea", "Arsenal", "2026-08-22", 2, 1, 1),
        ]

        predictions = PremierLeagueModel(fixtures).predict_completed(fixtures)

        self.assertEqual(len(predictions), 2)
        self.assertRegex(predictions[0]["predicted_score"], r"^\d+-\d+$")
        self.assertEqual(predictions[0]["home_score"], 2)
        self.assertEqual(predictions[0]["away_score"], 0)

    def test_prior_seasons_inform_early_predictions(self):
        history = [
            Fixture(f"h{week}", "Arsenal", "Chelsea", f"2026-0{1 + week % 5}-1{week % 9}", week, 3, 0)
            for week in range(10)
        ]
        season = [Fixture("next", "Arsenal", "Chelsea", "2026-08-15", 1)]

        without_history = PremierLeagueModel(season).predict(season[0])
        with_history = PremierLeagueModel(season, history).predict(season[0])

        self.assertGreater(with_history.home_win_probability, without_history.home_win_probability)

    def test_promoted_team_starts_from_relegated_teams_rating(self):
        history = []
        for week in range(1, 9):
            history += [
                Fixture(f"a{week}", "Arsenal", "Burnley", f"2026-05-{week:02d}", week, 3, 0),
                Fixture(f"b{week}", "Burnley", "Chelsea", f"2026-05-{week + 10:02d}", week, 0, 2),
                Fixture(f"c{week}", "Chelsea", "Arsenal", f"2026-04-{week:02d}", week, 1, 1),
            ]
        season = [
            Fixture("1", "Arsenal", "Sunderland", "2026-08-15", 1),
            Fixture("2", "Chelsea", "Arsenal", "2026-08-22", 2),
        ]

        model = PremierLeagueModel(season, history)
        sunderland_attack, _ = model.ratings.rating("Sunderland")
        chelsea_attack, _ = model.ratings.rating("Chelsea")

        self.assertLess(sunderland_attack, chelsea_attack)

    def test_predicted_score_agrees_with_favourite(self):
        fixtures = [
            Fixture("played", "Arsenal", "Chelsea", "2026-08-15", 1, 2, 1),
            Fixture("next", "Arsenal", "Chelsea", "2026-08-22", 2),
        ]
        prediction = PremierLeagueModel(fixtures).predict(fixtures[-1])
        home_goals, away_goals = map(int, prediction.predicted_score.split("-"))
        outcome = max(
            ("home", prediction.home_win_probability),
            ("draw", prediction.draw_probability),
            ("away", prediction.away_win_probability),
            key=lambda item: item[1],
        )[0]
        self.assertEqual(outcome, "home" if home_goals > away_goals else "draw" if home_goals == away_goals else "away")

    def test_score_matrix_is_normalized(self):
        fixture = Fixture("next", "Arsenal", "Chelsea", "2026-08-22", 2)

        matrix = PremierLeagueModel([]).score_matrix(fixture)

        self.assertEqual(len(matrix), 9)
        self.assertEqual(len(matrix[0]), 9)
        self.assertAlmostEqual(
            sum(cell["probability"] for row in matrix for cell in row),
            1.0,
            delta=0.001,
        )
