# Championship Stats Dashboard 2026/27

A free-data rebuild of the original Premier League / StatMuse dashboard for the 2026/27 EFL Championship.

## Live deployment branch

`championship-live` is the stable branch for the user-facing Championship dashboard. It is intentionally separate from `main`, which preserves the previous Premier League production deployment.

## Data source

The dashboard uses the free API at APIfootball.com and Championship league ID `153`.

The backend combines two levels of data:

- **Match/team statistics** for goals, shots, shots on target, possession, corners, offsides, fouls, saves and passes.
- **Aggregated player statistics** for tackles, interceptions, clearances, blocks, duels, aerial duels, crosses, dribbles, key passes and related metrics.

League rankings are calculated by the app across all Championship clubs.

## Required environment variable

Set your APIfootball key as:

```text
APIFOOTBALL_KEY=your_key_here
```

Do not commit the key to GitHub.

### Vercel

In the Vercel project, open **Settings → Environment Variables**, add `APIFOOTBALL_KEY`, paste the API key as the value, enable it for the environments you want, and redeploy.

You can then check `/api/health`. It should return `"api_key_configured": true`.

## Current feature set

- Attacking, Passing, Defending, Goalkeeping and Miscellaneous team-stat groups
- Clickable Championship-wide stat leaderboards
- Championship form, previous match and next fixture on club pages
- Full 24-club Championship table with Overall, Home and Away views
- Club comparison with category-by-category stat scoring
- Enhanced Opponent Preview inside Compare mode
- Last-five head-to-head records
- Screenshot-friendly 1280x720 exports for the Championship table and opponent preview

## Stat leaderboards

Every standard stat card can open a Championship-wide leaderboard for that metric. The selected club is highlighted, ranking direction follows the same higher-is-better/lower-is-better rules as the main dashboard, ties use the existing league ranking logic, and incomplete provider data remains unranked at the bottom rather than being treated as zero.

The leaderboard endpoint reuses the dashboard's existing season aggregation and is edge-cached for 15 minutes, so it does not introduce a new APIfootball data source or 24 separate team requests.

## Form and fixtures

Club pages show recent Championship form, the latest completed league match and the next scheduled league fixture. Fixture times are requested from APIfootball using the `Europe/London` timezone so BST/GMT changes are handled by the provider rather than by applying a manual offset.

The form/fixtures endpoint requests the Championship season schedule once and derives team-level context from that cached response.

## Championship table

The Table view uses APIfootball standings data to show all 24 clubs with Overall, Home and Away splits. It includes position, played, wins, draws, losses, goals for, goals against, goal difference and points.

The selected club is highlighted and the table can be exported as a table-only 1280x720 PNG for video use. Club badges are proxied through the app so they remain available to browser-based screenshot capture.

## Enhanced Opponent Preview

Compare mode includes a compact match-preparation panel for the two selected clubs. It brings together:

- current Championship position, points, W-D-L and goal difference
- recent Championship form
- last result and next league fixture
- the next scheduled Championship meeting between the selected clubs
- a compact last-five H2H summary and latest meeting
- selected key season statistics and their current league ranks

The next-meeting lookup is derived from the same cached season fixture response used for form and fixtures, so it does not add another APIfootball provider request. Opponent-preview data is lazy-loaded only when Compare is opened.

The panel can be exported as a 1280x720 PNG for use in video production.

## Head-to-head records

The Compare view uses APIfootball's `get_H2H` endpoint. The dedicated `/api/h2h` handler normalises the provider response, removes duplicate or unplayed fixtures, sorts completed meetings newest-first, and uses the five most recent meetings for both the displayed list and W/D/L summary. If the provider has no usable history for a pairing, the UI shows a clear no-history message.

## Comparison scoring

The dashboard can display totals and per-match versions of the same statistic, but **Overall Stats Won** scores only one representative metric per concept. This avoids double-counting, for example, both Shots and Shots per Match or both Goals and Goals per Match.

## Caching

The app keeps short-lived in-process caches and configures Vercel edge caching for the public API responses:

- stats: 15 minutes, with stale-while-revalidate for 6 hours
- stat leaderboards: 15 minutes, with stale-while-revalidate for 6 hours
- form and fixtures: 15 minutes, with stale-while-revalidate for 6 hours
- standings: 5 minutes, with stale-while-revalidate for 1 hour
- head-to-head: 6 hours, with stale-while-revalidate for 24 hours

This reduces repeated provider calls and cold-start season rebuilds while keeping the dashboard appropriately fresh.

## Data-quality handling

APIfootball occasionally returns duplicate match-stat keys. The importer intentionally keeps the **last valid occurrence** for a stat within a fixture. Player-level figures are only used for fields that reconcile appropriately; match-level shot figures take precedence over summed player shots.

Missing provider data is displayed as `—` rather than silently treated as zero, and incomplete metrics are excluded from Championship rankings.

Save Percentage is intentionally not published because the provider's saves and shots-on-target figures do not consistently reconcile. The Overview uses Saves per Match instead.

## Known limitation

The free API response tested for the Championship does not include xG/xGA, so those metrics are not shown.
