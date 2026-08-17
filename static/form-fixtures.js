(() => {
    const header = document.querySelector('.header');
    const tabs = document.querySelector('.tabs');
    const selectedTeamNameEl = document.getElementById('selected-team-name');
    if (!header || !tabs || !selectedTeamNameEl) return;

    const style = document.createElement('style');
    style.textContent = `
        .form-fixtures-strip {
            display:grid;
            grid-template-columns:0.82fr 1.25fr 1.25fr;
            gap:10px;
            margin:14px 0 12px;
        }
        .form-fixtures-strip.hidden { display:none; }
        .ff-card {
            min-width:0;
            min-height:100px;
            padding:14px 16px;
            border:1px solid rgba(255,255,255,.08);
            border-radius:14px;
            background:linear-gradient(145deg,rgba(255,255,255,.045),rgba(255,255,255,.018));
            box-shadow:0 8px 24px rgba(0,0,0,.12);
        }
        .ff-label {
            font-size:10px;
            font-weight:800;
            letter-spacing:.14em;
            text-transform:uppercase;
            opacity:.52;
            margin-bottom:9px;
        }
        .ff-form-badges { display:flex; gap:7px; align-items:center; min-height:32px; }
        .ff-form-badge {
            width:30px;
            height:30px;
            display:inline-flex;
            align-items:center;
            justify-content:center;
            border-radius:8px;
            font-size:13px;
            font-weight:800;
            border:1px solid rgba(255,255,255,.08);
        }
        .ff-form-badge.win { background:rgba(71,185,121,.2); color:#92e0b4; border-color:rgba(71,185,121,.3); }
        .ff-form-badge.draw { background:rgba(255,255,255,.075); color:#e7e7e9; }
        .ff-form-badge.loss { background:rgba(214,83,83,.17); color:#f1a1a1; border-color:rgba(214,83,83,.25); }
        .ff-form-badge.empty { background:rgba(255,255,255,.025); color:rgba(255,255,255,.22); }
        .ff-form-note { margin-top:7px; font-size:10px; opacity:.44; }
        .ff-fixture-main {
            display:grid;
            grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);
            gap:9px;
            align-items:center;
        }
        .ff-team {
            min-width:0;
            font-size:14px;
            line-height:1.15;
            font-weight:600;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
        }
        .ff-team:last-child { text-align:right; }
        .ff-team.selected { font-weight:800; color:#fff; }
        .ff-score {
            min-width:58px;
            padding:7px 8px;
            border-radius:9px;
            background:rgba(255,255,255,.075);
            text-align:center;
            font-size:15px;
            line-height:1;
            font-weight:800;
            font-variant-numeric:tabular-nums;
        }
        .ff-score.upcoming { font-size:11px; letter-spacing:.08em; text-transform:uppercase; opacity:.75; }
        .ff-meta {
            display:flex;
            justify-content:space-between;
            align-items:center;
            gap:10px;
            margin-top:10px;
            font-size:11px;
            opacity:.56;
        }
        .ff-result { font-weight:800; }
        .ff-result.win { color:#92e0b4; }
        .ff-result.draw { color:#d7d7da; }
        .ff-result.loss { color:#f1a1a1; }
        .ff-empty { font-size:13px; opacity:.54; padding-top:7px; }
        .ff-error { grid-column:1/-1; text-align:center; padding:11px 14px; font-size:12px; opacity:.6; }
        @media (max-width:900px) {
            .form-fixtures-strip { grid-template-columns:1fr 1fr; }
            .ff-form-card { grid-column:1/-1; }
        }
        @media (max-width:620px) {
            .form-fixtures-strip { grid-template-columns:1fr; }
            .ff-form-card { grid-column:auto; }
            .ff-card { min-height:auto; }
        }
    `;
    document.head.appendChild(style);

    const strip = document.createElement('section');
    strip.className = 'form-fixtures-strip';
    strip.id = 'form-fixtures-strip';
    strip.setAttribute('aria-label', 'Championship form and fixtures');
    tabs.parentNode.insertBefore(strip, tabs);

    let dataPromise = null;

    function selectedTeamKey() {
        return document.querySelector('#team-dropdown .dropdown-item.active')?.dataset?.value || 'west-ham';
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function formatDate(raw, includeWeekday = false) {
        if (!raw) return 'Date TBC';
        const date = new Date(`${raw}T12:00:00`);
        if (Number.isNaN(date.getTime())) return raw;
        return new Intl.DateTimeFormat('en-GB', {
            weekday: includeWeekday ? 'short' : undefined,
            day: 'numeric', month: 'short', year: includeWeekday ? undefined : 'numeric'
        }).format(date);
    }

    function resultFor(teamKey, fixture) {
        if (!fixture || fixture.home_score == null || fixture.away_score == null) return null;
        const isHome = fixture.home_key === teamKey;
        const ours = isHome ? fixture.home_score : fixture.away_score;
        const theirs = isHome ? fixture.away_score : fixture.home_score;
        if (ours > theirs) return 'W';
        if (ours < theirs) return 'L';
        return 'D';
    }

    function resultClass(result) {
        return result === 'W' ? 'win' : result === 'L' ? 'loss' : 'draw';
    }

    function resultWord(result) {
        return result === 'W' ? 'Win' : result === 'L' ? 'Loss' : 'Draw';
    }

    function fixtureMarkup(teamKey, fixture, isNext) {
        if (!fixture) {
            return `<div class="ff-empty">${isNext ? 'Next Championship fixture not available yet.' : 'No completed Championship match yet.'}</div>`;
        }
        const result = isNext ? null : resultFor(teamKey, fixture);
        const homeSelected = fixture.home_key === teamKey;
        const awaySelected = fixture.away_key === teamKey;
        const score = isNext ? 'VS' : `${fixture.home_score}–${fixture.away_score}`;
        const time = fixture.time && fixture.time !== '00:00' ? fixture.time : 'Time TBC';
        const venue = homeSelected ? 'Home' : awaySelected ? 'Away' : '';
        return `
            <div class="ff-fixture-main">
                <div class="ff-team${homeSelected ? ' selected' : ''}">${escapeHtml(fixture.home)}</div>
                <div class="ff-score${isNext ? ' upcoming' : ''}">${escapeHtml(score)}</div>
                <div class="ff-team${awaySelected ? ' selected' : ''}">${escapeHtml(fixture.away)}</div>
            </div>
            <div class="ff-meta">
                <span>${escapeHtml(formatDate(fixture.date, isNext))}${isNext ? ` · ${escapeHtml(time)}` : ''}</span>
                <span>${escapeHtml(venue)}${result ? ` · <strong class="ff-result ${resultClass(result)}">${resultWord(result)}</strong>` : ''}</span>
            </div>`;
    }

    function formMarkup(form) {
        const recent = Array.isArray(form) ? form.slice(-5) : [];
        const padded = [...Array(Math.max(0, 5 - recent.length)).fill(null), ...recent];
        return padded.map(item => item
            ? `<span class="ff-form-badge ${resultClass(item.result)}" title="${escapeHtml(item.venue)} vs ${escapeHtml(item.opponent)}">${escapeHtml(item.result)}</span>`
            : '<span class="ff-form-badge empty">–</span>'
        ).join('');
    }

    async function loadData(force = false) {
        if (!dataPromise || force) {
            dataPromise = fetch('/api/form-fixtures', { cache: force ? 'no-store' : 'default' }).then(async response => {
                const data = await response.json();
                if (!response.ok || data.error) throw new Error(data.error || `Request failed (${response.status})`);
                return data;
            });
        }
        return dataPromise;
    }

    async function render(force = false) {
        strip.innerHTML = '<div class="ff-error">Loading Championship form and fixtures…</div>';
        try {
            const data = await loadData(force);
            const teamKey = selectedTeamKey();
            const team = data.teams?.[teamKey];
            if (!team) throw new Error('Form and fixture data is not available for this club.');
            strip.innerHTML = `
                <div class="ff-card ff-form-card">
                    <div class="ff-label">Championship form</div>
                    <div class="ff-form-badges">${formMarkup(team.form)}</div>
                    <div class="ff-form-note">Last five league matches · newest on the right</div>
                </div>
                <div class="ff-card">
                    <div class="ff-label">Last match</div>
                    ${fixtureMarkup(teamKey, team.last_match, false)}
                </div>
                <div class="ff-card">
                    <div class="ff-label">Next match</div>
                    ${fixtureMarkup(teamKey, team.next_match, true)}
                </div>`;
        } catch (error) {
            strip.innerHTML = `<div class="ff-error">${escapeHtml(error.message || 'Unable to load form and fixtures.')}</div>`;
        }
        updateVisibility();
    }

    function updateVisibility() {
        const compareActive = document.querySelector('.tab-btn.tab-compare.active');
        strip.classList.toggle('hidden', Boolean(compareActive));
    }

    document.addEventListener('click', event => {
        if (event.target.closest('#team-dropdown .dropdown-item')) {
            setTimeout(() => render(false), 0);
        }
        if (event.target.closest('.tab-btn')) {
            setTimeout(updateVisibility, 0);
        }
    });

    document.getElementById('refresh-btn')?.addEventListener('click', () => {
        setTimeout(() => render(true), 0);
    });

    new MutationObserver(() => render(false)).observe(selectedTeamNameEl, {
        childList: true, characterData: true, subtree: true
    });

    render(false);
})();
