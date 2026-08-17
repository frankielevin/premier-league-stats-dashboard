(() => {
    const nav = document.querySelector('.tabs');
    if (!nav || document.getElementById('standings-open-btn')) return;

    const style = document.createElement('style');
    style.textContent = `
        .standings-open-btn { white-space:nowrap; }
        .standings-overlay { position:fixed; inset:0; z-index:1250; display:none; align-items:center; justify-content:center; padding:18px; background:rgba(4,5,9,.84); backdrop-filter:blur(8px); }
        .standings-overlay.open { display:flex; }
        .standings-modal { width:min(1120px, 100%); max-height:min(900px, 95vh); display:flex; flex-direction:column; background:#111217; border:1px solid rgba(255,255,255,.12); border-radius:18px; box-shadow:0 26px 80px rgba(0,0,0,.48); overflow:hidden; }
        .standings-head { position:relative; padding:16px 22px 12px; border-bottom:1px solid rgba(255,255,255,.08); }
        .standings-eyebrow { font-size:10px; font-weight:800; letter-spacing:.16em; text-transform:uppercase; opacity:.55; margin-bottom:4px; }
        .standings-title { margin:0; padding-right:44px; font-size:27px; line-height:1.05; font-weight:800; }
        .standings-subtitle { margin-top:5px; font-size:12px; opacity:.64; }
        .standings-close { position:absolute; right:16px; top:14px; width:34px; height:34px; border-radius:50%; border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.04); color:#fff; font-size:22px; line-height:1; cursor:pointer; }
        .standings-close:hover { background:rgba(255,255,255,.09); }
        .standings-toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:9px 16px; border-bottom:1px solid rgba(255,255,255,.07); }
        .standings-views { display:flex; gap:6px; }
        .standings-view-btn, .standings-shot-btn { border:1px solid rgba(255,255,255,.11); background:rgba(255,255,255,.035); color:inherit; border-radius:8px; padding:7px 12px; font:inherit; font-size:11px; font-weight:800; cursor:pointer; }
        .standings-view-btn.active { background:#fff; color:#101116; border-color:#fff; }
        .standings-view-btn:hover:not(.active), .standings-shot-btn:hover { background:rgba(255,255,255,.09); }
        .standings-table-head, .standings-row { display:grid; grid-template-columns:44px minmax(180px,1fr) repeat(4,44px) repeat(3,52px) 56px; align-items:center; column-gap:4px; }
        .standings-table-head { padding:6px 14px; border-bottom:1px solid rgba(255,255,255,.07); font-size:10px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; opacity:.52; }
        .standings-table-head span:not(:nth-child(2)) { text-align:center; }
        .standings-list { padding:5px 10px 7px; overflow:hidden; min-height:0; }
        .standings-row { min-height:25px; padding:2px 4px; border-radius:7px; border:1px solid transparent; font-size:12px; }
        .standings-row:nth-child(even) { background:rgba(255,255,255,.018); }
        .standings-row.selected { background:rgba(255,255,255,.09); border-color:rgba(255,255,255,.18); }
        .standings-pos { text-align:center; font-size:12px; font-weight:900; font-variant-numeric:tabular-nums; }
        .standings-team { min-width:0; display:flex; align-items:center; gap:7px; font-size:12px; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .standings-badge { width:18px; height:18px; object-fit:contain; flex:0 0 auto; }
        .standings-team-name { overflow:hidden; text-overflow:ellipsis; }
        .standings-num { text-align:center; font-size:12px; font-weight:650; font-variant-numeric:tabular-nums; }
        .standings-points { font-weight:900; font-size:13px; }
        .standings-gd.positive { color:#82d9a7; }
        .standings-gd.negative { color:#e89a91; }
        .standings-loading, .standings-error { padding:48px 24px; text-align:center; opacity:.72; }
        .standings-error { color:#ffb6ae; }
        .standings-foot { padding:7px 16px 9px; border-top:1px solid rgba(255,255,255,.06); font-size:10px; opacity:.48; text-align:center; }
        @media (max-height:800px) and (min-width:821px) {
            .standings-head { padding:11px 20px 9px; }
            .standings-title { font-size:24px; }
            .standings-subtitle { font-size:10px; margin-top:3px; }
            .standings-toolbar { padding:6px 14px; }
            .standings-view-btn, .standings-shot-btn { padding:5px 10px; font-size:10px; }
            .standings-table-head { padding:4px 12px; font-size:9px; }
            .standings-list { padding:3px 8px 4px; }
            .standings-row { min-height:20px; padding:0 4px; font-size:11px; }
            .standings-team, .standings-num, .standings-pos { font-size:11px; }
            .standings-points { font-size:12px; }
            .standings-badge { width:15px; height:15px; }
            .standings-foot { padding:4px 14px 5px; font-size:9px; }
        }
        @media (max-width:820px) {
            .standings-overlay { padding:8px; align-items:flex-end; }
            .standings-modal { width:100%; max-height:94vh; border-radius:16px 16px 8px 8px; }
            .standings-toolbar { align-items:stretch; flex-direction:column; }
            .standings-views { width:100%; }
            .standings-view-btn { flex:1; }
            .standings-table-head, .standings-row { grid-template-columns:38px minmax(140px,1fr) 34px 34px 34px 34px 40px 40px 42px 46px; min-width:620px; }
            .standings-table-scroll { overflow:auto; }
            .standings-list { overflow:visible; }
        }
    `;
    document.head.appendChild(style);

    const openBtn = document.createElement('button');
    openBtn.type = 'button';
    openBtn.id = 'standings-open-btn';
    openBtn.className = 'tab-btn standings-open-btn';
    openBtn.textContent = 'Table';
    nav.appendChild(openBtn);

    const overlay = document.createElement('div');
    overlay.className = 'standings-overlay';
    overlay.id = 'standings-overlay';
    overlay.innerHTML = `
        <section class="standings-modal" id="standings-modal" role="dialog" aria-modal="true" aria-labelledby="standings-title">
            <div class="standings-head">
                <button class="standings-close" type="button" aria-label="Close Championship table">×</button>
                <div class="standings-eyebrow">2026-27 · EFL Championship</div>
                <h2 class="standings-title" id="standings-title">Championship Table</h2>
                <div class="standings-subtitle" id="standings-subtitle">Overall standings · 24 clubs</div>
            </div>
            <div class="standings-toolbar">
                <div class="standings-views" role="group" aria-label="Standings view">
                    <button class="standings-view-btn active" type="button" data-view="overall">Overall</button>
                    <button class="standings-view-btn" type="button" data-view="home">Home</button>
                    <button class="standings-view-btn" type="button" data-view="away">Away</button>
                </div>
                <button class="standings-shot-btn" type="button">Save Screenshot</button>
            </div>
            <div class="standings-table-scroll">
                <div class="standings-table-head">
                    <span>Pos</span><span>Club</span><span>P</span><span>W</span><span>D</span><span>L</span><span>GF</span><span>GA</span><span>GD</span><span>Pts</span>
                </div>
                <div class="standings-list" id="standings-list"><div class="standings-loading">Loading Championship table…</div></div>
            </div>
            <div class="standings-foot">Overall, home and away views are supplied by APIfootball. Goal difference is calculated from goals for and against.</div>
        </section>
    `;
    document.body.appendChild(overlay);

    const modal = overlay.querySelector('#standings-modal');
    const closeBtn = overlay.querySelector('.standings-close');
    const listEl = overlay.querySelector('#standings-list');
    const subtitleEl = overlay.querySelector('#standings-subtitle');
    const viewBtns = [...overlay.querySelectorAll('.standings-view-btn')];
    const shotBtn = overlay.querySelector('.standings-shot-btn');

    let standingsData = null;
    let currentView = 'overall';

    function escapeHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function selectedTeamKey() {
        return document.querySelector('#team-dropdown .dropdown-item.active')?.dataset?.value || 'west-ham';
    }

    function formatGd(value) {
        const n = Number(value || 0);
        return n > 0 ? `+${n}` : String(n);
    }

    function gdClass(value) {
        const n = Number(value || 0);
        return n > 0 ? 'positive' : n < 0 ? 'negative' : '';
    }

    function render() {
        if (!standingsData) return;
        const selected = selectedTeamKey();
        const rows = Object.entries(standingsData)
            .map(([teamKey, team]) => ({ teamKey, team, split: team[currentView] || team.overall || {} }))
            .sort((a, b) => {
                const ap = Number(a.split.position || 999);
                const bp = Number(b.split.position || 999);
                if (ap !== bp) return ap - bp;
                return String(a.team.team || '').localeCompare(String(b.team.team || ''));
            });

        subtitleEl.textContent = `${currentView[0].toUpperCase()}${currentView.slice(1)} standings · ${rows.length} clubs`;
        listEl.innerHTML = rows.map(({teamKey, team, split}) => {
            const badge = team.badge ? `<img class="standings-badge" src="${escapeHtml(team.badge)}" alt="" loading="lazy">` : '';
            return `
                <div class="standings-row${teamKey === selected ? ' selected' : ''}" data-team-key="${escapeHtml(teamKey)}">
                    <div class="standings-pos">${escapeHtml(split.position || '—')}</div>
                    <div class="standings-team">${badge}<span class="standings-team-name">${escapeHtml(team.team || teamKey)}</span></div>
                    <div class="standings-num">${escapeHtml(split.played ?? '—')}</div>
                    <div class="standings-num">${escapeHtml(split.won ?? '—')}</div>
                    <div class="standings-num">${escapeHtml(split.drawn ?? '—')}</div>
                    <div class="standings-num">${escapeHtml(split.lost ?? '—')}</div>
                    <div class="standings-num">${escapeHtml(split.gf ?? '—')}</div>
                    <div class="standings-num">${escapeHtml(split.ga ?? '—')}</div>
                    <div class="standings-num standings-gd ${gdClass(split.gd)}">${escapeHtml(formatGd(split.gd))}</div>
                    <div class="standings-num standings-points">${escapeHtml(split.points ?? '—')}</div>
                </div>
            `;
        }).join('');
    }

    async function loadStandings() {
        if (standingsData) {
            render();
            return;
        }
        listEl.innerHTML = '<div class="standings-loading">Loading Championship table…</div>';
        try {
            const response = await fetch('/api/standings');
            const data = await response.json();
            if (!response.ok || data.error) throw new Error(data.error || `Request failed (${response.status})`);
            standingsData = data;
            render();
        } catch (error) {
            listEl.innerHTML = `<div class="standings-error">${escapeHtml(error.message || 'Unable to load the Championship table.')}</div>`;
        }
    }

    function open() {
        overlay.classList.add('open');
        document.body.style.overflow = 'hidden';
        loadStandings();
        closeBtn.focus({preventScroll:true});
    }

    function close() {
        overlay.classList.remove('open');
        document.body.style.overflow = '';
    }

    openBtn.addEventListener('click', open);
    closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', event => {
        if (event.target === overlay) close();
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && overlay.classList.contains('open')) close();
    });

    viewBtns.forEach(btn => btn.addEventListener('click', () => {
        currentView = btn.dataset.view || 'overall';
        viewBtns.forEach(item => item.classList.toggle('active', item === btn));
        render();
    }));

    shotBtn.addEventListener('click', async () => {
        if (typeof window.html2canvas !== 'function') return;
        const canvas = await window.html2canvas(modal, {backgroundColor:'#111217', useCORS:true, scale:1.25});
        const link = document.createElement('a');
        link.download = `championship-${currentView}-table.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
    });
})();
