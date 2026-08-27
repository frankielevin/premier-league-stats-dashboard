import copy

import app as core

# Verified post-match corrections for provider records that are demonstrably stale
# or incomplete. Values use the same APIfootball stat labels consumed by app.py.
# The Charlton match has been cross-checked against West Ham's official match
# report and independent full-time match-stat sources.
MATCH_OVERRIDES = {
    "812119": {
        "status": "verified_override",
        "reason": "APIfootball retained an incomplete match-stat snapshot after full-time.",
        "statistics": {
            "Shots Total": (25.0, 7.0),
            "Shots On Goal": (9.0, 5.0),
            "Shots Off Goal": (9.0, 2.0),
            "Shots Blocked": (7.0, 0.0),
            "Shots Inside Box": (18.0, 5.0),
            "Shots Outside Box": (7.0, 2.0),
            "Ball Possession": (77.6, 22.4),
            "Corners": (7.0, 4.0),
            "Fouls": (9.0, 16.0),
            "Offsides": (0.0, 1.0),
            "Saves": (3.0, 8.0),
            "Passes Total": (664.0, 191.0),
            "Passes Accurate": (612.0, 124.0),
            "Yellow Cards": (2.0, 3.0),
            "Red Cards": (0.0, 0.0),
        },
        # Player-level statistics from APIfootball are also incomplete for this
        # match. Excluding them is safer than publishing false tackles/duels/etc.
        "discard_player_statistics": True,
    },
}

_PATCHED = False


def _replace_statistics(rows, replacements):
    rows = [dict(row) for row in (rows or []) if isinstance(row, dict)]
    by_type = {}
    for index, row in enumerate(rows):
        stat_type = row.get("type")
        if stat_type:
            by_type[stat_type] = index

    for stat_type, values in replacements.items():
        home, away = values
        replacement = {"type": stat_type, "home": home, "away": away}
        if stat_type in by_type:
            rows[by_type[stat_type]] = replacement
        else:
            rows.append(replacement)
    return rows


def _apply_override_to_match(match):
    match_id = str((match or {}).get("match_id", ""))
    override = MATCH_OVERRIDES.get(match_id)
    if not override:
        return match

    updated = copy.deepcopy(match)
    updated["statistics"] = _replace_statistics(
        updated.get("statistics", []), override.get("statistics", {})
    )
    if override.get("discard_player_statistics"):
        updated["player_statistics"] = []
    updated["_data_quality"] = {
        "status": override.get("status", "verified_override"),
        "reason": override.get("reason", "Verified provider correction."),
    }
    return updated


def _apply_override_to_detail(match_id, detail):
    override = MATCH_OVERRIDES.get(str(match_id))
    if not override:
        return detail

    updated = copy.deepcopy(detail or {})
    updated["statistics"] = _replace_statistics(
        updated.get("statistics", []), override.get("statistics", {})
    )
    if override.get("discard_player_statistics"):
        updated["player_statistics"] = []
    return updated


def apply():
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    original_fetch_events = core.fetch_season_events
    original_fetch_match_statistics = core._fetch_match_statistics
    original_stats_for_team = core.stats_for_team

    def fetch_events_with_integrity():
        events = original_fetch_events()
        return [_apply_override_to_match(match) for match in events]

    def fetch_match_statistics_with_integrity(match_id):
        detail = original_fetch_match_statistics(match_id)
        return _apply_override_to_detail(match_id, detail)

    def stats_for_team_with_quality(team_key):
        output = original_stats_for_team(team_key)
        teams = core.fetch_teams()
        team = teams.get(team_key, {})
        api_id = str(team.get("api_id") or "")
        affected = []
        for match in fetch_events_with_integrity():
            match_id = str(match.get("match_id", ""))
            if match_id not in MATCH_OVERRIDES:
                continue
            if api_id and api_id not in {
                str(match.get("match_hometeam_id", "")),
                str(match.get("match_awayteam_id", "")),
            }:
                continue
            affected.append({
                "match_id": match_id,
                "status": MATCH_OVERRIDES[match_id].get("status", "verified_override"),
            })
        output["data_quality"] = {
            "verified_overrides": affected,
            "note": "Provider errors are corrected only from independently verified full-time data; unverified player-level fields are excluded rather than estimated.",
        }
        return output

    core.fetch_season_events = fetch_events_with_integrity
    core._fetch_match_statistics = fetch_match_statistics_with_integrity
    core.stats_for_team = stats_for_team_with_quality

    # Force any warm-process aggregate created before patching to rebuild from
    # the corrected match-level source.
    core._cache["events"] = None
    core._cache["aggregates"] = None
    core._cache["match_stats"].pop("812119", None)
