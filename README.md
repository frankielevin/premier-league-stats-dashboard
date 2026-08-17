# Championship Stats Dashboard 2026/27

A free-data rebuild of the original Premier League / StatMuse dashboard for the 2026/27 EFL Championship.

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

## Current stat groups

- Attacking
- Passing
- Defending
- Goalkeeping
- Miscellaneous
- Club comparison
- Championship standings in Overview
- Head-to-head records

## Head-to-head records

The Compare view uses APIfootball's `get_H2H` endpoint. The dedicated `/api/h2h` handler normalises the provider response, removes duplicate or unplayed fixtures, sorts completed meetings newest-first, and uses the five most recent meetings for both the displayed list and W/D/L summary. If the provider has no usable history for a pairing, the UI shows a clear no-history message.

## Comparison scoring

The dashboard can display totals and per-match versions of the same statistic, but **Overall Stats Won** scores only one representative metric per concept. This avoids double-counting, for example, both Shots and Shots per Match or both Goals and Goals per Match.

## Caching

The app keeps short-lived in-process caches and configures Vercel edge caching for the public API responses:

- stats: 15 minutes, with stale-while-revalidate for 1 hour
- standings: 10 minutes, with stale-while-revalidate for 1 hour
- head-to-head: 6 hours, with stale-while-revalidate for 24 hours

This reduces repeated provider calls and cold-start season rebuilds while keeping the dashboard appropriately fresh.

## Data-quality handling

APIfootball occasionally returns duplicate match-stat keys. The importer intentionally keeps the **last valid occurrence** for a stat within a fixture. Player-level figures are only used for fields that reconcile appropriately; match-level shot figures take precedence over summed player shots.

Missing provider data is displayed as `—` rather than silently treated as zero, and incomplete metrics are excluded from Championship rankings.

Save Percentage is intentionally not published because the provider's saves and shots-on-target figures do not consistently reconcile. The Overview uses Saves per Match instead.

## Known limitation

The free API response tested for the Championship does not include xG/xGA, so those metrics are not shown.

<!-- QA preview trigger: clean branch created from the fully validated Championship build. -->
