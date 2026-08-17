(() => {
    const cache = new Map();
    const statsContainer = document.getElementById('stats-container');
    if (!statsContainer) return;

    const style = document.createElement('style');
    style.textContent = `
        #stats-container .stat-card { cursor:pointer; transition:transform .16s ease, border-color .16s ease, box-shadow .16s ease; }
        #stats-container .stat-card:hover,
        #stats-container .stat-card:focus-visible { transform:translateY(-2px); border-color:rgba(255,255,255,.22); box-shadow:0 12px 28px rgba(0,0,0,.22); outline:none; }
        #stats-container .stat-card:focus-visible { box-shadow:0 0 0 2px rgba(255,255,255,.32), 0 12px 28px rgba(0,0,0,.22); }
        .leaderboard-overlay { position:fixed; inset:0; z-index:1200; display:none; align-items:center; justify-content:center; padding:18px; background:rgba(4,5,9,.82); backdrop-filter:blur(8px); }
        .leaderboard-overlay.open { display:flex; }
        .leaderboard-modal { width:min(1120px, 100%); max-height:min(760px, 94vh); display:flex; flex-direction:column; background:#111217; border:1px solid rgba(255,255,255,.12); border-radius:18px; box-shadow:0 26px 80px rgba(0,0,0,.48); overflow:hidden; }
        .leaderboard-head { position:relative; padding:18px 24px 14px; border-bottom:1px solid rgba(255,255,255,.08); }
        .leaderboard-close { position:absolute; right:16px; top:14px; width:34px; height:34px; border-radius:50%; border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.04); color:#fff; font-size:22px; line-height:1; cursor:pointer; }
        .leaderboard-close:hover { background:rgba(255,255,255,.09); }
        .leaderboard-eyebrow { font-size:10px; font-weight:800; letter-spacing:.16em; text-transform:uppercase; opacity:.55; margin-bottom:5px; }
        .leaderboard-title { margin:0; padding-right:44px; font-size:24px; line-height:1.1; font-weight:800; }
        .leaderboard-subtitle { margin-top:5px; font-size:12px; opacity:.64; }
        .leaderboard-selected-summary { margin-top:10px; display:flex; align-items:center; justify-content:space-between; gap:16px; padding:8px 12px; border:1px solid rgba(255,255,255,.1); border-radius:10px; background:rgba(255,255,255,.035); }
        .leaderboard-selected-name { font-size:12px; font-weight:700; }
        .leaderboard-selected-value { display:flex; align-items:baseline; gap:9px; font-weight:800; }
        .leaderboard-selected-value strong { font-size:18px; }
        .leaderboard-selected-value span { font-size:11px; opacity:.62; }
        .leaderboard-table-head { display:none; }
        .leaderboard-list { display:grid; grid-template-rows:repeat(12,minmax(0,1fr)); grid-auto-flow:column; grid-template-columns:repeat(2,minmax(0,1fr)); column-gap:18px; row-gap:2px; overflow:hidden; padding:10px 16px 12px; min-height:0; }
        .leaderboard-row { display:grid; grid-template-columns:42px minmax(0,1fr) 90px; gap:9px; align-items:center; min-height:34px; padding:3px 9px; border-radius:9px; border:1px solid transparent; }
        .leaderboard-row + .leaderboard-row { margin-top:0; }
        .leaderboard-row.selected { background:rgba(255,255,255,.075); border-color:rgba(255,255,255,.15); }
        .leaderboard-row.unavailable { opacity:.42; }
        .leaderboard-rank { font-size:12px; font-weight:800; }
        .leaderboard-team { min-width:0; font-size:12px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .leaderboard-value { text-align:right; font-size:13px; font-weight:800; font-variant-numeric:tabular-nums; }
        .leaderboard-rank.rank-top { color:#82d9a7; }
        .leaderboard-rank.rank-good { color:#91c7ef; }
        .leaderboard-rank.rank-mid { color:#e8cb7c; }
        .leaderboard-rank.rank-low { color:#e89a91; }
        .leaderboard-loading, .leaderboard-error { grid-row:1 / -1; grid-column:1 / -1; align-self:center; padding:36px 24px; text-align:center; opacity:.76; }
        .leaderboard-error { color:#ffb6ae; }
        .leaderboard-foot { padding:8px 18px 10px; border-top:1px solid rgba(255,255,255,.06); font-size:10px; opacity:.5; text-align:center; }
        @media (max-width:820px) {
            .leaderboard-overlay { padding:10px; align-items:flex-end; }
            .leaderboard-modal { width:100%; max-height:92vh; border-radius:18px 18px 10px 10px; }
            .leaderboard-head { padding:22px 18px 16px; }
            .leaderboard-title { font-size:23px; }
            .leaderboard-table-head { display:grid; grid-template-columns:46px minmax(0,1fr) 92px; gap:12px; padding:12px 16px; font-size:10px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; opacity:.5; border-bottom:1px solid rgba(255,255,255,.06); }
            .leaderboard-list { display:block; overflow:auto; overscroll-behavior:contain; padding:6px; }
            .leaderboard-row { grid-template-columns:46px minmax(0,1fr) 92px; min-height:44px; padding:6px 10px; }
            .leaderboard-row + .leaderboard-row { margin-top:2px; }
            .leaderboard-team { font-size:14px; }
            .leaderboard-value { font-size:15px; }
        }
    `;
    document.head.appendChild(style);

    const overlay = document.createElement('div');
    overlay.className = 'leaderboard-overlay';
    overlay.id = 'leaderboard-overlay';
    overlay.innerHTML = `
        <section class="leaderboard-modal" role="dialog" aria-modal="true" aria-labelledby="leaderboard-title">
            <div class="leaderboard-head">
                <button class="leaderboard-close" type="button" aria-label="Close leaderboard">×</button>
                <div class="leaderboard-eyebrow" id="leaderboard-eyebrow">Championship leaderboard</div>
                <h2 class="leaderboard-title" id="leaderboard-title">Loading…</h2>
                <div class="leaderboard-subtitle" id="leaderboard-subtitle"></div>
                <div class="leaderboard-selected-summary" id="leaderboard-selected-summary" hidden></div>
            </div>
            <div class="leaderboard-table-head"><span>Rank</span><span>Club</span><span style="text-align:right">Value</span></div>
            <div class="leaderboard-list" id="leaderboard-list"><div class="leaderboard-loading">Loading Championship rankings…</div></div>
            <div class="leaderboard-foot">Only complete APIfootball data is ranked. Unavailable club values appear at the bottom.</div>
        </section>
    `;
    document.body.appendChild(overlay);

    const closeBtn = overlay.querySelector('.leaderboard-close');
    const titleEl = overlay.querySelector('#leaderboard-title');
    const eyebrowEl = overlay.querySelector('#leaderboard-eyebrow');
    const subtitleEl = overlay.querySelector('#leaderboard-subtitle');
    const summaryEl = overlay.querySelector('#leaderboard-selected-summary');
    const listEl = overlay.querySelector('#leaderboard-list');

    function activeCategory() {
        const active = document.querySelector('.tab-btn.active');
        const category = active?.dataset?.category || '';
        return ['attacking','passing','defending','goalkeeping','miscellaneous'].includes(category) ? category : '';
    }

    function selectedTeamKey() {
        return document.querySelector('#team-dropdown .dropdown-item.active')?.dataset?.value || 'west-ham';
    }

    function selectedTeamName() {
        return document.getElementById('selected-team-name')?.textContent?.trim() || 'Selected club';
    }

    function rankNumber(rank) {
        const value = parseInt(String(rank || '').replace(/\D/g, ''), 10);
        return Number.isFinite(value) ? value : null;
    }

    function rankTone(rank) {
        const n = rankNumber(rank);
        if (n === null) return '';
        if (n <= 6) return 'rank-top';
        if (n <= 12) return 'rank-good';
        if (n <= 18) return 'rank-mid';
        return 'rank-low';
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function openOverlay() {
        overlay.classList.add('open');
        document.body.style.overflow = 'hidden';
        closeBtn.focus({ preventScroll:true });
    }

    function closeOverlay() {
        overlay.classList.remove('open');
        document.body.style.overflow = '';
    }

    function render(data) {
        const teamKey = selectedTeamKey();
        const teamName = selectedTeamName();
        const selected = (data.teams || []).find(row => row.team_key === teamKey);
        const direction = data.stat?.direction === 'lower' ? 'Lower is better' : 'Higher is better';

        eyebrowEl.textContent = `${data.category || ''} · Championship leaderboard`;
        titleEl.textContent = `${data.stat?.abbrev || ''} — ${data.stat?.name || 'Statistic'}`;
        subtitleEl.textContent = `${direction} · ${data.team_count || data.teams?.length || 0} Championship clubs`;

        if (selected) {
            summaryEl.hidden = false;
            summaryEl.innerHTML = `
                <div class="leaderboard-selected-name">${escapeHtml(teamName)}</div>
                <div class="leaderboard-selected-value"><strong>${escapeHtml(selected.value)}</strong><span>${escapeHtml(selected.rank === '-' ? 'Not ranked' : selected.rank)}</span></div>
            `;
        } else {
            summaryEl.hidden = true;
            summaryEl.innerHTML = '';
        }

        listEl.innerHTML = (data.teams || []).map(row => {
            const isSelected = row.team_key === teamKey;
            const unavailable = !row.available;
            return `
                <div class="leaderboard-row${isSelected ? ' selected' : ''}${unavailable ? ' unavailable' : ''}" data-team-key="${escapeHtml(row.team_key)}">
                    <div class="leaderboard-rank ${rankTone(row.rank)}">${escapeHtml(row.rank)}</div>
                    <div class="leaderboard-team">${escapeHtml(row.team)}</div>
                    <div class="leaderboard-value">${escapeHtml(row.value)}</div>
                </div>
            `;
        }).join('');
    }

    async function showLeaderboard(card) {
        const category = activeCategory();
        const abbrev = card.querySelector('.stat-abbrev')?.textContent?.trim();
        const name = card.querySelector('.stat-name')?.textContent?.trim();
        if (!category || !abbrev) return;

        titleEl.textContent = `${abbrev} — ${name || 'Statistic'}`;
        eyebrowEl.textContent = `${category} · Championship leaderboard`;
        subtitleEl.textContent = '';
        summaryEl.hidden = true;
        listEl.innerHTML = '<div class="leaderboard-loading">Loading Championship rankings…</div>';
        openOverlay();

        const key = `${category}|${abbrev}`;
        try {
            let data = cache.get(key);
            if (!data) {
                const response = await fetch(`/api/leaderboard?category=${encodeURIComponent(category)}&stat=${encodeURIComponent(abbrev)}`);
                data = await response.json();
                if (!response.ok || data.error) throw new Error(data.error || `Request failed (${response.status})`);
                cache.set(key, data);
            }
            render(data);
        } catch (error) {
            listEl.innerHTML = `<div class="leaderboard-error">${escapeHtml(error.message || 'Unable to load this leaderboard.')}</div>`;
        }
    }

    function decorateCards() {
        statsContainer.querySelectorAll('.stat-card').forEach(card => {
            card.setAttribute('role', 'button');
            card.setAttribute('tabindex', '0');
            const label = card.querySelector('.stat-name')?.textContent?.trim() || 'stat';
            card.setAttribute('aria-label', `View Championship leaderboard for ${label}`);
            card.setAttribute('title', `View Championship leaderboard for ${label}`);
        });
    }

    statsContainer.addEventListener('click', event => {
        const card = event.target.closest('.stat-card');
        if (card && statsContainer.contains(card)) showLeaderboard(card);
    });

    statsContainer.addEventListener('keydown', event => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const card = event.target.closest('.stat-card');
        if (!card || !statsContainer.contains(card)) return;
        event.preventDefault();
        showLeaderboard(card);
    });

    closeBtn.addEventListener('click', closeOverlay);
    overlay.addEventListener('click', event => {
        if (event.target === overlay) closeOverlay();
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && overlay.classList.contains('open')) closeOverlay();
    });

    new MutationObserver(decorateCards).observe(statsContainer, { childList:true, subtree:true });
    decorateCards();
})();
