import unittest

from fixtures import Fixture, normalize_sportmonks_fixtures
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
