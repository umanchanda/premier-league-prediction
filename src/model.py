"""Poisson scoreline model fitted to recent league results.

Each team gets one attacking and one defensive rating, plus a league-wide home
advantage, fitted by weighted Poisson regression. Prior seasons are included
with exponential time decay so early-season predictions are not based on a
handful of games, and promoted teams start from the average rating of the teams
they replaced. Ridge shrinkage pulls teams with little data toward average.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable

import numpy as np

from fixtures import Fixture

# Only used before any results are available.
DEFAULT_HOME_GOALS = 1.5
DEFAULT_AWAY_GOALS = 1.2
HALF_LIFE_DAYS = 180
HISTORY_WINDOW_DAYS = 730
# Ridge strength on team ratings, in units of a full-weight match.
RATING_RIDGE = 4.0
BASELINE_RIDGE = 1.0
# A team that played within this many days of the latest prior result was in last season's league.
LAST_SEASON_DAYS = 60


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


def _kickoff_date(fixture: Fixture) -> date | None:
    try:
        return date.fromisoformat((fixture.kickoff or "")[:10])
    except ValueError:
        return None


class _Ratings:
    """Weighted Poisson regression: log(goals) = baseline + home + attack - defence."""

    def __init__(
        self,
        games: list[Fixture],
        as_of: date | None,
        ridge: float = RATING_RIDGE,
        prior: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        prior = prior or {}
        teams = sorted({game.home for game in games} | {game.away for game in games})
        self.index = {team: position for position, team in enumerate(teams)}
        count = len(teams)
        size = 2 + 2 * count
        target = np.zeros(size)
        target[0] = math.log(DEFAULT_AWAY_GOALS)
        target[1] = math.log(DEFAULT_HOME_GOALS / DEFAULT_AWAY_GOALS)
        for team, position in self.index.items():
            target[2 + position], target[2 + count + position] = prior.get(team, (0.0, 0.0))
        penalty = np.full(size, ridge)
        penalty[:2] = BASELINE_RIDGE

        design = np.zeros((2 * len(games), size))
        goals = np.zeros(2 * len(games))
        weights = np.zeros(2 * len(games))
        for row, game in enumerate(games):
            home, away = self.index[game.home], self.index[game.away]
            played_on = _kickoff_date(game)
            age = (as_of - played_on).days if as_of and played_on else 0
            weight = 0.5 ** (max(age, 0) / HALF_LIFE_DAYS)
            design[2 * row, [0, 1, 2 + home, 2 + count + away]] = 1
            design[2 * row + 1, [0, 2 + away, 2 + count + home]] = 1
            goals[2 * row], goals[2 * row + 1] = game.home_score or 0, game.away_score or 0
            weights[2 * row] = weights[2 * row + 1] = weight

        params = target.copy()
        for _ in range(50):
            rates = np.exp(design @ params)
            gradient = design.T @ (weights * (goals - rates)) - penalty * (params - target)
            hessian = design.T @ (design * (weights * rates)[:, None]) + np.diag(penalty)
            step = np.linalg.solve(hessian, gradient)
            params += step
            if np.abs(step).max() < 1e-8:
                break
        self.params = params
        self.count = count
        self.prior = prior

    def rating(self, team: str) -> tuple[float, float]:
        """Return (attack, concede) log-ratings; unseen teams fall back to their prior."""
        position = self.index.get(team)
        if position is None:
            return self.prior.get(team, (0.0, 0.0))
        return float(self.params[2 + position]), float(self.params[2 + self.count + position])

    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        home_attack, home_concede = self.rating(home)
        away_attack, away_concede = self.rating(away)
        baseline, home_advantage = self.params[0], self.params[1]
        return (
            math.exp(baseline + home_advantage + home_attack + away_concede),
            math.exp(baseline + away_attack + home_concede),
        )


def _promoted_prior(history: list[Fixture], season_teams: set[str]) -> dict[str, tuple[float, float]]:
    """Start promoted teams from the average end-of-season rating of the relegated teams."""
    dated = [(game, _kickoff_date(game)) for game in history]
    dated = [(game, played_on) for game, played_on in dated if played_on]
    if not dated or not season_teams:
        return {}
    latest = max(played_on for _, played_on in dated)
    last_season = [game for game, played_on in dated if (latest - played_on).days <= LAST_SEASON_DAYS]
    last_season_teams = {game.home for game in last_season} | {game.away for game in last_season}
    relegated = last_season_teams - season_teams
    promoted = season_teams - last_season_teams
    if not relegated or not promoted:
        return {}
    ratings = _Ratings([game for game, _ in dated], latest, ridge=1.0)
    attack = sum(ratings.rating(team)[0] for team in relegated) / len(relegated)
    concede = sum(ratings.rating(team)[1] for team in relegated) / len(relegated)
    return {team: (attack, concede) for team in promoted}


class PremierLeagueModel:
    """Predicts scorelines for one league from this season's fixtures plus prior seasons."""

    def __init__(
        self,
        fixtures: list[Fixture],
        history: Iterable[Fixture] = (),
        _prior: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        self.history = [game for game in history if game.played]
        season_teams = {fixture.home for fixture in fixtures} | {fixture.away for fixture in fixtures}
        self.prior = _promoted_prior(self.history, season_teams) if _prior is None else _prior
        completed = [fixture for fixture in fixtures if fixture.played]
        dates = [played_on for game in self.history + completed if (played_on := _kickoff_date(game))]
        as_of = max(dates) if dates else None
        games = [
            game for game in self.history + completed
            if not as_of or not (played_on := _kickoff_date(game)) or (as_of - played_on).days <= HISTORY_WINDOW_DAYS
        ]
        self.ratings = _Ratings(games, as_of, prior=self.prior)

    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        home_mean, away_mean = self.ratings.expected_goals(home, away)
        return max(0.15, home_mean), max(0.15, away_mean)

    def predict(self, fixture: Fixture, max_goals: int = 8) -> ScorelinePrediction:
        home_mean, away_mean = self.expected_goals(fixture.home, fixture.away)
        probabilities = self._score_probabilities(home_mean, away_mean, max_goals)
        outcomes = {"home": 0.0, "draw": 0.0, "away": 0.0}
        for (home_goals, away_goals), probability in probabilities.items():
            outcomes[self._outcome(home_goals, away_goals)] += probability
        # Pick the likeliest scoreline within the likeliest result, so the headline
        # score never contradicts the favourite (e.g. 1-1 when a home win is 50%).
        likeliest = max(outcomes, key=outcomes.get)
        (home_goals, away_goals), probability = max(
            ((score, probability) for score, probability in probabilities.items() if self._outcome(*score) == likeliest),
            key=lambda item: item[1],
        )
        return ScorelinePrediction(
            fixture_id=fixture.id, home=fixture.home, away=fixture.away, kickoff=fixture.kickoff,
            expected_home_goals=round(home_mean, 2), expected_away_goals=round(away_mean, 2),
            predicted_score=f"{home_goals}-{away_goals}",
            home_win_probability=round(outcomes["home"], 4), draw_probability=round(outcomes["draw"], 4),
            away_win_probability=round(outcomes["away"], 4), scoreline_probability=round(probability, 4),
        )

    @staticmethod
    def _outcome(home_goals: int, away_goals: int) -> str:
        return "home" if home_goals > away_goals else "draw" if home_goals == away_goals else "away"

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
        by_day: dict[date | None, list[Fixture]] = defaultdict(list)
        for fixture in completed:
            by_day[_kickoff_date(fixture)].append(fixture)
        history: list[Fixture] = []
        predictions: list[dict] = []
        for day_fixtures in by_day.values():
            # Refit once per matchday: games on the same day can't inform each other.
            model = PremierLeagueModel(fixtures_before(fixtures, history), self.history, _prior=self.prior)
            for fixture in day_fixtures:
                prediction = asdict(model.predict(fixture))
                prediction["home_score"] = fixture.home_score
                prediction["away_score"] = fixture.away_score
                predictions.append(prediction)
            history.extend(day_fixtures)
        return predictions

    def model_before(self, fixtures: list[Fixture], fixture: Fixture) -> PremierLeagueModel:
        """A model fitted only on results from before the given fixture's matchday."""
        played_on = _kickoff_date(fixture)
        earlier = [
            item for item in fixtures
            if item.played and item.id != fixture.id
            and (played_on is None or ((item_date := _kickoff_date(item)) is not None and item_date < played_on))
        ]
        return PremierLeagueModel(fixtures_before(fixtures, earlier), self.history, _prior=self.prior)


def fixtures_before(fixtures: list[Fixture], played: list[Fixture]) -> list[Fixture]:
    """Keep the full schedule (for team lists) but only the given results."""
    played_ids = {fixture.id for fixture in played}
    return [
        fixture if fixture.id in played_ids or not fixture.played
        else Fixture(fixture.id, fixture.home, fixture.away, fixture.kickoff, fixture.round)
        for fixture in fixtures
    ]
