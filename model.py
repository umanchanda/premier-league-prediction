"""Poisson scoreline model trained from completed Premier League fixtures."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, dataclass

from fixtures import Fixture

LEAGUE_HOME_GOALS = 1.55
LEAGUE_AWAY_GOALS = 1.25
# Keep an early-season league baseline without flattening every matchup to 1-1.
PRIOR_MATCHES = 2.0


@dataclass(frozen=True)
class ScorelinePrediction:
    fixture_id: str
    home: str
    away: str
    kickoff: str | None
    expected_home_goals: float
    expected_away_goals: float
    predicted_score: str
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    scoreline_probability: float


def _poisson(k: int, mean: float) -> float:
    return math.exp(-mean) * mean**k / math.factorial(k)


class PremierLeagueModel:
    """Fits attacking and defensive rates with shrinkage to league averages."""

    def __init__(self, fixtures: list[Fixture]) -> None:
        completed = [fixture for fixture in fixtures if fixture.played]
        self.home_scored: dict[str, float] = defaultdict(float)
        self.home_conceded: dict[str, float] = defaultdict(float)
        self.away_scored: dict[str, float] = defaultdict(float)
        self.away_conceded: dict[str, float] = defaultdict(float)
        self.home_matches: dict[str, int] = defaultdict(int)
        self.away_matches: dict[str, int] = defaultdict(int)
        for fixture in completed:
            self.home_scored[fixture.home] += fixture.home_score or 0
            self.home_conceded[fixture.home] += fixture.away_score or 0
            self.away_scored[fixture.away] += fixture.away_score or 0
            self.away_conceded[fixture.away] += fixture.home_score or 0
            self.home_matches[fixture.home] += 1
            self.away_matches[fixture.away] += 1

    @staticmethod
    def _smoothed(total: float, matches: int, prior: float) -> float:
        return (total + PRIOR_MATCHES * prior) / (matches + PRIOR_MATCHES)

    def _venue_rate(
        self,
        primary_total: float,
        primary_matches: int,
        prior: float,
        fallback_total: float,
        fallback_matches: int,
        fallback_prior: float,
    ) -> float:
        if primary_matches:
            return self._smoothed(primary_total, primary_matches, prior)
        if fallback_matches:
            adjusted_total = fallback_total * prior / fallback_prior
            return self._smoothed(adjusted_total, fallback_matches, prior)
        return prior

    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        home_attack = self._venue_rate(
            self.home_scored[home], self.home_matches[home], LEAGUE_HOME_GOALS,
            self.away_scored[home], self.away_matches[home], LEAGUE_AWAY_GOALS,
        )
        away_defence = self._venue_rate(
            self.away_conceded[away], self.away_matches[away], LEAGUE_HOME_GOALS,
            self.home_conceded[away], self.home_matches[away], LEAGUE_AWAY_GOALS,
        )
        away_attack = self._venue_rate(
            self.away_scored[away], self.away_matches[away], LEAGUE_AWAY_GOALS,
            self.home_scored[away], self.home_matches[away], LEAGUE_HOME_GOALS,
        )
        home_defence = self._venue_rate(
            self.home_conceded[home], self.home_matches[home], LEAGUE_AWAY_GOALS,
            self.away_conceded[home], self.away_matches[home], LEAGUE_HOME_GOALS,
        )
        return (max(0.15, home_attack * away_defence / LEAGUE_HOME_GOALS),
                max(0.15, away_attack * home_defence / LEAGUE_AWAY_GOALS))

    def predict(self, fixture: Fixture, max_goals: int = 8) -> ScorelinePrediction:
        home_mean, away_mean = self.expected_goals(fixture.home, fixture.away)
        probabilities = self._score_probabilities(home_mean, away_mean, max_goals)
        home_win = sum(probability for (home_goals, away_goals), probability in probabilities.items() if home_goals > away_goals)
        draw = sum(probability for (home_goals, away_goals), probability in probabilities.items() if home_goals == away_goals)
        away_win = sum(probability for (home_goals, away_goals), probability in probabilities.items() if home_goals < away_goals)
        (home_goals, away_goals), probability = max(probabilities.items(), key=lambda item: item[1])
        return ScorelinePrediction(
            fixture_id=fixture.id, home=fixture.home, away=fixture.away, kickoff=fixture.kickoff,
            expected_home_goals=round(home_mean, 2), expected_away_goals=round(away_mean, 2),
            predicted_score=f"{home_goals}-{away_goals}",
            home_win_probability=round(home_win, 4), draw_probability=round(draw, 4),
            away_win_probability=round(away_win, 4), scoreline_probability=round(probability, 4),
        )

    @staticmethod
    def _score_probabilities(home_mean: float, away_mean: float, max_goals: int) -> dict[tuple[int, int], float]:
        return {
            (home_goals, away_goals): _poisson(home_goals, home_mean) * _poisson(away_goals, away_mean)
            for home_goals in range(max_goals + 1)
            for away_goals in range(max_goals + 1)
        }

    def score_matrix(self, fixture: Fixture, max_goals: int = 8) -> list[list[dict[str, float | int]]]:
        """Return normalized score probabilities for a fixture heatmap."""
        home_mean, away_mean = self.expected_goals(fixture.home, fixture.away)
        probabilities = self._score_probabilities(home_mean, away_mean, max_goals)
        total = sum(probabilities.values())
        return [
            [
                {
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "probability": round(probabilities[(home_goals, away_goals)] / total, 6),
                }
                for away_goals in range(max_goals + 1)
            ]
            for home_goals in range(max_goals + 1)
        ]

    def predict_upcoming(self, fixtures: list[Fixture]) -> list[dict]:
        return [asdict(self.predict(fixture)) for fixture in fixtures if not fixture.played]

    def predict_completed(self, fixtures: list[Fixture]) -> list[dict]:
        """Backtest completed fixtures using only results available beforehand."""
        completed = sorted(
            (fixture for fixture in fixtures if fixture.played),
            key=lambda fixture: fixture.kickoff or "",
        )
        history: list[Fixture] = []
        predictions: list[dict] = []
        for fixture in completed:
            prediction = asdict(PremierLeagueModel(history).predict(fixture))
            prediction["home_score"] = fixture.home_score
            prediction["away_score"] = fixture.away_score
            predictions.append(prediction)
            history.append(fixture)
        return predictions
