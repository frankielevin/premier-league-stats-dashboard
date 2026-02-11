import requests
from bs4 import BeautifulSoup
import json

BASE_URL = "https://www.statmuse.com/fc/club/west-ham-united-133/stats/2026"

STAT_CATEGORIES = {
    "attacking": "",
    "passing": "?statCategory=passing",
    "defending": "?statCategory=defending",
    "goalkeeping": "?statCategory=goalkeeping",
    "miscellaneous": "?statCategory=miscellaneous"
}

# Full names for stat abbreviations
STAT_NAMES = {
    # Attacking
    "M": "Matches",
    "G": "Goals",
    "G/M": "Goals per Match",
    "A": "Assists",
    "xG": "Expected Goals",
    "xA": "Expected Assists",
    "POSS%": "Possession %",
    "PK": "Penalties",
    "FK": "Free Kicks",
    "SH": "Shots",
    "SOT": "Shots on Target",
    "TCH": "Touches",
    "TCH-BOX": "Touches in Box",
    "OFF": "Offsides",
    # Passing
    "PASS": "Passes",
    "PASS/M": "Passes per Match",
    "PASS%": "Pass Completion %",
    "PASS-ATT": "Pass Attempts",
    "BCC": "Big Chances Created",
    "PASS-KEY": "Key Passes",
    "PASS-LNG": "Long Passes",
    "PASS-F3RD": "Passes into Final Third",
    "THRU-BALL": "Through Balls",
    "CRS": "Crosses",
    "CNR": "Corner Kicks",
    # Defending
    "xGA": "Expected Goals Against",
    "TKL": "Tackles",
    "TKL-W": "Tackles Won",
    "TKL-LM": "Tackles Lost/Missed",
    "SH-BLK": "Shots Blocked",
    "BLK-CRS": "Blocked Crosses",
    "INT": "Interceptions",
    "CLR": "Clearances",
    "REC": "Recoveries",
    "ERR-SH": "Errors Leading to Shots",
    "ERR-G": "Errors Leading to Goals",
    "PKC": "Penalties Conceded",
    "OG": "Own Goals",
    # Goalkeeping
    "GC": "Goals Conceded",
    "GC/M": "Goals Conceded per Match",
    "SV": "Saves",
    "SV-PK": "Penalty Saves",
    "CS": "Clean Sheets",
    # Miscellaneous
    "YC": "Yellow Cards",
    "RC": "Red Cards",
    "FOUL": "Fouls",
    "FOULED": "Fouled",
    "PK-W": "Penalties Won",
    "CNR-W": "Corners Won",
    "AER-W": "Aerial Wins",
    "AER-L": "Aerial Losses",
    "DUEL-W": "Duels Won",
    "DUEL-L": "Duels Lost",
    "POSS-L": "Possession Lost"
}


def scrape_stats(category="attacking"):
    """Scrape stats for a given category."""
    url = BASE_URL + STAT_CATEGORIES.get(category, "")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching {category}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')

    stats = []

    # Find the Club Stats table - look for table with stat data
    # The table structure typically has rows with stat abbreviation, club value, and club rank

    # Try to find tables on the page
    tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                # Try to extract stat data from cells
                cell_texts = [cell.get_text(strip=True) for cell in cells]

                # Look for rows that have a stat abbreviation we recognize
                if cell_texts and cell_texts[0] in STAT_NAMES:
                    stat_entry = {
                        "abbrev": cell_texts[0],
                        "name": STAT_NAMES.get(cell_texts[0], cell_texts[0]),
                        "club": cell_texts[1] if len(cell_texts) > 1 else "",
                        "rank": cell_texts[2] if len(cell_texts) > 2 else ""
                    }
                    stats.append(stat_entry)

    # If table parsing didn't work, try alternative parsing
    if not stats:
        stats = parse_stats_alternative(soup, category)

    return stats


def parse_stats_alternative(soup, category):
    """Alternative parsing method using different selectors."""
    stats = []

    # Look for divs or spans that might contain stat data
    # StatMuse often uses specific class names for stats

    # Try finding elements that contain stat abbreviations
    all_text = soup.get_text()

    # Get the expected stats for this category
    expected_stats = get_expected_stats(category)

    # Try to find a container that has the club stats
    # Look for common patterns in the page structure

    # Find all elements and look for stat patterns
    for stat_abbrev in expected_stats:
        # Search for the stat in the page
        elements = soup.find_all(string=lambda text: text and stat_abbrev == text.strip())

        for elem in elements:
            # Try to find the parent row or container
            parent = elem.parent
            if parent:
                # Look for sibling elements that might contain value and rank
                siblings = parent.find_next_siblings()

                value = ""
                rank = ""

                for sib in siblings[:3]:  # Check next few siblings
                    sib_text = sib.get_text(strip=True)
                    if sib_text:
                        if not value:
                            value = sib_text
                        elif not rank:
                            rank = sib_text
                            break

                if value:
                    stats.append({
                        "abbrev": stat_abbrev,
                        "name": STAT_NAMES.get(stat_abbrev, stat_abbrev),
                        "club": value,
                        "rank": rank
                    })
                    break

    return stats


def get_expected_stats(category):
    """Return expected stat abbreviations for each category."""
    stats_by_category = {
        "attacking": ["M", "G", "G/M", "A", "xG", "xA", "POSS%", "PK", "FK", "SH", "SOT", "TCH", "TCH-BOX", "OFF"],
        "passing": ["M", "A", "xA", "PASS", "PASS/M", "PASS%", "PASS-ATT", "BCC", "PASS-KEY", "PASS-LNG", "PASS-F3RD", "THRU-BALL", "CRS", "CNR"],
        "defending": ["M", "xGA", "TKL", "TKL-W", "TKL-LM", "SH-BLK", "BLK-CRS", "INT", "CLR", "REC", "ERR-SH", "ERR-G", "PKC", "OG"],
        "goalkeeping": ["M", "GC", "xGA", "GC/M", "SV", "SV-PK", "CS"],
        "miscellaneous": ["M", "YC", "RC", "FOUL", "FOULED", "PK-W", "CNR-W", "AER-W", "AER-L", "DUEL-W", "DUEL-L", "POSS-L"]
    }
    return stats_by_category.get(category, [])


def scrape_all_stats():
    """Scrape all stat categories."""
    all_stats = {}

    for category in STAT_CATEGORIES.keys():
        print(f"Scraping {category} stats...")
        all_stats[category] = scrape_stats(category)

    return all_stats


def save_stats_to_json(stats, filename="stats.json"):
    """Save stats to a JSON file."""
    with open(filename, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"Stats saved to {filename}")


if __name__ == "__main__":
    all_stats = scrape_all_stats()
    save_stats_to_json(all_stats)

    # Print summary
    for category, stats in all_stats.items():
        print(f"\n{category.upper()} ({len(stats)} stats):")
        for stat in stats[:3]:  # Show first 3
            print(f"  {stat['abbrev']}: {stat['club']} (Rank: {stat['rank']})")
