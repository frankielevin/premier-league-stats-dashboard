from flask import Flask, jsonify
import time

import app as core

app = Flask(__name__)

CACHE_TTL = 300
_cache = {"ts": 0, "data": None}


def _int(value):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _split(row, prefix):
    gf = _int(row.get(f"{prefix}_league_GF"))
    ga = _int(row.get(f"{prefix}_league_GA"))
    return {
        "position": _int(row.get(f"{prefix}_league_position")),
        "played": _int(row.get(f"{prefix}_league_payed")),
        "won": _int(row.get(f"{prefix}_league_W")),
        "drawn": _int(row.get(f"{prefix}_league_D")),
        "lost": _int(row.get(f"{prefix}_league_L")),
        "gf": gf,
        "ga": ga,
        "gd": gf - ga,
        "points": _int(row.get(f"{prefix}_league_PTS")),
        "promotion": str(row.get(f"{prefix}_promotion", "") or ""),
    }


def build_standings():
    if _cache["data"] is not None and time.time() - _cache["ts"] < CACHE_TTL:
        return _cache["data"]

    data = core._api_get("get_standings", league_id=core.LEAGUE_ID)
    result = {}

    for row in data if isinstance(data, list) else []:
        if not isinstance(row, dict):
            continue
        api_name = str(row.get("team_name", "") or "").strip()
        if not api_name:
            continue

        team_key = core._slugify(api_name)
        overall = _split(row, "overall")
        home = _split(row, "home")
        away = _split(row, "away")

        result[team_key] = {
            # Keep these top-level fields for the existing Overview feature.
            "position": overall["position"],
            "points": overall["points"],
            "played": overall["played"],
            "team": core._display_name(api_name),
            "badge": str(row.get("team_badge", "") or ""),
            "overall": overall,
            "home": home,
            "away": away,
        }

    _cache.update({"ts": time.time(), "data": result})
    return result


@app.route("/api/standings")
def standings():
    try:
        return jsonify(build_standings())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503
