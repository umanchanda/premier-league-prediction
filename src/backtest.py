"""Walk-forward backtest of the model on the latest prior season.

Every matchday is predicted using only results from before it, with the older
history seasons as the starting point, exactly as the live app would have done.
Lower RPS (ranked probability score) is better.

    python3 src/backtest.py
    python3 src/backtest.py --league la-liga
"""

from __future__ import annotations

import argparse
from statistics import mean

from fixtures import LEAGUES
from history import HISTORY_SEASONS, load_history
from model import PremierLeagueModel


def _outcome(home_goals: int, away_goals: int) -> int:
    return 0 if home_goals > away_goals else 1 if home_goals == away_goals else 2


def evaluate(league: str) -> dict[str, float]:
    games = load_history(league)
    season_ids = f"openfootball-{HISTORY_SEASONS[-1]}-"
    season = [game for game in games if game.id.startswith(season_ids)]
    earlier = [game for game in games if not game.id.startswith(season_ids)]
    predictions = PremierLeagueModel(season, earlier).predict_completed(season)

    rps, correct, exact, points = [], [], [], []
    for prediction in predictions:
        actual = _outcome(prediction["home_score"], prediction["away_score"])
        probabilities = [
            prediction["home_win_probability"], prediction["draw_probability"], prediction["away_win_probability"],
        ]
        cumulative = [sum(probabilities[: index + 1]) for index in range(2)]
        observed = [1.0 if actual <= index else 0.0 for index in range(2)]
        rps.append(sum((c - o) ** 2 for c, o in zip(cumulative, observed)) / 2)
        correct.append(probabilities.index(max(probabilities)) == actual)
        is_exact = prediction["predicted_score"] == f"{prediction['home_score']}-{prediction['away_score']}"
        exact.append(is_exact)
        predicted_home, predicted_away = map(int, prediction["predicted_score"].split("-"))
        points.append(3 if is_exact else int(_outcome(predicted_home, predicted_away) == actual))
    return {
        "matches": len(predictions),
        "rps": mean(rps),
        "result_accuracy": mean(correct),
        "exact_score_rate": mean(exact),
        "points_per_match": mean(points),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--league", choices=LEAGUES, action="append")
    args = parser.parse_args()
    for league in args.league or list(LEAGUES):
        result = evaluate(league)
        print(
            f"{league} {HISTORY_SEASONS[-1]}: {result['matches']} matches, RPS {result['rps']:.4f}, "
            f"result accuracy {result['result_accuracy']:.1%}, exact score {result['exact_score_rate']:.1%}, "
            f"points/match {result['points_per_match']:.2f}"
        )


if __name__ == "__main__":
    main()
