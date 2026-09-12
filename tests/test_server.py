import unittest

from fixtures import Fixture
from fixtures import filter_fixtures
import server


class FixtureEndpointTests(unittest.TestCase):
    def test_filters_upcoming_fixtures(self):
        fixtures = [
            Fixture("played", "Home", "Away", None, 1, 2, 1),
            Fixture("upcoming", "Home", "Away", None, 2),
        ]

        filtered = filter_fixtures(fixtures, upcoming_only=True, round=None)

        self.assertEqual([fixture.id for fixture in filtered], ["upcoming"])

    def test_filters_requested_round(self):
        fixtures = [
            Fixture("one", "Home", "Away", None, 1),
            Fixture("two", "Home", "Away", None, 2),
        ]

        filtered = filter_fixtures(fixtures, upcoming_only=False, round=2)

        self.assertEqual([fixture.id for fixture in filtered], ["two"])

    def test_la_liga_endpoint_filters_upcoming_fixtures(self):
        original = server._la_liga_fixtures
        server._la_liga_fixtures = [
            Fixture("played", "Home", "Away", None, 1, 2, 1),
            Fixture("upcoming", "Home", "Away", None, 2),
        ]

        try:
            response = server.fixtures(league="la-liga", upcoming_only=True, round=None)
        finally:
            server._la_liga_fixtures = original

        self.assertEqual([fixture.id for fixture in response["fixtures"]], ["upcoming"])

    def test_la_liga_endpoint_filters_requested_round(self):
        original = server._la_liga_fixtures
        server._la_liga_fixtures = [
            Fixture("one", "Home", "Away", None, 1),
            Fixture("two", "Home", "Away", None, 2),
        ]

        try:
            response = server.fixtures(league="la-liga", upcoming_only=False, round=2)
        finally:
            server._la_liga_fixtures = original

        self.assertEqual([fixture.id for fixture in response["fixtures"]], ["two"])
