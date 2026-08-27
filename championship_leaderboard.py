from championship_entry import load_app

# Load and patch the Championship core before importing the leaderboard module,
# because leaderboard.py imports app as core and builds rankings from it.
load_app("app")
from data_integrity import apply
apply()

app = load_app("leaderboard")
