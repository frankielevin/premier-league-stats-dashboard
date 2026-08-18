from flask import Flask, jsonify, request

import app as core

app = Flask(__name__)


def _definition(category, abbrev):
    definitions = core.STAT_DEFINITIONS.get(category, [])
    return next((item for item in definitions if item[0] == abbrev), None)


def _leaderboard_rows(metric, kind):
    teams = core.fetch_teams()
    aggregates = core.build_aggregates()
    ranks = core._metric_ranks(aggregates, metric)
    higher_is_better = metric not in core.LOWER_IS_BETTER

    available = []
    unavailable = []

    for team_key, team in teams.items():
        record = aggregates.get(team_key, core._blank_record())
        complete = core._metric_complete(record, metric)
        raw_value = record.get(metric) if complete else None
        available_matches, total_matches = core._metric_coverage(record, metric)
        row = {
            "team_key": team_key,
            "team": team.get("name", team_key),
            "value": core._format_value(raw_value, kind) if complete else "—",
            "rank": ranks.get(team_key, "-"),
            "available": bool(complete and raw_value is not None),
            "coverage": {
                "available_matches": available_matches,
                "total_matches": total_matches,
                "complete": complete,
            },
            "_raw": float(raw_value) if complete and raw_value is not None else None,
        }
        if row["available"]:
            available.append(row)
        else:
            unavailable.append(row)

    available.sort(key=lambda row: row["_raw"], reverse=higher_is_better)
    unavailable.sort(key=lambda row: row["team"].lower())

    rows = available + unavailable
    for row in rows:
        row.pop("_raw", None)
    return rows


@app.route("/api/leaderboard")
def leaderboard():
    category = request.args.get("category", "").strip().lower()
    abbrev = request.args.get("stat", "").strip()
    definition = _definition(category, abbrev)
    if not definition:
        return jsonify({"error": "Unknown Championship statistic."}), 400

    _, name, metric, kind = definition
    try:
        rows = _leaderboard_rows(metric, kind)
        return jsonify({
            "success": True,
            "category": category,
            "stat": {
                "abbrev": abbrev,
                "name": name,
                "metric": metric,
                "direction": "lower" if metric in core.LOWER_IS_BETTER else "higher",
            },
            "teams": rows,
            "team_count": len(rows),
            "source": "APIfootball.com",
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503
