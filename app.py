from flask import Flask, render_template, jsonify, request
import requests
from bs4 import BeautifulSoup
import time
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

PL_API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://www.premierleague.com",
    "Referer": "https://www.premierleague.com/",
}

# In-memory H2H cache — keyed by sorted team ID pair, TTL 4 hours
_h2h_cache = {}


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
        "recent":        recent_matches[-6:][::-1],
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
