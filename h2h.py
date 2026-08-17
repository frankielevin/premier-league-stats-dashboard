from flask import Flask, jsonify, request
import os
import re
import time
from datetime import datetime

import requests

app = Flask(__name__)

# Dedicated, cacheable last-five head-to-head endpoint for Compare mode.
API_BASE = "https://apiv3.apifootball.com/"
LEAGUE_ID = "153"
API_KEY_ENV = "APIFOOTBALL_KEY"

_teams_cache = {"ts": 0, "data": {}}
_h2h_cache = {}

DISPLAY_NAME_OVERRIDES = {
    "West Ham": "West Ham United",
    "West Ham United": "West Ham United",
    "Sheffield Utd": "Sheffield United",
    "West Brom": "West Bromwich Albion",
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
        "cardiff-city": "cardiff",
        "charlton-athletic": "charlton",
        "derby-county": "derby",
        "lincoln-city": "lincoln",
        "norwich-city": "norwich",
        "preston-north-end": "preston",
        "stoke-city": "stoke",
        "swansea-city": "swansea",
        "west-bromwich": "west-brom",
        "birmingham-city": "birmingham",
    }
    return aliases.get(value, value)


def _display_name(name):
    return DISPLAY_NAME_OVERRIDES.get(name, name)


def _api_get(action, **params):
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        raise RuntimeError(f"{API_KEY_ENV} is not configured.")
    query = {"action": action, "APIkey": api_key}
    query.update({k: v for k, v in params.items() if v is not None})
    response = requests.get(API_BASE, params=query, timeout=30)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(str(data["error"]))
    return data


def _fetch_teams():
    if _teams_cache["data"] and time.time() - _teams_cache["ts"] < 21600:
        return _teams_cache["data"]
    data = _api_get("get_teams", league_id=LEAGUE_ID)
    teams = {}
    for item in data if isinstance(data, list) else []:
        name = item.get("team_name", "")
        team_id = str(item.get("team_key", ""))
        if name and team_id:
            teams[_slugify(name)] = {
                "id": team_id,
                "api_name": name,
                "name": _display_name(name),
            }
    _teams_cache.update({"ts": time.time(), "data": teams})
    return teams


def _extract_h2h_matches(payload):
    # V3 documents a dict response. Older responses can be wrapped in a list.
    if isinstance(payload, list):
        payload = next((x for x in payload if isinstance(x, dict)), {})
    if not isinstance(payload, dict):
        return []
    matches = payload.get("firstTeam_VS_secondTeam", [])
    return matches if isinstance(matches, list) else []


def _is_finished(match):
    status = str(match.get("match_status", "")).strip().lower()
    if status in {"finished", "ft", "aet", "after penalties"}:
        return True
    home = match.get("match_hometeam_score")
    away = match.get("match_awayteam_score")
    return home not in (None, "") and away not in (None, "")


def _score(match, side):
    for key in (f"match_{side}_ft_score", f"match_{side}_score"):
        value = match.get(key)
        if value not in (None, ""):
            try:
                return int(float(str(value).strip()))
            except (TypeError, ValueError):
                continue
    return None


def _date_value(match):
    raw = str(match.get("match_date", ""))
    try:
        return datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return datetime.min


def _format_date(raw):
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%d %b %Y")
    except (TypeError, ValueError):
        return raw or ""


def _load_h2h(team1, team2):
    cache_key = "-".join(sorted((team1["id"], team2["id"])))
    cached = _h2h_cache.get(cache_key)
    if cached and time.time() - cached["ts"] < 21600:
        return cached["data"]

    payload = _api_get(
        "get_H2H",
        firstTeamId=team1["id"],
        secondTeamId=team2["id"],
    )
    matches = _extract_h2h_matches(payload)

    # Some historical records are more reliable when queried by team name.
    if not matches:
        payload = _api_get(
            "get_H2H",
            firstTeam=team1["api_name"],
            secondTeam=team2["api_name"],
        )
        matches = _extract_h2h_matches(payload)

    # De-duplicate in case the provider repeats a fixture.
    unique = {}
    for match in matches:
        if not isinstance(match, dict):
            continue
        match_id = str(match.get("match_id", ""))
        key = match_id or (
            str(match.get("match_date", "")),
            str(match.get("match_hometeam_id", "")),
            str(match.get("match_awayteam_id", "")),
        )
        unique[key] = match

    matches = list(unique.values())
    _h2h_cache[cache_key] = {"ts": time.time(), "data": matches}
    return matches


@app.route("/api/h2h")
def h2h():
    team1_key = request.args.get("team1", "west-ham")
    team2_key = request.args.get("team2", "burnley")

    if team1_key == team2_key:
        return jsonify({"error": "Please select two different teams."}), 400

    try:
        teams = _fetch_teams()
        team1 = teams.get(team1_key)
        team2 = teams.get(team2_key)
        if not team1 or not team2:
            return jsonify({"error": "One or both teams could not be found."}), 404

        matches = [m for m in _load_h2h(team1, team2) if _is_finished(m)]
        matches.sort(key=_date_value, reverse=True)
        matches = matches[:5]

        w = d = l = 0
        goals_for = goals_against = 0
        parsed = []

        for match in matches:
            hs = _score(match, "hometeam")
            aws = _score(match, "awayteam")
            if hs is None or aws is None:
                continue

            home_id = str(match.get("match_hometeam_id", ""))
            away_id = str(match.get("match_awayteam_id", ""))
            team1_home = home_id == team1["id"]
            if not team1_home and away_id != team1["id"]:
                continue

            t1_score, t2_score = (hs, aws) if team1_home else (aws, hs)
            goals_for += t1_score
            goals_against += t2_score
            if t1_score > t2_score:
                w += 1
            elif t1_score < t2_score:
                l += 1
            else:
                d += 1

            parsed.append({
                "match_id": str(match.get("match_id", "")),
                "home": _display_name(match.get("match_hometeam_name", "")),
                "away": _display_name(match.get("match_awayteam_name", "")),
                "home_score": hs,
                "away_score": aws,
                "date": _format_date(match.get("match_date", "")),
                "league": match.get("league_name", ""),
                "season": match.get("league_year") or match.get("league_name", ""),
            })

        return jsonify({
            "team1": team1["name"],
            "team2": team2["name"],
            "played": len(parsed),
            "overall": {"w": w, "d": d, "l": l},
            "goals_for": goals_for,
            "goals_against": goals_against,
            "recent": parsed,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503


if __name__ == "__main__":
    app.run(debug=True, port=5001)
