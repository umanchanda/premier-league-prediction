import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fixtures import Fixture, SportMonksFixtureSource, normalize_sportmonks_fixtures, save_cache
from model import PremierLeagueModel


class FixtureNormalizationTests(unittest.TestCase):
    def test_sportmonks_source_accepts_league_and_season(self):
        source = SportMonksFixtureSource(api_key="test", season_id=27965, league_id=564)
        self.assertEqual(source.season_id, 27965)
        self.assertEqual(source.league_id, 564)

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
