from flask import Flask, render_template, jsonify, request
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

import requests

app = Flask(__name__)

API_BASE = "https://apiv3.apifootball.com/"
LEAGUE_ID = "153"
SEASON_LABEL = "2026/2027"
SEASON_START = date(2026, 8, 1)
API_KEY_ENV = "APIFOOTBALL_KEY"
DETAIL_MAX_WORKERS = 8

FALLBACK_TEAM_NAMES = [
    "Birmingham", "Blackburn", "Bolton", "Bristol City", "Burnley", "Cardiff",
    "Charlton", "Derby", "Lincoln", "Middlesbrough", "Millwall", "Norwich",
    "Portsmouth", "Preston", "QPR", "Sheffield Utd", "Southampton", "Stoke",
    "Swansea", "Watford", "West Brom", "West Ham United", "Wolves", "Wrexham",
]

DISPLAY_NAME_OVERRIDES = {
    "West Ham": "West Ham United",
    "West Ham United": "West Ham United",
    "Sheffield Utd": "Sheffield United",
    "West Brom": "West Bromwich Albion",
}

CACHE_TTLS = {
    "teams": 21600,
    "events": 900,
    "aggregates": 900,
    "standings": 600,
    "h2h": 21600,
    "match_stats": 21600,
}

_cache = {
    "teams": None,
    "events": None,
    "aggregates": None,
    "standings": None,
    "h2h": {},
    "match_stats": {},
}

# Stat rows that are actually supported by the API feed or can be safely derived.
# Save percentage is deliberately excluded: the feed's saves and shots-on-target
# figures do not consistently reconcile, so publishing a derived save % would be misleading.
STAT_DEFINITIONS = {
    "attacking": [
        ("M", "Matches", "matches", "int"),
        ("G", "Goals", "goals", "int"),
        ("G/M", "Goals per Match", "goals_per_match", "decimal"),
        ("POSS%", "Average Possession", "possession", "percent"),
        ("SH", "Shots", "shots", "int"),
        ("SH/M", "Shots per Match", "shots_per_match", "decimal"),
        ("SOT", "Shots on Target", "shots_on_target", "int"),
        ("SOT%", "Shot Accuracy", "shot_accuracy", "percent"),
        ("SH-BLK", "Blocked Shots", "shots_blocked", "int"),
        ("SH-IN", "Shots Inside Box", "shots_inside_box", "int"),
        ("SH-OUT", "Shots Outside Box", "shots_outside_box", "int"),
        ("A", "Assists", "assists", "int"),
        ("OFF", "Offsides", "offsides", "int"),
        ("WOOD", "Hit Woodwork", "woodwork", "int"),
    ],
    "passing": [
        ("M", "Matches", "matches", "int"),
        ("PASS", "Passes", "passes", "int"),
        ("PASS/M", "Passes per Match", "passes_per_match", "decimal"),
        ("PASS-ACC", "Accurate Passes", "passes_accurate", "int"),
        ("PASS%", "Pass Completion %", "pass_completion", "percent"),
        ("PASS-KEY", "Key Passes", "key_passes", "int"),
        ("PASS-KEY/M", "Key Passes per Match", "key_passes_per_match", "decimal"),
        ("CRS", "Crosses", "crosses", "int"),
        ("CRS-ACC", "Accurate Crosses", "crosses_accurate", "int"),
        ("CRS%", "Cross Accuracy", "cross_accuracy", "percent"),
        ("CNR", "Corner Kicks", "corners", "int"),
    ],
    "defending": [
        ("M", "Matches", "matches", "int"),
        ("TKL", "Tackles", "tackles", "int"),
        ("TKL/M", "Tackles per Match", "tackles_per_match", "decimal"),
        ("INT", "Interceptions", "interceptions", "int"),
        ("INT/M", "Interceptions per Match", "interceptions_per_match", "decimal"),
        ("CLR", "Clearances", "clearances", "int"),
        ("CLR/M", "Clearances per Match", "clearances_per_match", "decimal"),
        ("BLK", "Blocks", "blocks", "int"),
        ("DUEL", "Duels", "duels_total", "int"),
        ("DUEL-W", "Duels Won", "duels_won", "int"),
        ("DUEL%", "Duel Win %", "duel_win_pct", "percent"),
        ("AER-W", "Aerial Duels Won", "aerials_won", "int"),
    ],
    "goalkeeping": [
        ("M", "Matches", "matches", "int"),
        ("GC", "Goals Conceded", "goals_against", "int"),
        ("GC/M", "Goals Conceded per Match", "goals_against_per_match", "decimal"),
        ("SV", "Saves", "saves", "int"),
        ("SV/M", "Saves per Match", "saves_per_match", "decimal"),
        ("SV-BOX", "Saves Inside Box", "saves_inside_box", "int"),
        ("SV-PK", "Penalty Saves", "penalty_saves", "int"),
        ("CS", "Clean Sheets", "clean_sheets", "int"),
    ],
    "miscellaneous": [
        ("M", "Matches", "matches", "int"),
        ("YC", "Yellow Cards", "yellow_cards", "int"),
        ("RC", "Red Cards", "red_cards", "int"),
        ("FOUL", "Fouls", "fouls", "int"),
        ("FOUL/M", "Fouls per Match", "fouls_per_match", "decimal"),
        ("PKC", "Penalties Conceded", "penalties_conceded", "int"),
        ("PK-W", "Penalties Won", "penalties_won", "int"),
        ("POSS-L", "Dispossessed", "dispossessed", "int"),
        ("DRB", "Dribbles Attempted", "dribbles_attempted", "int"),
        ("DRB-S", "Successful Dribbles", "dribbles_successful", "int"),
        ("DRB%", "Dribble Success %", "dribble_success_pct", "percent"),
    ],
}

LOWER_IS_BETTER = {
    "offsides", "goals_against", "goals_against_per_match",
    "yellow_cards", "red_cards", "fouls", "fouls_per_match",
    "penalties_conceded", "dispossessed",
}

# Metrics calculated from one or more source metrics. A derived value is only
# exposed if every source metric has complete coverage across the team's matches.
DERIVED_REQUIREMENTS = {
    "goals_per_match": ("goals",),
    "possession": ("possession_raw",),
    "shots_per_match": ("shots",),
    "shot_accuracy": ("shots", "shots_on_target"),
    "passes_per_match": ("passes",),
    "pass_completion": ("passes", "passes_accurate"),
    "key_passes_per_match": ("key_passes",),
    "cross_accuracy": ("crosses", "crosses_accurate"),
    "tackles_per_match": ("tackles",),
    "interceptions_per_match": ("interceptions",),
    "clearances_per_match": ("clearances",),
    "duel_win_pct": ("duels_total", "duels_won"),
    "goals_against_per_match": ("goals_against",),
    "saves_per_match": ("saves",),
    "fouls_per_match": ("fouls",),
    "dribble_success_pct": ("dribbles_attempted", "dribbles_successful"),
}

ALWAYS_COMPLETE = {"matches", "goals", "goals_against", "clean_sheets"}

TEAM_STAT_MAPPING = [
    ("Shots Total", "shots"),
    ("Shots On Goal", "shots_on_target"),
    ("Shots Off Goal", "shots_off_target"),
    ("Shots Blocked", "shots_blocked"),
    ("Shots Inside Box", "shots_inside_box"),
    ("Shots Outside Box", "shots_outside_box"),
    ("Fouls", "fouls"),
    ("Corners", "corners"),
    ("Offsides", "offsides"),
    ("Saves", "saves"),
    ("Passes Total", "passes"),
    ("Passes Accurate", "passes_accurate"),
    ("Yellow Cards", "yellow_cards"),
    ("Red Cards", "red_cards"),
]

PLAYER_STAT_MAPPING = {
    "player_tackles": "tackles",
    "player_blocks": "blocks",
    "player_total_crosses": "crosses",
    "player_acc_crosses": "crosses_accurate",
    "player_interceptions": "interceptions",
    "player_clearances": "clearances",
    "player_dispossesed": "dispossessed",
    "player_saves_inside_box": "saves_inside_box",
    "player_duels_total": "duels_total",
    "player_duels_won": "duels_won",
    "player_aerials_won": "aerials_won",
    "player_dribble_attempts": "dribbles_attempted",
    "player_dribble_succ": "dribbles_successful",
    "player_pen_save": "penalty_saves",
    "player_pen_committed": "penalties_conceded",
    "player_pen_won": "penalties_won",
    "player_hit_woodwork": "woodwork",
    "player_key_passes": "key_passes",
    "player_assists": "assists",
}


def _slugify(value):
    value = (value or "").strip().lower().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    aliases = {
        "west-ham-united": "west-ham", "west-ham": "west-ham",
        "sheffield-united": "sheffield-utd", "west-bromwich-albion": "west-brom",
        "queens-park-rangers": "qpr", "wolverhampton-wanderers": "wolves",
        "blackburn-rovers": "blackburn", "bolton-wanderers": "bolton",
        "bristol-city": "bristol-city", "cardiff-city": "cardiff",
        "charlton-athletic": "charlton", "derby-county": "derby",
        "lincoln-city": "lincoln", "norwich-city": "norwich",
        "preston-north-end": "preston", "stoke-city": "stoke",
        "swansea-city": "swansea", "watford": "watford", "wrexham": "wrexham",
        "birmingham-city": "birmingham",
    }
    return aliases.get(value, value)


def _display_name(name):
    return DISPLAY_NAME_OVERRIDES.get(name, name)


def _cache_get(name):
    entry = _cache.get(name)
    if not entry or name in {"h2h", "match_stats"}:
        return None
    if time.time() - entry["ts"] > CACHE_TTLS[name]:
        return None
    return entry["data"]


def _cache_set(name, data):
    _cache[name] = {"ts": time.time(), "data": data}


def _api_get(action, **params):
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        raise RuntimeError(
            f"{API_KEY_ENV} is not configured. Add your APIfootball key as an environment variable."
        )
    query = {"action": action, "APIkey": api_key}
    query.update({k: v for k, v in params.items() if v is not None})
    response = requests.get(API_BASE, params=query, timeout=40)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(str(data["error"]))
    return data


def _fallback_teams():
    return {
        _slugify(name): {"name": _display_name(name), "api_name": name, "api_id": None, "badge": ""}
        for name in FALLBACK_TEAM_NAMES
    }


def fetch_teams():
    cached = _cache_get("teams")
    if cached:
        return cached
    try:
        data = _api_get("get_teams", league_id=LEAGUE_ID)
        teams = {}
        for item in data if isinstance(data, list) else []:
            api_name = item.get("team_name", "")
            if not api_name:
                continue
            key = _slugify(api_name)
            teams[key] = {
                "name": _display_name(api_name),
                "api_name": api_name,
                "api_id": str(item.get("team_key", "")) or None,
                "badge": item.get("team_badge", ""),
            }
        if teams:
            teams = dict(sorted(teams.items(), key=lambda kv: kv[1]["name"]))
            _cache_set("teams", teams)
            return teams
    except Exception:
        pass
    teams = _fallback_teams()
    _cache_set("teams", teams)
    return teams


def _is_finished(match):
    status = str(match.get("match_status", "")).lower()
    if status in {"finished", "ft", "after penalties", "aet"}:
        return True
    return bool(match.get("match_hometeam_ft_score") != "" and match.get("match_awayteam_ft_score") != "")


def _fetch_events_call():
    data = _api_get(
        "get_events",
        **{
            "from": SEASON_START.isoformat(),
            "to": max(date.today(), SEASON_START).isoformat(),
            "league_id": LEAGUE_ID,
            "withPlayerStats": "1",
        },
    )
    data = [m for m in data if isinstance(m, dict) and _is_finished(m)] if isinstance(data, list) else []
    _cache_set("events", data)
    return data


def fetch_season_events():
    cached = _cache_get("events")
    if cached is not None:
        return cached
    return _fetch_events_call()


def _to_number(value):
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace(",", "")
    if not text or text in {"-", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalized_match_stats(rows):
    """Keep the last valid duplicate; APIfootball can emit duplicate stat rows."""
    result = {}
    for row in rows or []:
        stat_type = row.get("type")
        home = _to_number(row.get("home"))
        away = _to_number(row.get("away"))
        if stat_type and home is not None and away is not None:
            result[stat_type] = (home, away)
    return result


def _match_stats_cache_get(match_id):
    entry = _cache["match_stats"].get(str(match_id))
    if not entry:
        return None
    if time.time() - entry["ts"] > CACHE_TTLS["match_stats"]:
        return None
    return entry["data"]


def _fetch_match_statistics(match_id):
    """Fetch the dedicated statistics payload for one match, including player stats."""
    match_id = str(match_id or "")
    if not match_id:
        return {"statistics": [], "player_statistics": []}
    cached = _match_stats_cache_get(match_id)
    if cached is not None:
        return cached
    data = _api_get("get_statistics", match_id=match_id)
    payload = {}
    if isinstance(data, dict):
        payload = data.get(match_id) or {}
        if not payload and "statistics" in data:
            payload = data
    elif isinstance(data, list) and data:
        payload = data[0] if isinstance(data[0], dict) else {}
    result = {
        "statistics": payload.get("statistics", []) if isinstance(payload, dict) else [],
        "player_statistics": payload.get("player_statistics", []) if isinstance(payload, dict) else [],
    }
    _cache["match_stats"][match_id] = {"ts": time.time(), "data": result}
    return result


def _detail_payloads(events):
    """Fetch details only for matches whose get_events row lacks player statistics."""
    needed = [m for m in events if m.get("match_id") and not m.get("player_statistics")]
    if not needed:
        return {}
    results = {}
    workers = min(DETAIL_MAX_WORKERS, len(needed))
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_fetch_match_statistics, m.get("match_id")): str(m.get("match_id")) for m in needed}
        for future in as_completed(futures):
            match_id = futures[future]
            try:
                results[match_id] = future.result()
            except Exception:
                results[match_id] = {"statistics": [], "player_statistics": []}
    return results


def _blank_record():
    fields = [
        "matches", "goals", "goals_against", "clean_sheets", "possession_sum",
        "shots", "shots_on_target", "shots_off_target", "shots_blocked",
        "shots_inside_box", "shots_outside_box", "fouls", "corners", "offsides",
        "saves", "passes", "passes_accurate", "tackles", "blocks", "crosses",
        "crosses_accurate", "interceptions", "clearances", "dispossessed",
        "saves_inside_box", "duels_total", "duels_won", "aerials_won",
        "dribbles_attempted", "dribbles_successful", "penalty_saves",
        "penalties_conceded", "penalties_won", "woodwork", "key_passes",
        "assists", "yellow_cards", "red_cards",
    ]
    record = {field: 0.0 for field in fields}
    record["_coverage"] = {}
    return record


def _mark_coverage(record, metric):
    record["_coverage"][metric] = record["_coverage"].get(metric, 0) + 1


def _add_team_stat(record, stats, stat_type, key, side):
    values = stats.get(stat_type)
    if not values:
        return False
    record[key] += values[0 if side == "home" else 1]
    _mark_coverage(record, key)
    return True


def _player_totals(players, team_side):
    team_players = [p for p in (players or []) if p.get("team_name") == team_side]
    totals = {}
    available = set()
    if not team_players:
        return totals, available
    for source, dest in PLAYER_STAT_MAPPING.items():
        values = []
        for player in team_players:
            value = _to_number(player.get(source))
            if value is not None:
                values.append(value)
        if values:
            totals[dest] = sum(values)
            available.add(dest)
    for source, dest in (("player_yellowcards", "yellow_cards"), ("player_redcards", "red_cards")):
        values = []
        for player in team_players:
            value = _to_number(player.get(source))
            if value is not None:
                values.append(value)
        if values:
            totals[dest] = sum(values)
            available.add(dest)
    return totals, available


def _apply_player_totals(record, totals, available, already_covered):
    for metric in available:
        if metric in already_covered:
            continue
        record[metric] += totals.get(metric, 0.0)
        _mark_coverage(record, metric)


def _safe_div(numerator, denominator, multiplier=1.0):
    if denominator is None or denominator == 0:
        return 0.0
    return numerator / denominator * multiplier


def _metric_complete(record, metric):
    matches = int(record.get("matches", 0))
    if matches <= 0:
        return False
    if metric in ALWAYS_COMPLETE:
        return True
    if metric in DERIVED_REQUIREMENTS:
        return all(_metric_complete(record, source) for source in DERIVED_REQUIREMENTS[metric])
    return int(record.get("_coverage", {}).get(metric, 0)) == matches


def _metric_coverage(record, metric):
    matches = int(record.get("matches", 0))
    if metric in ALWAYS_COMPLETE:
        return matches, matches
    if metric in DERIVED_REQUIREMENTS:
        sources = DERIVED_REQUIREMENTS[metric]
        available = min((_metric_coverage(record, source)[0] for source in sources), default=0)
        return available, matches
    return int(record.get("_coverage", {}).get(metric, 0)), matches


def _finalize_record(record):
    m = record["matches"]
    possession_games = record.get("_coverage", {}).get("possession_raw", 0)
    record["possession"] = _safe_div(record["possession_sum"], possession_games)
    record["goals_per_match"] = _safe_div(record["goals"], m)
    record["shots_per_match"] = _safe_div(record["shots"], m)
    record["shot_accuracy"] = _safe_div(record["shots_on_target"], record["shots"], 100)
    record["passes_per_match"] = _safe_div(record["passes"], m)
    record["pass_completion"] = _safe_div(record["passes_accurate"], record["passes"], 100)
    record["key_passes_per_match"] = _safe_div(record["key_passes"], m)
    record["cross_accuracy"] = _safe_div(record["crosses_accurate"], record["crosses"], 100)
    record["tackles_per_match"] = _safe_div(record["tackles"], m)
    record["interceptions_per_match"] = _safe_div(record["interceptions"], m)
    record["clearances_per_match"] = _safe_div(record["clearances"], m)
    record["duel_win_pct"] = _safe_div(record["duels_won"], record["duels_total"], 100)
    record["goals_against_per_match"] = _safe_div(record["goals_against"], m)
    record["saves_per_match"] = _safe_div(record["saves"], m)
    record["fouls_per_match"] = _safe_div(record["fouls"], m)
    record["dribble_success_pct"] = _safe_div(record["dribbles_successful"], record["dribbles_attempted"], 100)
    return record


def build_aggregates():
    cached = _cache_get("aggregates")
    if cached:
        return cached

    teams = fetch_teams()
    id_to_key = {str(team["api_id"]): key for key, team in teams.items() if team.get("api_id")}
    aggregates = {key: _blank_record() for key in teams}
    events = fetch_season_events()
    details = _detail_payloads(events)

    for match in events:
        home_id = str(match.get("match_hometeam_id", ""))
        away_id = str(match.get("match_awayteam_id", ""))
        home_key = id_to_key.get(home_id) or _slugify(match.get("match_hometeam_name", ""))
        away_key = id_to_key.get(away_id) or _slugify(match.get("match_awayteam_name", ""))
        if home_key not in aggregates:
            aggregates[home_key] = _blank_record()
        if away_key not in aggregates:
            aggregates[away_key] = _blank_record()

        home, away = aggregates[home_key], aggregates[away_key]
        home["matches"] += 1
        away["matches"] += 1

        home_goals = _to_number(match.get("match_hometeam_ft_score"))
        away_goals = _to_number(match.get("match_awayteam_ft_score"))
        if home_goals is None:
            home_goals = _to_number(match.get("match_hometeam_score")) or 0
        if away_goals is None:
            away_goals = _to_number(match.get("match_awayteam_score")) or 0
        home["goals"] += home_goals
        home["goals_against"] += away_goals
        away["goals"] += away_goals
        away["goals_against"] += home_goals
        if away_goals == 0:
            home["clean_sheets"] += 1
        if home_goals == 0:
            away["clean_sheets"] += 1

        match_id = str(match.get("match_id", ""))
        detail = details.get(match_id, {})
        stats = _normalized_match_stats(match.get("statistics", []))
        detail_stats = _normalized_match_stats(detail.get("statistics", []))
        if detail_stats:
            stats.update(detail_stats)

        covered_home, covered_away = set(), set()
        for stat_type, key in TEAM_STAT_MAPPING:
            if _add_team_stat(home, stats, stat_type, key, "home"):
                covered_home.add(key)
            if _add_team_stat(away, stats, stat_type, key, "away"):
                covered_away.add(key)

        poss = stats.get("Ball Possession")
        if poss:
            home["possession_sum"] += poss[0]
            away["possession_sum"] += poss[1]
            _mark_coverage(home, "possession_raw")
            _mark_coverage(away, "possession_raw")

        players = match.get("player_statistics") or detail.get("player_statistics") or []
        home_totals, home_available = _player_totals(players, "home")
        away_totals, away_available = _player_totals(players, "away")
        _apply_player_totals(home, home_totals, home_available, covered_home)
        _apply_player_totals(away, away_totals, away_available, covered_away)

    for key in list(aggregates):
        aggregates[key] = _finalize_record(aggregates[key])
    _cache_set("aggregates", aggregates)
    return aggregates


def _ordinal(number):
    number = int(number)
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _metric_ranks(aggregates, metric):
    values = []
    for key, record in aggregates.items():
        if not _metric_complete(record, metric):
            continue
        value = record.get(metric)
        if value is None:
            continue
        values.append((key, float(value)))
    reverse = metric not in LOWER_IS_BETTER
    values.sort(key=lambda item: item[1], reverse=reverse)
    ranks, previous_value, previous_rank = {}, None, 0
    for index, (key, value) in enumerate(values, 1):
        if previous_value is not None and abs(value - previous_value) < 1e-9:
            rank = previous_rank
        else:
            rank = index
            previous_rank = rank
            previous_value = value
        ranks[key] = _ordinal(rank)
    return ranks


def _format_value(value, kind):
    if value is None:
        return "—"
    if kind == "int":
        return f"{int(round(value)):,}"
    if kind == "percent":
        return f"{value:.1f}%"
    if kind == "decimal":
        return f"{value:.2f}"
    return str(value)


def stats_for_team(team_key):
    teams = fetch_teams()
    if team_key not in teams:
        team_key = "west-ham" if "west-ham" in teams else next(iter(teams))
    aggregates = build_aggregates()
    record = aggregates.get(team_key, _blank_record())
    output = {}
    for category, definitions in STAT_DEFINITIONS.items():
        stats = []
        for abbrev, name, metric, kind in definitions:
            complete = _metric_complete(record, metric)
            available_matches, total_matches = _metric_coverage(record, metric)
            rank_map = _metric_ranks(aggregates, metric) if complete else {}
            stats.append({
                "abbrev": abbrev,
                "name": name,
                "club": _format_value(record.get(metric) if complete else None, kind),
                "rank": rank_map.get(team_key, "-"),
                "coverage": {
                    "available_matches": available_matches,
                    "total_matches": total_matches,
                    "complete": complete,
                },
            })
        output[category] = {"success": True, "stats": stats, "category": category}
    output["team"] = {"key": team_key, "name": teams[team_key]["name"]}
    output["source"] = "APIfootball.com"
    return output


def fetch_standings():
    cached = _cache_get("standings")
    if cached:
        return cached
    teams = fetch_teams()
    by_id = {str(v.get("api_id")): k for k, v in teams.items() if v.get("api_id")}
    by_name = {_slugify(v.get("api_name") or v.get("name")): k for k, v in teams.items()}
    data = _api_get("get_standings", league_id=LEAGUE_ID)
    result = {}
    for row in data if isinstance(data, list) else []:
        api_id = str(row.get("team_id", ""))
        key = by_id.get(api_id) or by_name.get(_slugify(row.get("team_name", "")))
        if not key:
            continue
        try:
            result[key] = {
                "position": int(row.get("overall_league_position", 0)),
                "points": int(row.get("overall_league_PTS", 0)),
                "played": int(row.get("overall_league_payed", 0)),
            }
        except (TypeError, ValueError):
            continue
    _cache_set("standings", result)
    return result


def fetch_h2h_data(team1_key, team2_key):
    teams = fetch_teams()
    if team1_key not in teams or team2_key not in teams:
        return {"error": "One or both teams could not be found."}
    if team1_key == team2_key:
        return {"error": "Please select two different teams."}
    id1 = teams[team1_key].get("api_id")
    id2 = teams[team2_key].get("api_id")
    if not id1 or not id2:
        return {"error": "Head-to-head data is unavailable until team IDs are loaded from APIfootball."}
    cache_key = f"{min(int(id1), int(id2))}-{max(int(id1), int(id2))}"
    cached = _cache["h2h"].get(cache_key)
    if cached and time.time() - cached["ts"] < CACHE_TTLS["h2h"]:
        matches = cached["data"]
    else:
        data = _api_get("get_H2H", firstTeamId=id1, secondTeamId=id2)
        matches = data.get("firstTeam_VS_secondTeam", []) if isinstance(data, dict) else []
        _cache["h2h"][cache_key] = {"ts": time.time(), "data": matches}

    name1, name2 = teams[team1_key]["name"], teams[team2_key]["name"]
    w = d = l = hw = hd = hl = aw = ad = al = 0
    goals_for = goals_against = 0
    recent = []
    for match in matches:
        if not _is_finished(match):
            continue
        home_id = str(match.get("match_hometeam_id", ""))
        away_id = str(match.get("match_awayteam_id", ""))
        hs = _to_number(match.get("match_hometeam_ft_score"))
        as_ = _to_number(match.get("match_awayteam_ft_score"))
        if hs is None:
            hs = _to_number(match.get("match_hometeam_score"))
        if as_ is None:
            as_ = _to_number(match.get("match_awayteam_score"))
        if hs is None or as_ is None:
            continue
        t1_home = home_id == str(id1)
        if not t1_home and away_id != str(id1):
            continue
        t1_score, t2_score = (hs, as_) if t1_home else (as_, hs)
        goals_for += int(t1_score)
        goals_against += int(t2_score)
        if t1_score > t2_score:
            w += 1
            if t1_home: hw += 1
            else: aw += 1
        elif t1_score < t2_score:
            l += 1
            if t1_home: hl += 1
            else: al += 1
        else:
            d += 1
            if t1_home: hd += 1
            else: ad += 1
        raw_date = match.get("match_date", "")
        try:
            date_str = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d %b %Y")
        except Exception:
            date_str = raw_date
        recent.append({
            "home": _display_name(match.get("match_hometeam_name", "")),
            "away": _display_name(match.get("match_awayteam_name", "")),
            "home_score": int(hs), "away_score": int(as_),
            "season": match.get("league_year") or match.get("league_name", ""),
            "date": date_str,
        })
    def _recent_sort_key(item):
        try:
            return datetime.strptime(item.get("date", ""), "%d %b %Y")
        except Exception:
            return datetime.min
    recent.sort(key=_recent_sort_key, reverse=True)
    return {
        "team1": name1, "team2": name2, "played": w + d + l,
        "overall": {"w": w, "d": d, "l": l},
        "home": {"w": hw, "d": hd, "l": hl},
        "away": {"w": aw, "d": ad, "l": al},
        "goals_for": goals_for, "goals_against": goals_against, "recent": recent,
    }


@app.route("/")
def index():
    return render_template("index.html", teams=fetch_teams())


@app.route("/api/teams")
def get_teams():
    return jsonify(fetch_teams())


@app.route("/api/stats")
def get_all_stats():
    team_key = request.args.get("team", "west-ham")
    try:
        return jsonify(stats_for_team(team_key))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503


@app.route("/api/stats/<category>")
def get_category_stats(category):
    if category not in STAT_DEFINITIONS:
        return jsonify({"error": "Invalid category"}), 400
    team_key = request.args.get("team", "west-ham")
    try:
        data = stats_for_team(team_key)
        return jsonify(data[category])
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc), "stats": []}), 503


@app.route("/api/standings")
def get_standings():
    try:
        return jsonify(fetch_standings())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503


@app.route("/api/h2h")
def get_h2h():
    team1 = request.args.get("team1", "west-ham")
    team2 = request.args.get("team2", "burnley")
    try:
        return jsonify(fetch_h2h_data(team1, team2))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503


@app.route("/api/team-news")
def get_team_news():
    return jsonify({
        "team1": {"players": [], "error": "Team news is not included in the free APIfootball feed."},
        "team2": {"players": [], "error": "Team news is not included in the free APIfootball feed."},
    })


@app.route("/api/predicted-lineups")
def get_predicted_lineups():
    team1_key = request.args.get("team1", "west-ham")
    team2_key = request.args.get("team2", "burnley")
    teams = fetch_teams()
    return jsonify({
        "team1": {"name": teams.get(team1_key, {}).get("name", team1_key), "starters": [], "error": "Predicted lineups are not included in the free APIfootball feed."},
        "team2": {"name": teams.get(team2_key, {}).get("name", team2_key), "starters": [], "error": "Predicted lineups are not included in the free APIfootball feed."},
        "sameMatch": False,
    })


@app.route("/api/health")
def health():
    return jsonify({
        "ok": True,
        "league_id": LEAGUE_ID,
        "season": SEASON_LABEL,
        "api_key_configured": bool(os.getenv(API_KEY_ENV, "").strip()),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
