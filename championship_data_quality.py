from flask import jsonify, request

from championship_entry import load_app

# championship_entry places the isolated Championship source directory first on
# sys.path before importing its app module. load_app returns that exact Flask app
# wrapped for the /championship namespace.
app = load_app("app")

# Import after load_app so this resolves to championship/app.py, not the legacy
# Premier League app.py at repository root.
import app as core

KEY_STATS = (
    "Shots Total",
    "Shots On Goal",
    "Shots Off Goal",
    "Shots Blocked",
    "Shots Inside Box",
    "Shots Outside Box",
    "Ball Possession",
    "Corners",
    "Passes Total",
    "Passes Accurate",
)

PLAYER_SHOT_FIELDS = (
    "player_shots_total",
    "player_shots_on_goal",
)


def _side_value(values, side):
    if not values:
        return None
    return values[0 if side == "home" else 1]


def _compact(stats, side):
    return {
        name: _side_value(stats.get(name), side)
        for name in KEY_STATS
        if stats.get(name)
    }


def _player_shot_totals(players, side):
    team_players = [p for p in (players or []) if p.get("team_name") == side]
    totals = {}
    for field in PLAYER_SHOT_FIELDS:
        values = []
        for player in team_players:
            value = core._to_number(player.get(field))
            if value is not None:
                values.append(value)
        totals[field] = sum(values) if values else None
    return {"players_found": len(team_players), **totals}


def _validation(stats, side, player_shots=None):
    issues = []
    shots = _side_value(stats.get("Shots Total"), side)
    sot = _side_value(stats.get("Shots On Goal"), side)
    inside = _side_value(stats.get("Shots Inside Box"), side)
    outside = _side_value(stats.get("Shots Outside Box"), side)
    passes = _side_value(stats.get("Passes Total"), side)
    accurate = _side_value(stats.get("Passes Accurate"), side)

    if shots is not None and sot is not None and sot > shots:
        issues.append("shots_on_target_exceeds_total_shots")
    if shots is not None and inside is not None and outside is not None:
        if abs((inside + outside) - shots) > 1:
            issues.append("inside_plus_outside_does_not_match_total_shots")
    if passes is not None and accurate is not None and accurate > passes:
        issues.append("accurate_passes_exceed_total_passes")

    possession = stats.get("Ball Possession")
    if possession:
        total = possession[0] + possession[1]
        if abs(total - 100) > 2:
            issues.append("possession_does_not_sum_to_100")

    required = ("Shots Total", "Shots On Goal", "Ball Possession", "Corners", "Passes Total")
    missing = [name for name in required if not stats.get(name)]
    if missing:
        issues.append("missing_core_stats:" + ",".join(missing))

    if player_shots:
        player_total = player_shots.get("player_shots_total")
        player_sot = player_shots.get("player_shots_on_goal")
        if shots is not None and player_total is not None and abs(shots - player_total) > 1:
            issues.append(f"team_shots_disagree_with_player_sum:{shots:g}_vs_{player_total:g}")
        if sot is not None and player_sot is not None and abs(sot - player_sot) > 1:
            issues.append(f"team_sot_disagree_with_player_sum:{sot:g}_vs_{player_sot:g}")

    return {"valid": not issues, "issues": issues}


@app.route("/api/data-quality")
def data_quality():
    team_key = str(request.args.get("team", "west-ham") or "west-ham").strip()
    teams = core.fetch_teams()
    team = teams.get(team_key)
    if not team:
        return jsonify({"error": "Unknown team"}), 404

    team_id = str(team.get("api_id") or "")
    events = core.fetch_season_events()
    output = []

    for match in events:
        home_id = str(match.get("match_hometeam_id", ""))
        away_id = str(match.get("match_awayteam_id", ""))
        if team_id and team_id not in {home_id, away_id}:
            continue
        if not team_id:
            names = {
                core._slugify(match.get("match_hometeam_name", "")),
                core._slugify(match.get("match_awayteam_name", "")),
            }
            if team_key not in names:
                continue

        side = "home" if (team_id and home_id == team_id) or core._slugify(match.get("match_hometeam_name", "")) == team_key else "away"
        match_id = str(match.get("match_id", ""))
        embedded = core._normalized_match_stats(match.get("statistics", []))
        embedded_player_shots = _player_shot_totals(match.get("player_statistics", []), side)

        try:
            detail = core._fetch_match_statistics(match_id)
            dedicated = core._normalized_match_stats(detail.get("statistics", []))
            dedicated_player_shots = _player_shot_totals(detail.get("player_statistics", []), side)
            dedicated_error = None
        except Exception as exc:
            dedicated = {}
            dedicated_player_shots = {"players_found": 0, "player_shots_total": None, "player_shots_on_goal": None}
            dedicated_error = str(exc)

        output.append({
            "match_id": match_id,
            "date": match.get("match_date"),
            "home": match.get("match_hometeam_name"),
            "away": match.get("match_awayteam_name"),
            "score": f"{match.get('match_hometeam_ft_score', match.get('match_hometeam_score', ''))}-{match.get('match_awayteam_ft_score', match.get('match_awayteam_score', ''))}",
            "team_side": side,
            "embedded": _compact(embedded, side),
            "embedded_player_shots": embedded_player_shots,
            "dedicated": _compact(dedicated, side),
            "dedicated_player_shots": dedicated_player_shots,
            "embedded_validation": _validation(embedded, side, embedded_player_shots),
            "dedicated_validation": _validation(dedicated, side, dedicated_player_shots),
            "dedicated_error": dedicated_error,
        })

    return jsonify({"team": team_key, "matches": output})
