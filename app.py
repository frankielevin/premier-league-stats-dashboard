from flask import Flask, render_template, jsonify, request
import os
import re
import time
from datetime import date, datetime, timedelta

import requests

app = Flask(__name__)

API_BASE = "https://apiv3.apifootball.com/"
LEAGUE_ID = "153"
SEASON_LABEL = "2026/2027"
SEASON_START = date(2026, 8, 1)
API_KEY_ENV = "APIFOOTBALL_KEY"

# Fallback names let the page render before the API key is configured.
# IDs are filled from get_teams at runtime.
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
    "teams": 21600,       # 6 hours
    "events": 900,        # 15 minutes
    "aggregates": 900,    # 15 minutes
    "standings": 600,     # 10 minutes
    "h2h": 21600,         # 6 hours
}

_cache = {
    "teams": None,
    "events": None,
    "aggregates": None,
    "standings": None,
    "h2h": {},
}


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
        ("SV%", "Save Percentage", "save_percentage", "percent"),
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
        ("AER-W", "Aerial Wins", "aerials_won", "int"),
        ("DUEL-W", "Duels Won", "duels_won", "int"),
    ],
}

# Rank 1 is always generated as "best" by this backend.
LOWER_IS_BETTER = {
    "offsides", "goals_against", "goals_against_per_match",
    "yellow_cards", "red_cards", "fouls", "fouls_per_match",
    "penalties_conceded", "dispossessed",
}


def _slugify(value):
    value = (value or "").strip().lower().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    aliases = {
        "west-ham-united": "west-ham",
        "west-ham": "west-ham",
        "sheffield-united": "sheffield-utd",
        "west-bromwich-albion": "west-brom",
        "queens-park-rangers": "qpr",
        "wolverhampton-wanderers": "wolves",
        "blackburn-rovers": "blackburn",
        "bolton-wanderers": "bolton",
        "bristol-city": "bristol-city",
        "cardiff-city": "cardiff",
        "charlton-athletic": "charlton",
        "derby-county": "derby",
        "lincoln-city": "lincoln",
        "norwich-city": "norwich",
        "preston-north-end": "preston",
        "stoke-city": "stoke",
        "swansea-city": "swansea",
        "watford": "watford",
        "wrexham": "wrexham",
        "birmingham-city": "birmingham",
    }
    return aliases.get(value, value)


def _display_name(name):
    return DISPLAY_NAME_OVERRIDES.get(name, name)


def _cache_get(name):
    entry = _cache.get(name)
    if not entry or name == "h2h":
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
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        raise RuntimeError(
            f"{API_KEY_ENV} is not configured. Add your APIfootball key as an environment variable."
        )
    params = {
        "action": "get_events",
        "from": SEASON_START.isoformat(),
        "to": max(date.today(), SEASON_START).isoformat(),
        "league_id": LEAGUE_ID,
        "withPlayerStats": "1",
        "APIkey": api_key,
    }
    response = requests.get(API_BASE, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(str(data["error"]))
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
    """Last valid duplicate wins (APIfootball occasionally returns duplicate fields)."""
    result = {}
    for row in rows or []:
        stat_type = row.get("type")
        home = _to_number(row.get("home"))
        away = _to_number(row.get("away"))
        if stat_type and home is not None and away is not None:
            result[stat_type] = (home, away)
    return result


def _blank_record():
    fields = [
        "matches", "goals", "goals_against", "clean_sheets",
        "possession_sum", "possession_games", "shots", "shots_on_target",
        "shots_off_target", "shots_blocked", "shots_inside_box", "shots_outside_box",
        "fouls", "corners", "offsides", "saves", "passes", "passes_accurate",
        "tackles", "blocks", "crosses", "crosses_accurate", "interceptions",
        "clearances", "dispossessed", "saves_inside_box", "duels_total", "duels_won",
        "aerials_won", "dribbles_attempted", "dribbles_successful", "penalty_saves",
        "penalties_conceded", "penalties_won", "woodwork", "key_passes", "assists",
        "yellow_cards", "red_cards",
    ]
    return {field: 0.0 for field in fields}


def _add_team_stat(record, stats, stat_type, key, side):
    values = stats.get(stat_type)
    if not values:
        return
    record[key] += values[0 if side == "home" else 1]


def _aggregate_player_stats(record, players, team_side):
    fields = {
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
    for player in players or []:
        if player.get("team_name") != team_side:
            continue
        for source, dest in fields.items():
            number = _to_number(player.get(source))
            if number is not None:
                record[dest] += number


def _safe_div(numerator, denominator, multiplier=1.0):
    if not denominator:
        return 0.0
    return numerator / denominator * multiplier


def _finalize_record(record):
    m = record["matches"]
    record["possession"] = _safe_div(record["possession_sum"], record["possession_games"])
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
    record["save_percentage"] = _safe_div(record["saves"], record["saves"] + record["goals_against"], 100)
    record["fouls_per_match"] = _safe_div(record["fouls"], m)
    record["dribble_success_pct"] = _safe_div(record["dribbles_successful"], record["dribbles_attempted"], 100)
    return record


def build_aggregates():
    cached = _cache_get("aggregates")
    if cached:
        return cached

    teams = fetch_teams()
    id_to_key = {
        str(team["api_id"]): key for key, team in teams.items() if team.get("api_id")
    }
    aggregates = {key: _blank_record() for key in teams}
    events = fetch_season_events()

    for match in events:
        home_id = str(match.get("match_hometeam_id", ""))
        away_id = str(match.get("match_awayteam_id", ""))
        home_key = id_to_key.get(home_id) or _slugify(match.get("match_hometeam_name", ""))
        away_key = id_to_key.get(away_id) or _slugify(match.get("match_awayteam_name", ""))

        if home_key not in aggregates:
            aggregates[home_key] = _blank_record()
        if away_key not in aggregates:
            aggregates[away_key] = _blank_record()

        home = aggregates[home_key]
        away = aggregates[away_key]
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

        stats = _normalized_match_stats(match.get("statistics", []))
        mapping = [
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
        for stat_type, key in mapping:
            _add_team_stat(home, stats, stat_type, key, "home")
            _add_team_stat(away, stats, stat_type, key, "away")

        poss = stats.get("Ball Possession")
        if poss:
            home["possession_sum"] += poss[0]
            away["possession_sum"] += poss[1]
            home["possession_games"] += 1
            away["possession_games"] += 1

        players = match.get("player_statistics", [])
        _aggregate_player_stats(home, players, "home")
        _aggregate_player_stats(away, players, "away")

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
        if record.get("matches", 0) <= 0:
            continue
        value = record.get(metric)
        if value is None:
            continue
        values.append((key, float(value)))

    reverse = metric not in LOWER_IS_BETTER
    values.sort(key=lambda item: item[1], reverse=reverse)

    ranks = {}
    previous_value = None
    previous_rank = 0
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
        return "-"
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
            rank_map = _metric_ranks(aggregates, metric)
            stats.append({
                "abbrev": abbrev,
                "name": name,
                "club": _format_value(record.get(metric, 0), kind),
                "rank": rank_map.get(team_key, "-"),
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

    name1 = teams[team1_key]["name"]
    name2 = teams[team2_key]["name"]
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
            if t1_home:
                hw += 1
            else:
                aw += 1
        elif t1_score < t2_score:
            l += 1
            if t1_home:
                hl += 1
            else:
                al += 1
        else:
            d += 1
            if t1_home:
                hd += 1
            else:
                ad += 1

        raw_date = match.get("match_date", "")
        try:
            date_str = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d %b %Y")
        except Exception:
            date_str = raw_date

        recent.append({
            "home": _display_name(match.get("match_hometeam_name", "")),
            "away": _display_name(match.get("match_awayteam_name", "")),
            "home_score": int(hs),
            "away_score": int(as_),
            "season": match.get("league_year") or match.get("league_name", ""),
            "date": date_str,
        })

    recent.sort(key=lambda m: datetime.strptime(m["date"], "%d %b %Y") if m["date"] else datetime.min, reverse=True)

    return {
        "team1": name1,
        "team2": name2,
        "played": w + d + l,
        "overall": {"w": w, "d": d, "l": l},
        "home": {"w": hw, "d": hd, "l": hl},
        "away": {"w": aw, "d": ad, "l": al},
        "goals_for": goals_for,
        "goals_against": goals_against,
        "recent": recent,
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
    # Keep the existing UI functional without introducing another paid/scraped dependency.
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
        "team1": {
            "name": teams.get(team1_key, {}).get("name", team1_key),
            "starters": [],
            "error": "Predicted lineups are not included in the free APIfootball feed.",
        },
        "team2": {
            "name": teams.get(team2_key, {}).get("name", team2_key),
            "starters": [],
            "error": "Predicted lineups are not included in the free APIfootball feed.",
        },
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
