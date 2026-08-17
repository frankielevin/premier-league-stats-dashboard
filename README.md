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

The Compare view uses APIfootball's `get_H2H` endpoint. The dedicated `/api/h2h` handler normalises the provider response, removes duplicate or unplayed fixtures, sorts completed meetings newest-first, and uses only the five most recent completed meetings for both the displayed fixtures and W/D/L summary.

## API caching

To protect the free API allowance and avoid rebuilding identical season data for repeated visitors, Vercel edge-caches API responses:

- Team statistics: 15 minutes, with stale responses available while revalidating for up to 6 hours.
- Championship standings: 5 minutes, with stale responses available while revalidating for up to 1 hour.
- Head-to-head records: 6 hours, with stale responses available while revalidating for up to 24 hours.

The application also keeps short-lived in-process caches for provider responses within a warm serverless function.

## Data-quality handling

APIfootball occasionally returns duplicate match-stat keys. The importer intentionally keeps the **last valid occurrence** for a stat within a fixture. Player-level figures are only used for fields that reconcile appropriately; match-level shot figures take precedence over summed player shots.

Missing provider data is shown as `—` rather than treated as a genuine zero, and incomplete metrics are excluded from league rankings.

## Known limitation

The free API response tested for the Championship does not include xG/xGA, so those metrics are not shown.
