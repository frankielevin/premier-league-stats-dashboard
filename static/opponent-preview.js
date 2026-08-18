(() => {
    const compareContainer = document.getElementById('compare-container');
    const compare1 = document.getElementById('compare-dropdown-1');
    const compare2 = document.getElementById('compare-dropdown-2');
    const matchupHeader = compareContainer?.querySelector('.matchup-header');
    if (!compareContainer || !compare1 || !compare2 || !matchupHeader || document.getElementById('opponent-preview')) return;

    const keyMetrics = [
        { category:'attacking', abbrev:'G/M', label:'Goals / match', lower:false },
        { category:'attacking', abbrev:'POSS%', label:'Possession', lower:false },
        { category:'attacking', abbrev:'SH/M', label:'Shots / match', lower:false },
        { category:'passing', abbrev:'PASS%', label:'Pass completion', lower:false },
        { category:'defending', abbrev:'TKL/M', label:'Tackles / match', lower:false },
        { category:'goalkeeping', abbrev:'GC/M', label:'Goals conceded / match', lower:true },
    ];

    const style = document.createElement('style');
    style.textContent = `
        .opp-preview { margin:18px 0 20px; border:1px solid rgba(255,255,255,.1); border-radius:16px; background:linear-gradient(145deg,rgba(255,255,255,.045),rgba(255,255,255,.018)); overflow:hidden; }
        .opp-preview-head { display:flex; align-items:center; justify-content:space-between; gap:14px; padding:12px 16px; border-bottom:1px solid rgba(255,255,255,.07); }
        .opp-preview-kicker { font-size:10px; font-weight:800; letter-spacing:.15em; text-transform:uppercase; opacity:.55; }
        .opp-preview-title { margin:2px 0 0; font-size:18px; font-weight:800; }
        .opp-preview-shot { border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.045); color:inherit; border-radius:8px; padding:7px 11px; font:inherit; font-size:10px; font-weight:800; cursor:pointer; white-space:nowrap; }
        .opp-preview-shot:hover { background:rgba(255,255,255,.09); }
        .opp-preview-shot:disabled { opacity:.45; cursor:default; }
        .opp-preview-body { padding:14px; }
        .opp-preview-loading,.opp-preview-error { padding:34px 16px; text-align:center; opacity:.68; }
        .opp-preview-error { color:#ffb6ae; }
        .opp-context-grid { display:grid; grid-template-columns:minmax(0,1fr) minmax(250px,.78fr) minmax(0,1fr); gap:12px; align-items:stretch; }
        .opp-team-card,.opp-meeting-card,.opp-key-stats { border:1px solid rgba(255,255,255,.075); background:rgba(0,0,0,.13); border-radius:12px; }
        .opp-team-card { padding:12px; }
        .opp-team-card.right { text-align:right; }
        .opp-team-top { display:flex; align-items:center; gap:10px; }
        .opp-team-card.right .opp-team-top { flex-direction:row-reverse; }
        .opp-team-badge { width:34px; height:34px; object-fit:contain; flex:0 0 auto; }
        .opp-team-name { font-size:15px; font-weight:800; line-height:1.15; }
        .opp-standing { margin-top:2px; font-size:11px; opacity:.62; }
        .opp-record { display:grid; grid-template-columns:repeat(4,1fr); gap:5px; margin-top:10px; }
        .opp-record-cell { padding:6px 4px; border-radius:7px; background:rgba(255,255,255,.035); text-align:center; }
        .opp-record-value { display:block; font-size:13px; font-weight:850; }
        .opp-record-label { display:block; margin-top:1px; font-size:8px; font-weight:750; letter-spacing:.08em; text-transform:uppercase; opacity:.48; }
        .opp-form-wrap { display:flex; align-items:center; gap:7px; margin-top:10px; }
        .opp-team-card.right .opp-form-wrap { justify-content:flex-end; }
        .opp-small-label { font-size:8px; font-weight:800; letter-spacing:.11em; text-transform:uppercase; opacity:.46; }
        .opp-form { display:flex; gap:4px; }
        .opp-form-badge { width:22px; height:22px; display:flex; align-items:center; justify-content:center; border-radius:6px; font-size:10px; font-weight:900; background:rgba(255,255,255,.07); }
        .opp-form-badge.w { background:rgba(80,190,120,.2); color:#9de2b6; }
        .opp-form-badge.d { background:rgba(225,182,82,.18); color:#f0cf83; }
        .opp-form-badge.l { background:rgba(210,92,82,.2); color:#f0a49e; }
        .opp-fixture-lines { margin-top:10px; display:grid; gap:5px; }
        .opp-fixture-line { display:grid; grid-template-columns:38px minmax(0,1fr); gap:7px; align-items:baseline; font-size:10px; line-height:1.25; }
        .opp-team-card.right .opp-fixture-line { grid-template-columns:minmax(0,1fr) 38px; }
        .opp-team-card.right .opp-fixture-line .opp-small-label { order:2; }
        .opp-team-card.right .opp-fixture-line span:last-child { text-align:right; }
        .opp-fixture-value { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .opp-meeting-card { padding:12px; display:flex; flex-direction:column; justify-content:center; text-align:center; }
        .opp-meeting-section + .opp-meeting-section { margin-top:11px; padding-top:10px; border-top:1px solid rgba(255,255,255,.065); }
        .opp-meeting-title { margin-top:3px; font-size:12px; font-weight:800; }
        .opp-meeting-detail { margin-top:3px; font-size:9px; opacity:.58; }
        .opp-h2h-score { display:grid; grid-template-columns:1fr auto 1fr; gap:7px; align-items:center; margin-top:7px; }
        .opp-h2h-side { min-width:0; font-size:9px; font-weight:750; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .opp-h2h-side strong { display:block; font-size:17px; line-height:1; }
        .opp-h2h-draw { font-size:8px; opacity:.55; }
        .opp-h2h-draw strong { display:block; font-size:13px; opacity:1; }
        .opp-key-stats { margin-top:12px; overflow:hidden; }
        .opp-key-stats-head { padding:7px 12px; font-size:9px; font-weight:800; letter-spacing:.11em; text-transform:uppercase; opacity:.5; border-bottom:1px solid rgba(255,255,255,.06); text-align:center; }
        .opp-metric-row { display:grid; grid-template-columns:minmax(90px,1fr) 160px minmax(90px,1fr); align-items:center; min-height:29px; padding:0 12px; border-bottom:1px solid rgba(255,255,255,.045); }
        .opp-metric-row:last-child { border-bottom:0; }
        .opp-metric-value { font-size:12px; font-weight:850; }
        .opp-metric-value.right { text-align:right; }
        .opp-metric-value.winner { color:#a9e4bf; }
        .opp-metric-rank { margin-left:5px; font-size:8px; font-weight:650; opacity:.46; }
        .opp-metric-label { text-align:center; font-size:9px; font-weight:700; opacity:.58; }
        .opp-preview-note { margin-top:8px; text-align:center; font-size:8px; opacity:.38; }
        .opp-export-stage { position:fixed; left:-20000px; top:0; width:1280px; height:720px; padding:28px 42px; box-sizing:border-box; display:flex; align-items:center; justify-content:center; background:#111217; color:#fff; pointer-events:none; overflow:hidden; }
        .opp-export-stage .opp-preview { width:1196px; margin:0; background:#111217; }
        .opp-export-stage .opp-preview-shot { display:none; }
        .opp-export-stage .opp-preview-head { padding:11px 16px; }
        .opp-export-stage .opp-preview-body { padding:12px 14px 13px; }
        .opp-export-stage .opp-context-grid { gap:10px; }
        .opp-export-stage .opp-team-card,.opp-export-stage .opp-meeting-card { padding:10px 12px; }
        .opp-export-stage .opp-key-stats { margin-top:10px; }
        .opp-export-stage .opp-metric-row { min-height:27px; }
        @media (max-width:920px) {
            .opp-context-grid { grid-template-columns:1fr; }
            .opp-team-card.right { text-align:left; }
            .opp-team-card.right .opp-team-top { flex-direction:row; }
            .opp-team-card.right .opp-form-wrap { justify-content:flex-start; }
            .opp-team-card.right .opp-fixture-line { grid-template-columns:38px minmax(0,1fr); }
            .opp-team-card.right .opp-fixture-line .opp-small-label { order:0; }
            .opp-team-card.right .opp-fixture-line span:last-child { text-align:left; }
            .opp-metric-row { grid-template-columns:minmax(70px,1fr) 120px minmax(70px,1fr); }
        }
    `;
    document.head.appendChild(style);

    const preview = document.createElement('section');
    preview.className = 'opp-preview';
    preview.id = 'opponent-preview';
    preview.innerHTML = `
        <div class="opp-preview-head">
            <div>
                <div class="opp-preview-kicker">Match preparation</div>
                <h3 class="opp-preview-title">Opponent Preview</h3>
            </div>
            <button type="button" class="opp-preview-shot">Save Match Preview</button>
        </div>
        <div class="opp-preview-body"><div class="opp-preview-loading">Open Compare to load matchup context…</div></div>
    `;
    matchupHeader.insertAdjacentElement('afterend', preview);

    const body = preview.querySelector('.opp-preview-body');
    const shotBtn = preview.querySelector('.opp-preview-shot');
    const cache = {
        standings: null,
        fixtures: null,
        stats: new Map(),
        h2h: new Map(),
    };
    let refreshTimer = null;
    let requestSerial = 0;

    function escapeHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    async function fetchJson(url) {
        const response = await fetch(url);
        const data = await response.json();
        if (!response.ok || data?.error) throw new Error(data?.error || `Request failed (${response.status})`);
        return data;
    }

    function teamKeys() {
        return [compare1.dataset.value || 'burnley', compare2.dataset.value || 'west-ham'];
    }

    function teamName(dropdown, fallback) {
        return dropdown.querySelector('.compare-selected-team')?.textContent?.trim() || fallback;
    }

    function pairKey(a, b) {
        return [a, b].sort().join('__');
    }

    function shortDate(raw) {
        const parts = String(raw || '').split('-').map(Number);
        if (parts.length !== 3 || parts.some(v => !Number.isFinite(v))) return raw || 'TBC';
        const d = new Date(parts[0], parts[1] - 1, parts[2]);
        return d.toLocaleDateString('en-GB', {day:'numeric', month:'short'});
    }

    function fixtureForTeam(teamKey, fixture, completed=false) {
        if (!fixture) return '—';
        const home = fixture.home_key === teamKey;
        const opponent = home ? fixture.away : fixture.home;
        if (completed) {
            const teamScore = home ? fixture.home_score : fixture.away_score;
            const oppScore = home ? fixture.away_score : fixture.home_score;
            const result = teamScore > oppScore ? 'W' : teamScore < oppScore ? 'L' : 'D';
            return `${result} · ${home ? 'vs' : '@'} ${opponent} ${teamScore}–${oppScore} · ${shortDate(fixture.date)}`;
        }
        const time = fixture.time ? ` · ${fixture.time}` : '';
        return `${home ? 'vs' : '@'} ${opponent} · ${shortDate(fixture.date)}${time}`;
    }

    function formHtml(form) {
        const items = Array.isArray(form) ? form.slice(-5) : [];
        if (!items.length) return '<span style="opacity:.45;font-size:9px">No league form yet</span>';
        return `<div class="opp-form">${items.map(item => {
            const result = String(item.result || '').toUpperCase();
            return `<span class="opp-form-badge ${result.toLowerCase()}" title="${escapeHtml(`${result} vs ${item.opponent || ''}`)}">${escapeHtml(result)}</span>`;
        }).join('')}</div>`;
    }

    function standingRecord(split) {
        if (!split) return '<div class="opp-record-cell"><span class="opp-record-value">—</span><span class="opp-record-label">No data</span></div>';
        const gd = Number(split.gd || 0);
        return `
            <div class="opp-record-cell"><span class="opp-record-value">${escapeHtml(split.played ?? '—')}</span><span class="opp-record-label">Played</span></div>
            <div class="opp-record-cell"><span class="opp-record-value">${escapeHtml(split.won ?? '—')}-${escapeHtml(split.drawn ?? '—')}-${escapeHtml(split.lost ?? '—')}</span><span class="opp-record-label">W-D-L</span></div>
            <div class="opp-record-cell"><span class="opp-record-value">${gd > 0 ? '+' : ''}${escapeHtml(gd)}</span><span class="opp-record-label">GD</span></div>
            <div class="opp-record-cell"><span class="opp-record-value">${escapeHtml(split.points ?? '—')}</span><span class="opp-record-label">Pts</span></div>
        `;
    }

    function teamCard(teamKey, name, standings, formData, side) {
        const teamStanding = standings?.[teamKey] || {};
        const split = teamStanding.overall || {};
        const teamForm = formData?.teams?.[teamKey] || {};
        const position = split.position ? `${split.position}${ordinalSuffix(split.position)}` : '—';
        return `
            <article class="opp-team-card ${side}">
                <div class="opp-team-top">
                    <img class="opp-team-badge" src="/api/standings?badge=${encodeURIComponent(teamKey)}" alt="">
                    <div>
                        <div class="opp-team-name">${escapeHtml(name)}</div>
                        <div class="opp-standing">${escapeHtml(position)} in Championship · ${escapeHtml(split.points ?? '—')} pts</div>
                    </div>
                </div>
                <div class="opp-record">${standingRecord(split)}</div>
                <div class="opp-form-wrap"><span class="opp-small-label">Form</span>${formHtml(teamForm.form)}</div>
                <div class="opp-fixture-lines">
                    <div class="opp-fixture-line"><span class="opp-small-label">Last</span><span class="opp-fixture-value">${escapeHtml(fixtureForTeam(teamKey, teamForm.last_match, true))}</span></div>
                    <div class="opp-fixture-line"><span class="opp-small-label">Next</span><span class="opp-fixture-value">${escapeHtml(fixtureForTeam(teamKey, teamForm.next_match, false))}</span></div>
                </div>
            </article>
        `;
    }

    function ordinalSuffix(value) {
        const n = Number(value);
        if (!Number.isFinite(n)) return '';
        const mod100 = n % 100;
        if (mod100 >= 11 && mod100 <= 13) return 'th';
        return {1:'st',2:'nd',3:'rd'}[n % 10] || 'th';
    }

    function nextMeetingHtml(fixture) {
        if (!fixture) {
            return `<div class="opp-meeting-title">Next league meeting unavailable</div><div class="opp-meeting-detail">No future Championship fixture is currently returned for this pairing.</div>`;
        }
        return `
            <div class="opp-meeting-title">${escapeHtml(fixture.home)} vs ${escapeHtml(fixture.away)}</div>
            <div class="opp-meeting-detail">${escapeHtml(shortDate(fixture.date))}${fixture.time ? ` · ${escapeHtml(fixture.time)}` : ''}</div>
        `;
    }

    function h2hHtml(h2h, name1, name2) {
        if (!h2h || !Number(h2h.played || 0)) {
            return `<div class="opp-meeting-title">No previous meetings available</div><div class="opp-meeting-detail">APIfootball has no completed H2H history for this pairing.</div>`;
        }
        const overall = h2h.overall || {};
        const latest = h2h.recent?.[0];
        const latestText = latest
            ? `${latest.home} ${latest.home_score}–${latest.away_score} ${latest.away} · ${latest.date}`
            : 'No recent meeting details available';
        return `
            <div class="opp-h2h-score">
                <div class="opp-h2h-side"><strong>${escapeHtml(overall.w ?? 0)}</strong>${escapeHtml(name1)} wins</div>
                <div class="opp-h2h-draw"><strong>${escapeHtml(overall.d ?? 0)}</strong>draws</div>
                <div class="opp-h2h-side"><strong>${escapeHtml(overall.l ?? 0)}</strong>${escapeHtml(name2)} wins</div>
            </div>
            <div class="opp-meeting-detail">Last ${escapeHtml(h2h.played)} meetings · Goals ${escapeHtml(h2h.goals_for ?? 0)}–${escapeHtml(h2h.goals_against ?? 0)}</div>
            <div class="opp-meeting-detail">Latest: ${escapeHtml(latestText)}</div>
        `;
    }

    function meetingCard(formData, h2h, key1, key2, name1, name2) {
        const meeting = formData?.next_meetings?.[pairKey(key1, key2)] || null;
        return `
            <article class="opp-meeting-card">
                <div class="opp-meeting-section">
                    <div class="opp-small-label">Next meeting</div>
                    ${nextMeetingHtml(meeting)}
                </div>
                <div class="opp-meeting-section">
                    <div class="opp-small-label">Head to head</div>
                    ${h2hHtml(h2h, name1, name2)}
                </div>
            </article>
        `;
    }

    function metricStat(stats, spec) {
        return stats?.[spec.category]?.stats?.find(item => item.abbrev === spec.abbrev) || null;
    }

    function numeric(value) {
        if (value === null || value === undefined || value === '—' || value === '-') return null;
        const n = parseFloat(String(value).replaceAll(',','').replace('%',''));
        return Number.isFinite(n) ? n : null;
    }

    function metricWinner(left, right, lower) {
        const a = numeric(left?.club);
        const b = numeric(right?.club);
        if (a === null || b === null || Math.abs(a - b) < 1e-9) return '';
        const leftWins = lower ? a < b : a > b;
        return leftWins ? 'left' : 'right';
    }

    function metricsHtml(stats1, stats2) {
        return `
            <section class="opp-key-stats">
                <div class="opp-key-stats-head">Key team stats · Championship season to date</div>
                ${keyMetrics.map(spec => {
                    const left = metricStat(stats1, spec);
                    const right = metricStat(stats2, spec);
                    const winner = metricWinner(left, right, spec.lower);
                    return `
                        <div class="opp-metric-row">
                            <div class="opp-metric-value ${winner === 'left' ? 'winner' : ''}">${escapeHtml(left?.club ?? '—')}<span class="opp-metric-rank">${escapeHtml(left?.rank && left.rank !== '-' ? left.rank : '')}</span></div>
                            <div class="opp-metric-label">${escapeHtml(spec.label)}</div>
                            <div class="opp-metric-value right ${winner === 'right' ? 'winner' : ''}">${escapeHtml(right?.club ?? '—')}<span class="opp-metric-rank">${escapeHtml(right?.rank && right.rank !== '-' ? right.rank : '')}</span></div>
                        </div>
                    `;
                }).join('')}
            </section>
        `;
    }

    async function getStandings() {
        if (!cache.standings) cache.standings = fetchJson('/api/standings').catch(error => { cache.standings = null; throw error; });
        return cache.standings;
    }

    async function getFixtures() {
        if (!cache.fixtures) cache.fixtures = fetchJson('/api/form-fixtures').catch(error => { cache.fixtures = null; throw error; });
        return cache.fixtures;
    }

    async function getStats(teamKey) {
        if (!cache.stats.has(teamKey)) {
            cache.stats.set(teamKey, fetchJson(`/api/stats?team=${encodeURIComponent(teamKey)}`).catch(error => {
                cache.stats.delete(teamKey);
                throw error;
            }));
        }
        return cache.stats.get(teamKey);
    }

    async function getH2h(key1, key2) {
        const key = `${key1}__${key2}`;
        if (!cache.h2h.has(key)) {
            cache.h2h.set(key, fetchJson(`/api/h2h?team1=${encodeURIComponent(key1)}&team2=${encodeURIComponent(key2)}`).catch(error => {
                cache.h2h.delete(key);
                throw error;
            }));
        }
        return cache.h2h.get(key);
    }

    async function refreshPreview() {
        const serial = ++requestSerial;
        const [key1, key2] = teamKeys();
        const name1 = teamName(compare1, key1);
        const name2 = teamName(compare2, key2);
        if (key1 === key2) {
            body.innerHTML = '<div class="opp-preview-error">Select two different teams to build an opponent preview.</div>';
            return;
        }

        body.innerHTML = '<div class="opp-preview-loading">Loading league, form, H2H and key-stat context…</div>';
        const results = await Promise.allSettled([
            getStandings(),
            getFixtures(),
            getH2h(key1, key2),
            getStats(key1),
            getStats(key2),
        ]);
        if (serial !== requestSerial) return;

        const [standingsResult, fixturesResult, h2hResult, stats1Result, stats2Result] = results;
        const standings = standingsResult.status === 'fulfilled' ? standingsResult.value : {};
        const fixtures = fixturesResult.status === 'fulfilled' ? fixturesResult.value : {};
        const h2h = h2hResult.status === 'fulfilled' ? h2hResult.value : null;
        const stats1 = stats1Result.status === 'fulfilled' ? stats1Result.value : {};
        const stats2 = stats2Result.status === 'fulfilled' ? stats2Result.value : {};

        if (!Object.keys(standings).length && !Object.keys(fixtures).length && !h2h && !Object.keys(stats1).length && !Object.keys(stats2).length) {
            body.innerHTML = '<div class="opp-preview-error">Unable to load opponent-preview data right now.</div>';
            return;
        }

        body.innerHTML = `
            <div class="opp-context-grid">
                ${teamCard(key1, name1, standings, fixtures, 'left')}
                ${meetingCard(fixtures, h2h, key1, key2, name1, name2)}
                ${teamCard(key2, name2, standings, fixtures, 'right')}
            </div>
            ${metricsHtml(stats1, stats2)}
            <div class="opp-preview-note">League-only context. Missing provider data is shown as — rather than estimated.</div>
        `;
    }

    function scheduleRefresh(delay=1400) {
        clearTimeout(refreshTimer);
        refreshTimer = setTimeout(refreshPreview, delay);
    }

    [compare1, compare2].forEach(dropdown => {
        new MutationObserver(mutations => {
            if (mutations.some(mutation => mutation.type === 'attributes' && mutation.attributeName === 'data-value')) scheduleRefresh();
        }).observe(dropdown, {attributes:true, attributeFilter:['data-value']});
    });

    document.addEventListener('click', event => {
        if (event.target.closest('.tab-compare')) scheduleRefresh(1400);
        if (event.target.closest('.compare-dropdown-item')) scheduleRefresh();
    });

    async function waitForImages(root) {
        const images = [...root.querySelectorAll('img')];
        await Promise.all(images.map(img => {
            if (img.complete && img.naturalWidth > 0) return Promise.resolve();
            return new Promise(resolve => {
                img.addEventListener('load', resolve, {once:true});
                img.addEventListener('error', resolve, {once:true});
            });
        }));
    }

    shotBtn.addEventListener('click', async () => {
        if (typeof window.html2canvas !== 'function') return;
        shotBtn.disabled = true;
        const originalText = shotBtn.textContent;
        shotBtn.textContent = 'Preparing…';
        let stage = null;
        try {
            await waitForImages(preview);
            if (document.fonts?.ready) await document.fonts.ready;
            stage = document.createElement('div');
            stage.className = 'opp-export-stage';
            const clone = preview.cloneNode(true);
            clone.removeAttribute('id');
            stage.appendChild(clone);
            document.body.appendChild(stage);
            await waitForImages(stage);
            const canvas = await window.html2canvas(stage, {
                backgroundColor:'#111217',
                useCORS:true,
                scale:1,
                width:1280,
                height:720,
                logging:false,
            });
            const [key1, key2] = teamKeys();
            const link = document.createElement('a');
            link.download = `${key1}-vs-${key2}-preview-1280x720.png`;
            link.href = canvas.toDataURL('image/png');
            link.click();
        } finally {
            stage?.remove();
            shotBtn.disabled = false;
            shotBtn.textContent = originalText;
        }
    });
})();
