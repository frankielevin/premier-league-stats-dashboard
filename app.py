from flask import Flask, render_template, jsonify, request
import requests
from bs4 import BeautifulSoup
import time
import re
import json
from datetime import datetime

app = Flask(__name__)

# All Premier League teams with their StatMuse slugs
TEAMS = {
    "arsenal": {"name": "Arsenal", "slug": "arsenal-6"},
    "aston-villa": {"name": "Aston Villa", "slug": "aston-villa-8"},
    "bournemouth": {"name": "AFC Bournemouth", "slug": "afc-bournemouth-18"},
    "brentford": {"name": "Brentford", "slug": "brentford-21"},
    "brighton": {"name": "Brighton & Hove Albion", "slug": "brighton-&-hove-albion-22"},
    "burnley": {"name": "Burnley", "slug": "burnley-25"},
    "chelsea": {"name": "Chelsea", "slug": "chelsea-34"},
    "crystal-palace": {"name": "Crystal Palace", "slug": "crystal-palace-42"},
    "everton": {"name": "Everton", "slug": "everton-49"},
    "fulham": {"name": "Fulham", "slug": "fulham-53"},
    "leeds": {"name": "Leeds United", "slug": "leeds-united-68"},
    "liverpool": {"name": "Liverpool", "slug": "liverpool-72"},
    "man-city": {"name": "Manchester City", "slug": "manchester-city-77"},
    "man-united": {"name": "Manchester United", "slug": "manchester-united-78"},
    "newcastle": {"name": "Newcastle United", "slug": "newcastle-united-89"},
    "nottingham-forest": {"name": "Nottingham Forest", "slug": "nottingham-forest-94"},
    "sunderland": {"name": "Sunderland", "slug": "sunderland-122"},
    "tottenham": {"name": "Tottenham Hotspur", "slug": "tottenham-hotspur-128"},
    "west-ham": {"name": "West Ham United", "slug": "west-ham-united-133"},
    "wolves": {"name": "Wolverhampton Wanderers", "slug": "wolverhampton-wanderers-136"},
}

STAT_CATEGORIES = {
    "attacking": "",
    "passing": "?statCategory=passing",
    "defending": "?statCategory=defending",
    "goalkeeping": "?statCategory=goalkeeping",
    "miscellaneous": "?statCategory=miscellaneous"
}

STAT_NAMES = {
    "M": "Matches", "G": "Goals", "G/M": "Goals per Match", "A": "Assists",
    "xG": "Expected Goals", "xA": "Expected Assists", "POSS%": "Possession %",
    "PK": "Penalties", "FK": "Free Kicks", "SH": "Shots", "SOT": "Shots on Target",
    "TCH": "Touches", "TCH-BOX": "Touches in Box", "OFF": "Offsides",
    "PASS": "Passes", "PASS/M": "Passes per Match", "PASS%": "Pass Completion %",
    "PASS-ATT": "Pass Attempts", "BCC": "Big Chances Created", "PASS-KEY": "Key Passes",
    "PASS-LNG": "Long Passes", "PASS-F3RD": "Passes into Final Third",
    "THRU-BALL": "Through Balls", "CRS": "Crosses", "CNR": "Corner Kicks",
    "xGA": "Expected Goals Against", "TKL": "Tackles", "TKL-W": "Tackles Won",
    "TKL-LM": "Tackles Lost/Missed", "SH-BLK": "Shots Blocked", "BLK-CRS": "Blocked Crosses",
    "INT": "Interceptions", "CLR": "Clearances", "REC": "Recoveries",
    "ERR-SH": "Errors Leading to Shots", "ERR-G": "Errors Leading to Goals",
    "PKC": "Penalties Conceded", "OG": "Own Goals", "GC": "Goals Conceded",
    "GC/M": "Goals Conceded per Match", "SV": "Saves", "SV-PK": "Penalty Saves",
    "CS": "Clean Sheets", "YC": "Yellow Cards", "RC": "Red Cards", "FOUL": "Fouls",
    "FOULED": "Fouled", "PK-W": "Penalties Won", "CNR-W": "Corners Won",
    "AER-W": "Aerial Wins", "AER-L": "Aerial Losses", "DUEL-W": "Duels Won",
    "DUEL-L": "Duels Lost", "POSS-L": "Possession Lost"
}


# Official Premier League API team IDs (footballapi.pulselive.com)
PL_TEAM_IDS = {
    "arsenal":           1,
    "aston-villa":       2,
    "bournemouth":       127,
    "brentford":         130,
    "brighton":          131,
    "burnley":           43,
    "chelsea":           4,
    "crystal-palace":    6,
    "everton":           7,
    "fulham":            34,
    "leeds":             9,
    "liverpool":         10,
    "man-city":          11,
    "man-united":        12,
    "newcastle":         23,
    "nottingham-forest": 15,
    "sunderland":        29,
    "tottenham":         21,
    "west-ham":          25,
    "wolves":            38,
}

# FotMob team IDs (stable across seasons for existing clubs)
FOTMOB_TEAM_IDS = {
    "arsenal":           9825,
    "aston-villa":       10252,
    "bournemouth":       8678,
    "brentford":         9937,
    "brighton":          10204,
    "burnley":           8191,
    "chelsea":           8455,
    "crystal-palace":    9826,
    "everton":           8668,
    "fulham":            9879,
    "leeds":             8463,
    "liverpool":         8650,
    "man-city":          8456,
    "man-united":        10260,
    "newcastle":         10261,
    "nottingham-forest": 10203,
    "sunderland":        8472,
    "tottenham":         8586,
    "west-ham":          8654,
    "wolves":            8602,
}

FOTMOB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

PL_API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://www.premierleague.com",
    "Referer": "https://www.premierleague.com/",
}

# In-memory H2H cache — keyed by sorted team ID pair, TTL 4 hours
_h2h_cache = {}

# In-memory standings cache — TTL 6 hours
_standings_cache = {}

# In-memory FotMob lineup cache — TTL 2 hours per team
_fotmob_cache = {}


def fetch_standings():
    """Fetch current PL standings. Returns dict keyed by app team key."""
    if _standings_cache:
        cached = next(iter(_standings_cache.values()))
        if time.time() - cached["ts"] < 21600:
            return cached["data"]

    # Discover current season ID from the latest fixture
    season_id = 777  # 2025/26 fallback
    try:
        r = requests.get(
            "https://footballapi.pulselive.com/football/fixtures?pageSize=1&comps=1&sort=desc",
            headers=PL_API_HEADERS, timeout=8
        )
        r.raise_for_status()
        fixtures = r.json().get("content", [])
        if fixtures:
            season_id = int(fixtures[0]["gameweek"]["compSeason"]["id"])
    except Exception:
        pass

    try:
        r = requests.get(
            f"https://footballapi.pulselive.com/football/standings?compSeasons={season_id}&pageSize=20&comps=1",
            headers=PL_API_HEADERS, timeout=8
        )
        r.raise_for_status()
        entries = r.json()["tables"][0]["entries"]
    except Exception as e:
        return {"error": str(e)}

    # Build reverse lookup: PL team ID → app team key
    id_to_key = {v: k for k, v in PL_TEAM_IDS.items()}

    result = {}
    for e in entries:
        pl_id = e["team"]["id"]
        key = id_to_key.get(pl_id)
        if key:
            result[key] = {
                "position": e["position"],
                "points":   e["overall"]["points"],
                "played":   e["overall"]["played"],
            }

    _standings_cache["data"] = {"data": result, "ts": time.time()}
    return result

def fetch_fotmob_lineup(team_key):
    """
    Fetch the predicted/confirmed lineup for a team's next match from FotMob.
    Scrapes the FotMob team overview page to find nextMatch, then fetches
    the match page __NEXT_DATA__ for lineup coordinates.
    Cached per team for 2 hours.
    """
    if team_key in _fotmob_cache:
        cached = _fotmob_cache[team_key]
        if time.time() - cached["ts"] < 7200:
            return cached["data"]

    fotmob_id = FOTMOB_TEAM_IDS.get(team_key)
    if not fotmob_id:
        return {"error": "Team not available on FotMob"}

    try:
        # ── Step 1: get the team's next match URL ──────────────────────────
        team_url = f"https://www.fotmob.com/teams/{fotmob_id}/overview"
        r = requests.get(team_url, headers=FOTMOB_HEADERS, timeout=15)
        r.raise_for_status()

        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        if not m:
            return {"error": "Could not parse FotMob team page"}

        team_page = json.loads(m.group(1))
        fallback   = team_page["props"]["pageProps"].get("fallback", {})
        team_info  = fallback.get(f"team-{fotmob_id}", {})
        next_match = team_info.get("fixtures", {}).get("allFixtures", {}).get("nextMatch")

        if not next_match or not next_match.get("pageUrl"):
            return {"error": "No upcoming match found for this team"}

        page_url = next_match["pageUrl"]   # e.g. /matches/…/2u9b5i#4813659
        match_id = next_match["id"]
        opponent_name = next_match.get("opponent", {}).get("name", "")
        home_side = next_match.get("home", {})
        away_side = next_match.get("away", {})
        kickoff   = next_match.get("status", {}).get("utcTime", "")
        is_home   = home_side.get("id") == fotmob_id

        # ── Step 2: fetch the match page for lineup data ───────────────────
        match_url = f"https://www.fotmob.com/en-GB{page_url}"
        r2 = requests.get(match_url, headers=FOTMOB_HEADERS, timeout=15)
        r2.raise_for_status()

        m2 = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r2.text, re.DOTALL)
        if not m2:
            return {"error": "Could not parse FotMob match page"}

        match_page   = json.loads(m2.group(1))
        lineup_block = match_page["props"]["pageProps"]["content"].get("lineup", {})
        lineup_type  = lineup_block.get("lineupType", "")   # 'predicted' or 'lineup' (confirmed)

        # Find the correct side for this team
        home_data = lineup_block.get("homeTeam", {})
        away_data = lineup_block.get("awayTeam", {})
        team_side = home_data if home_data.get("id") == fotmob_id else away_data

        starters = []
        for p in team_side.get("starters", []):
            hl = p.get("horizontalLayout", {})
            starters.append({
                "name":  p.get("name", ""),
                "shirt": str(p.get("shirtNumber", "")),
                "x":     float(hl.get("x", 0.5)),
                "y":     float(hl.get("y", 0.5)),
            })

        unavailable = []
        for p in team_side.get("unavailable", []):
            u = p.get("unavailability", {})
            unavailable.append({
                "name":   p.get("name", ""),
                "type":   u.get("type", "injury"),
                "return": u.get("expectedReturn", "Unknown"),
            })

        result = {
            "name":        team_side.get("name", TEAMS[team_key]["name"]),
            "formation":   team_side.get("formation", ""),
            "lineupType":  lineup_type,
            "starters":    starters,
            "unavailable": unavailable,
            "nextMatch": {
                "matchId":   match_id,
                "pageUrl":   page_url,
                "opponent":  opponent_name,
                "kickoff":   kickoff,
                "isHome":    is_home,
            },
        }

    except Exception as e:
        return {"error": str(e)}

    _fotmob_cache[team_key] = {"data": result, "ts": time.time()}
    return result


# knocksandbans.com slugs for team news scraping
KNOCKSANDBANS_SLUGS = {
    "arsenal":           "arsenal",
    "aston-villa":       "aston-villa",
    "bournemouth":       "bournemouth",
    "brentford":         "brentford",
    "brighton":          "brighton-hove-albion",
    "burnley":           "burnley",
    "chelsea":           "chelsea",
    "crystal-palace":    "crystal-palace",
    "everton":           "everton",
    "fulham":            "fulham",
    "leeds":             "leeds-united",
    "liverpool":         "liverpool",
    "man-city":          "manchester-city",
    "man-united":        "manchester-united",
    "newcastle":         "newcastle-united",
    "nottingham-forest": "nottingham-forest",
    "sunderland":        "sunderland",
    "tottenham":         "tottenham-hotspur",
    "west-ham":          "west-ham-united",
    "wolves":            "wolverhampton-wanderers",
}

KNOCKSANDBANS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.knocksandbans.com/",
}

# In-memory team-news cache — keyed by team key, TTL 1 hour
_news_cache = {}


def parse_team_news(html):
    """Parse injury/suspension data from knocksandbans.com team page."""
    soup = BeautifulSoup(html, "html.parser")
    players = []

    for a in soup.find_all("a", href=True):
        text = a.get_text(separator=" ", strip=True)
        if "Status:" not in text:
            continue

        strong = a.find("strong")
        if not strong:
            continue
        name = strong.get_text(strip=True)

        # Detect suspension by icon filename
        imgs = a.find_all("img")
        is_suspension = any("schorsing" in img.get("src", "") for img in imgs)

        # Extract raw status (e.g. "OUT", "OUT (ban)", "75%", "50%", "25%")
        raw_status = ""
        status_match = re.search(r"Status:\s*([^\s].*?)(?:\s+Est\.|\s*$)", text)
        if status_match:
            raw_status = status_match.group(1).strip()

        # Map to display label
        if "ban" in raw_status.lower() or is_suspension:
            status_label = "Suspended"
            status_type  = "suspended"
        elif "OUT" in raw_status.upper():
            status_label = "OUT"
            status_type  = "out"
        else:
            pct_match = re.search(r"(\d+)%", raw_status)
            pct = int(pct_match.group(1)) if pct_match else 50
            if pct >= 75:
                status_label = "Slight Doubt"
            elif pct >= 50:
                status_label = "Doubtful"
            else:
                status_label = "Unlikely"
            status_type = "doubtful"

        # Extract reason (text between "- " and "Status:")
        reason = ""
        reason_match = re.search(r"-\s+(.+?)\s+Status:", text)
        if reason_match:
            reason = reason_match.group(1).strip().title()
        if is_suspension or "ban" in raw_status.lower():
            reason = "Suspension"

        # Extract return date
        return_date = "Unknown"
        return_match = re.search(r"Est\.\s*Return\s+(.+)", text)
        if return_match:
            raw_date = return_match.group(1).strip()
            # Reformat DD/MM/YY → DD Mon YYYY
            try:
                dt = datetime.strptime(raw_date, "%d/%m/%y")
                return_date = dt.strftime("%-d %b %Y")
            except Exception:
                return_date = raw_date if raw_date else "Unknown"

        players.append({
            "name":   name,
            "status": status_label,
            "type":   status_type,
            "reason": reason,
            "return": return_date,
        })

    return players


def fetch_team_news(team_key):
    """Fetch injury/suspension list for a team from knocksandbans.com."""
    slug = KNOCKSANDBANS_SLUGS.get(team_key)
    if not slug:
        return {"team": TEAMS.get(team_key, {}).get("name", team_key), "players": [], "error": "No data available."}

    # Return cached data if still fresh (1 hour TTL)
    if team_key in _news_cache:
        cached = _news_cache[team_key]
        if time.time() - cached["ts"] < 3600:
            return cached["data"]

    url = f"https://www.knocksandbans.com/{slug}"
    try:
        resp = requests.get(url, headers=KNOCKSANDBANS_HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return {"team": TEAMS[team_key]["name"], "players": [], "error": f"Could not fetch team news: {str(e)}"}

    players = parse_team_news(resp.text)
    data = {"team": TEAMS[team_key]["name"], "players": players}
    _news_cache[team_key] = {"data": data, "ts": time.time()}
    return data


def fetch_h2h_data(team1_key, team2_key):
    """Fetch all-time Premier League H2H record between two teams."""
    pl_id1 = PL_TEAM_IDS.get(team1_key)
    pl_id2 = PL_TEAM_IDS.get(team2_key)

    if not pl_id1 or not pl_id2:
        return {"error": "Head-to-head data not available for one or both of these teams."}

    # Order-independent cache key
    cache_key = f"{min(pl_id1, pl_id2)}-{max(pl_id1, pl_id2)}"

    # Return cached raw fixtures if still fresh
    if cache_key in _h2h_cache:
        cached = _h2h_cache[cache_key]
        if time.time() - cached["ts"] < 14400:
            h2h_fixtures = cached["fixtures"]
        else:
            h2h_fixtures = None
    else:
        h2h_fixtures = None

    # Fetch from PL API if not cached
    if h2h_fixtures is None:
        all_fixtures = []
        page = 0
        base = "https://footballapi.pulselive.com/football/fixtures"

        while True:
            url = f"{base}?teams={pl_id1}&pageSize=100&sort=asc&comps=1&page={page}"
            try:
                resp = requests.get(url, headers=PL_API_HEADERS, timeout=10)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                if not all_fixtures:
                    return {"error": f"Could not reach the Premier League data source: {str(e)}"}
                break

            content = data.get("content", [])
            if not content:
                break

            all_fixtures.extend(content)

            page_info = data.get("pageInfo", {})
            if page >= page_info.get("numPages", 1) - 1:
                break

            page += 1

        # Keep only completed H2H fixtures
        h2h_fixtures = []
        for fix in all_fixtures:
            teams = fix.get("teams", [])
            if len(teams) != 2:
                continue
            team_ids = [t["team"]["id"] for t in teams]
            if pl_id2 not in team_ids:
                continue
            if teams[0].get("score") is None or teams[1].get("score") is None:
                continue
            h2h_fixtures.append(fix)

        h2h_fixtures.sort(key=lambda f: f.get("kickoff", {}).get("millis", 0))
        _h2h_cache[cache_key] = {"fixtures": h2h_fixtures, "ts": time.time()}

    # Compute stats from team1's perspective
    w = d = l = hw = hd = hl = aw = ad = al = 0
    goals_for = goals_against = 0
    recent_matches = []

    for fix in h2h_fixtures:
        td = fix["teams"]
        home_id    = td[0]["team"]["id"]
        home_score = int(td[0]["score"])
        away_score = int(td[1]["score"])

        t1_home  = (home_id == pl_id1)
        t1_score = home_score if t1_home else away_score
        t2_score = away_score if t1_home else home_score

        goals_for      += t1_score
        goals_against  += t2_score

        if t1_score > t2_score:
            w += 1
            if t1_home: hw += 1
            else:        aw += 1
        elif t1_score < t2_score:
            l += 1
            if t1_home: hl += 1
            else:        al += 1
        else:
            d += 1
            if t1_home: hd += 1
            else:        ad += 1

        # Format date
        millis = fix.get("kickoff", {}).get("millis", 0)
        try:
            date_str = datetime.fromtimestamp(millis / 1000).strftime("%d %b %Y") if millis else ""
        except Exception:
            date_str = fix.get("kickoff", {}).get("label", "")

        recent_matches.append({
            "home":       td[0]["team"]["name"],
            "away":       td[1]["team"]["name"],
            "home_score": home_score,
            "away_score": away_score,
            "season":     fix.get("gameweek", {}).get("compSeason", {}).get("label", ""),
            "date":       date_str,
        })

    return {
        "team1":         TEAMS[team1_key]["name"],
        "team2":         TEAMS[team2_key]["name"],
        "played":        w + d + l,
        "overall":       {"w": w,  "d": d,  "l": l},
        "home":          {"w": hw, "d": hd, "l": hl},
        "away":          {"w": aw, "d": ad, "l": al},
        "goals_for":     goals_for,
        "goals_against": goals_against,
        "recent":        recent_matches[::-1],
    }


def get_base_url(team_key):
    """Get the base stats URL for a team."""
    team = TEAMS.get(team_key, TEAMS["west-ham"])
    return f"https://www.statmuse.com/fc/club/{team['slug']}/stats/2026"


def fetch_page(url):
    """Fetch page content with proper headers."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.text


def parse_club_stats(html):
    """
    Parse club stats from HTML.
    The table structure is:
    - Row 1: Empty cell + stat abbreviations as headers
    - Row 2: "Club" label + values
    - Row 3: "Club Rank" label + rank values
    """
    soup = BeautifulSoup(html, 'html.parser')
    stats = []

    # Find all tables and look for the one with Club Stats
    tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')
        if len(rows) < 3:
            continue

        # Get cells from each row
        header_cells = rows[0].find_all(['td', 'th'])
        value_cells = rows[1].find_all(['td', 'th'])
        rank_cells = rows[2].find_all(['td', 'th'])

        # Extract text from cells
        headers = [c.get_text(strip=True) for c in header_cells]
        values = [c.get_text(strip=True) for c in value_cells]
        ranks = [c.get_text(strip=True) for c in rank_cells]

        # Check if this is the Club Stats table
        # Row 2 should start with "Club" and Row 3 should start with "Club Rank"
        if len(values) > 0 and values[0] == 'Club' and len(ranks) > 0 and ranks[0] == 'Club Rank':
            # Parse the stats - skip the first column (row label)
            for i in range(1, len(headers)):
                abbrev = headers[i] if i < len(headers) else ""
                value = values[i] if i < len(values) else "-"
                rank = ranks[i] if i < len(ranks) else "-"

                # Clean up empty ranks
                if not rank or rank == '':
                    rank = "-"

                if abbrev:  # Only add if we have an abbreviation
                    stats.append({
                        "abbrev": abbrev,
                        "name": STAT_NAMES.get(abbrev, abbrev),
                        "club": value,
                        "rank": rank
                    })

            break  # Found the Club Stats table, no need to continue

    return stats


def scrape_category(team_key, category):
    """Scrape a single category of stats for a team."""
    base_url = get_base_url(team_key)
    url = base_url + STAT_CATEGORIES.get(category, "")
    try:
        html = fetch_page(url)
        stats = parse_club_stats(html)
        return {"success": True, "stats": stats, "category": category}
    except Exception as e:
        return {"success": False, "error": str(e), "category": category, "stats": []}


def scrape_all(team_key):
    """Scrape all categories for a team."""
    results = {}
    for category in STAT_CATEGORIES.keys():
        results[category] = scrape_category(team_key, category)
    return results


@app.route('/')
def index():
    """Main page."""
    return render_template('index.html', teams=TEAMS)


@app.route('/api/teams')
def get_teams():
    """API endpoint to get all teams."""
    return jsonify(TEAMS)


@app.route('/api/stats')
def get_all_stats():
    """API endpoint to get all stats for a team."""
    team_key = request.args.get('team', 'west-ham')
    if team_key not in TEAMS:
        team_key = 'west-ham'

    team_info = TEAMS[team_key]
    result = scrape_all(team_key)
    result['team'] = {
        'key': team_key,
        'name': team_info['name']
    }
    return jsonify(result)


@app.route('/api/stats/<category>')
def get_category_stats(category):
    """API endpoint to get stats for a specific category."""
    team_key = request.args.get('team', 'west-ham')
    if team_key not in TEAMS:
        team_key = 'west-ham'

    if category not in STAT_CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400

    return jsonify(scrape_category(team_key, category))


@app.route('/api/h2h')
def get_h2h():
    """API endpoint to get all-time Premier League H2H record between two teams."""
    team1_key = request.args.get('team1', 'west-ham')
    team2_key = request.args.get('team2', 'arsenal')

    if team1_key not in TEAMS:
        team1_key = 'west-ham'
    if team2_key not in TEAMS:
        team2_key = 'arsenal'

    if team1_key == team2_key:
        return jsonify({"error": "Please select two different teams."}), 400

    return jsonify(fetch_h2h_data(team1_key, team2_key))


@app.route('/api/standings')
def get_standings():
    """API endpoint to get current PL standings for all teams."""
    return jsonify(fetch_standings())


@app.route('/api/team-news')
def get_team_news():
    """API endpoint to get injury/suspension news for both teams."""
    team1_key = request.args.get('team1', 'west-ham')
    team2_key = request.args.get('team2', 'arsenal')

    if team1_key not in TEAMS:
        team1_key = 'west-ham'
    if team2_key not in TEAMS:
        team2_key = 'arsenal'

    return jsonify({
        'team1': fetch_team_news(team1_key),
        'team2': fetch_team_news(team2_key),
    })


@app.route('/api/predicted-lineups')
def get_predicted_lineups():
    """API endpoint to get FotMob predicted/confirmed lineups for both teams."""
    team1_key = request.args.get('team1', 'west-ham')
    team2_key = request.args.get('team2', 'arsenal')

    if team1_key not in TEAMS:
        team1_key = 'west-ham'
    if team2_key not in TEAMS:
        team2_key = 'arsenal'

    lineup1 = fetch_fotmob_lineup(team1_key)
    lineup2 = fetch_fotmob_lineup(team2_key)

    # Flag if both teams are playing each other (same matchId)
    m1 = lineup1.get("nextMatch", {}).get("matchId")
    m2 = lineup2.get("nextMatch", {}).get("matchId")

    return jsonify({
        'team1':      lineup1,
        'team2':      lineup2,
        'sameMatch':  bool(m1 and m2 and m1 == m2),
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
