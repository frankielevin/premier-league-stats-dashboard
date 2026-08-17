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

## Data-quality handling

APIfootball occasionally returns duplicate match-stat keys. The importer intentionally keeps the **last valid occurrence** for a stat within a fixture. Player-level figures are only used for fields that reconcile appropriately; match-level shot figures take precedence over summed player shots.

## Known limitation

The free API response tested for the Championship does not include xG/xGA, so those metrics are not shown.
