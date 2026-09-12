import unittest

from fixtures import Fixture, normalize_fixtures, normalize_sportmonks_fixtures
from model import PremierLeagueModel


class FixtureNormalizationTests(unittest.TestCase):
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

    def test_extracts_premier_league_fixture_from_team_payload(self):
        payload = {
            "fixtures": {
                "allFixtures": {
                    "fixtures": [{
                        "id": 123,
                        "homeTeamName": "Arsenal",
                        "awayTeamName": "Chelsea",
                        "leagueName": "Premier League",
                        "seasonName": "2026/2027",
                        "status": {"utcTime": "2026-08-15T14:00:00.000Z"},
                        "round": 1,
                    }]
                }
            }
        }
        fixtures = normalize_fixtures(payload)
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0].home, "Arsenal")
        self.assertEqual(fixtures[0].round, 1)

    def test_ignores_placeholder_scores_for_unfinished_fixture(self):
        payload = {
            "fixtures": [{
                "id": 456,
                "home": {"name": "Arsenal", "score": 0},
                "away": {"name": "Chelsea", "score": 0},
                "tournament": {"name": "Premier League"},
                "season": "2026/2027",
                "status": {"utcTime": "2027-01-02T15:00:00.000Z", "finished": False},
            }]
        }
        fixtures = normalize_fixtures(payload)
        self.assertEqual(len(fixtures), 1)
        self.assertFalse(fixtures[0].played)


class PredictionTests(unittest.TestCase):
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
