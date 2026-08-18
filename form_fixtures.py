from flask import Flask, jsonify
from datetime import datetime
import time

import app as core

app = Flask(__name__)

SEASON_END = "2027-05-31"
CACHE_TTL = 900
_cache = {"ts": 0, "data": None}


def _score(match, side):
    for key in (f"match_{side}_ft_score", f"match_{side}_score"):
        value = match.get(key)
        if value not in (None, ""):
            try:
                return int(float(str(value).strip()))
            except (TypeError, ValueError):
                continue
    return None


def _match_datetime(match):
    raw_date = str(match.get("match_date", "")).strip()
    raw_time = str(match.get("match_time", "")).strip()
    for raw, fmt in (
        (f"{raw_date} {raw_time}", "%Y-%m-%d %H:%M"),
        (raw_date, "%Y-%m-%d"),
    ):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except (TypeError, ValueError):
            continue
    return datetime.min


def _is_finished(match):
    status = str(match.get("match_status", "")).strip().lower()
    if status in {"finished", "ft", "after penalties", "aet"}:
        return True
    match_dt = _match_datetime(match)
    if match_dt != datetime.min and match_dt > datetime.now():
        return False
    home = _score(match, "hometeam")
    away = _score(match, "awayteam")
    return home is not None and away is not None and status not in {
        "not started", "scheduled", "postponed", "cancelled", "canceled", "abandoned"
    }


def _team_key(match, side):
    return core._slugify(match.get(f"match_{side}_name", ""))


def _team_name(match, side):
    return core._display_name(match.get(f"match_{side}_name", ""))


def _fixture(match):
    home_score = _score(match, "hometeam")
    away_score = _score(match, "awayteam")
    return {
        "match_id": str(match.get("match_id", "")),
        "home_key": _team_key(match, "hometeam"),
        "away_key": _team_key(match, "awayteam"),
        "home": _team_name(match, "hometeam"),
        "away": _team_name(match, "awayteam"),
        "home_score": home_score,
        "away_score": away_score,
        "date": str(match.get("match_date", "")),
        "time": str(match.get("match_time", "")),
        "status": str(match.get("match_status", "")),
    }


def _result_for(team_key, fixture):
    home = fixture["home_key"] == team_key
    team_score = fixture["home_score"] if home else fixture["away_score"]
    opp_score = fixture["away_score"] if home else fixture["home_score"]
    if team_score is None or opp_score is None:
        return None
    if team_score > opp_score:
        return "W"
    if team_score < opp_score:
        return "L"
    return "D"


def _team_payload(team_key, team_name, completed, upcoming):
    completed_for_team = [
        fixture for fixture in completed
        if fixture["home_key"] == team_key or fixture["away_key"] == team_key
    ]
    upcoming_for_team = [
        fixture for fixture in upcoming
        if fixture["home_key"] == team_key or fixture["away_key"] == team_key
    ]

    recent = completed_for_team[-5:]
    form = []
    for fixture in recent:
        result = _result_for(team_key, fixture)
        if result:
            opponent = fixture["away"] if fixture["home_key"] == team_key else fixture["home"]
            form.append({
                "result": result,
                "opponent": opponent,
                "venue": "Home" if fixture["home_key"] == team_key else "Away",
                "match_id": fixture["match_id"],
            })

    return {
        "name": team_name,
        "form": form,
        "last_match": completed_for_team[-1] if completed_for_team else None,
        "next_match": upcoming_for_team[0] if upcoming_for_team else None,
        "completed_matches": len(completed_for_team),
    }


def _pair_key(team1_key, team2_key):
    keys = sorted(key for key in (team1_key, team2_key) if key)
    return "__".join(keys) if len(keys) == 2 and keys[0] != keys[1] else ""


def build_form_fixtures():
    if _cache["data"] is not None and time.time() - _cache["ts"] < CACHE_TTL:
        return _cache["data"]

    events = core._api_get(
        "get_events",
        **{
            "from": core.SEASON_START.isoformat(),
            "to": SEASON_END,
            "league_id": core.LEAGUE_ID,
            "timezone": "Europe/London",
        },
    )
    events = [event for event in events if isinstance(event, dict)] if isinstance(events, list) else []
    events.sort(key=_match_datetime)

    completed = []
    upcoming = []
    team_names = {
        core._slugify(name): core._display_name(name)
        for name in core.FALLBACK_TEAM_NAMES
    }

    today = datetime.now().date()
    for match in events:
        home_key = _team_key(match, "hometeam")
        away_key = _team_key(match, "awayteam")
        if home_key:
            team_names[home_key] = _team_name(match, "hometeam")
        if away_key:
            team_names[away_key] = _team_name(match, "awayteam")

        fixture = _fixture(match)
        if _is_finished(match):
            completed.append(fixture)
        elif _match_datetime(match) != datetime.min and _match_datetime(match).date() >= today:
            upcoming.append(fixture)

    # The first future fixture for every unordered club pair. This lets Compare
    # show the next league meeting without making another provider request.
    next_meetings = {}
    for fixture in upcoming:
        pair_key = _pair_key(fixture.get("home_key"), fixture.get("away_key"))
        if pair_key and pair_key not in next_meetings:
            next_meetings[pair_key] = fixture

    payload = {
        "success": True,
        "league": "Championship",
        "season": "2026-27",
        "teams": {
            key: _team_payload(key, name, completed, upcoming)
            for key, name in sorted(team_names.items(), key=lambda item: item[1])
        },
        "next_meetings": next_meetings,
    }
    _cache.update({"ts": time.time(), "data": payload})
    return payload


@app.route("/api/form-fixtures")
def form_fixtures():
    try:
        return jsonify(build_form_fixtures())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503
