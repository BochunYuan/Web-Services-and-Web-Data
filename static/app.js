/* ── F1 Analytics API — Frontend ──────────────────────── */

const API = window.__API_BASE_PREFIX__ || '/api/v1';

// ─────────────────────────────────────────────────────────
// Utility helpers
// ─────────────────────────────────────────────────────────

async function apiFetch(path, params = {}) {
  const url = new URL(API + path, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (Array.isArray(v)) v.forEach(vi => url.searchParams.append(k, vi));
    else if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, v);
  });
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function show(id)  { document.getElementById(id)?.classList.remove('hidden'); }
function hide(id)  { document.getElementById(id)?.classList.add('hidden'); }
function el(id)    { return document.getElementById(id); }
function set(id, html) { const e = el(id); if (e) e.innerHTML = html; }

function medal(i) {
  return ['🥇','🥈','🥉'][i] ?? `${i+1}.`;
}

function flagEmoji(nat) {
  const flags = {
    British: '🇬🇧', German: '🇩🇪', Finnish: '🇫🇮', French: '🇫🇷',
    Italian: '🇮🇹', Brazilian: '🇧🇷', Austrian: '🇦🇹', Dutch: '🇳🇱',
    Spanish: '🇪🇸', Australian: '🇦🇺', American: '🇺🇸', Canadian: '🇨🇦',
    Mexican: '🇲🇽', Japanese: '🇯🇵', Monegasque: '🇲🇨', Danish: '🇩🇰',
    Thai: '🇹🇭', Chinese: '🇨🇳', Swiss: '🇨🇭', New_Zealander: '🇳🇿',
    Argentine: '🇦🇷', South_African: '🇿🇦', Belgian: '🇧🇪',
  };
  return flags[nat?.replace(/ /g,'_')] ?? '🏁';
}

// ─────────────────────────────────────────────────────────
// Driver Search
// ─────────────────────────────────────────────────────────

async function searchDrivers() {
  const q = el('searchInput').value.trim();
  if (!q) return;

  hide('driverGrid'); hide('searchEmpty');
  show('searchLoading');

  try {
    const data = await apiFetch('/drivers', { search: q, limit: 24 });
    hide('searchLoading');

    if (!data.items.length) { show('searchEmpty'); return; }

    const html = data.items.map(d => `
      <div class="driver-card" onclick="openDriver(${d.id})">
        ${d.code ? `<span class="dc-code">${d.code}</span>` : ''}
        <div class="dc-name">${d.forename} ${d.surname}</div>
        <div class="dc-nat">${flagEmoji(d.nationality)} ${d.nationality ?? '—'}</div>
        ${d.driver_number ? `<div class="dc-num">#${d.driver_number}</div>` : ''}
      </div>
    `).join('');

    el('driverGrid').innerHTML = html;
    show('driverGrid');
  } catch(e) {
    hide('searchLoading');
    el('driverGrid').innerHTML = `<p class="error-msg">Error: ${e.message}</p>`;
    show('driverGrid');
  }
}

// Enter key triggers search
el('searchInput')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') searchDrivers();
});
el('searchBtn')?.addEventListener('click', searchDrivers);

// ─────────────────────────────────────────────────────────
// Driver Detail
// ─────────────────────────────────────────────────────────

async function openDriver(id) {
  // Show detail panel, hide explore results
  show('driverDetail');
  el('driverDetail').scrollIntoView({ behavior: 'smooth', block: 'start' });

  set('detailHeader', '<div class="spinner" style="margin:32px auto"></div>');
  set('performanceGrid', '');
  set('resultsTable', '');

  // Reset tabs
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelector('[data-tab="performance"]')?.classList.add('active');
  show('tabPerformance'); hide('tabResults');

  try {
    // Parallel: driver info + career performance
    const [driver, perf] = await Promise.all([
      apiFetch(`/drivers/${id}`),
      apiFetch(`/analytics/drivers/${id}/performance`),
    ]);

    renderDetailHeader(driver, perf.career_summary);
    renderPerformance(perf.seasons);

    // Lazy-load recent results when tab is clicked
    el('tabResults')._driverId = id;

  } catch(e) {
    set('detailHeader', `<p class="error-msg">Failed to load driver: ${e.message}</p>`);
  }
}

function renderDetailHeader(driver, summary) {
  const code = driver.code ?? driver.driver_ref?.slice(0,3).toUpperCase() ?? '?';
  set('detailHeader', `
    <div class="dh-badge">${code}</div>
    <div class="dh-info">
      <div class="dh-name">${driver.forename} ${driver.surname}</div>
      <div class="dh-meta">
        ${flagEmoji(driver.nationality)} ${driver.nationality ?? '—'}
        ${driver.driver_number ? ` · #${driver.driver_number}` : ''}
        ${driver.dob ? ` · Born ${driver.dob}` : ''}
      </div>
      <div class="dh-stats">
        <div class="dh-stat">
          <span class="dh-stat-n" style="color:var(--gold)">${summary?.total_wins ?? 0}</span>
          <span class="dh-stat-l">Wins</span>
        </div>
        <div class="dh-stat">
          <span class="dh-stat-n">${summary?.total_podiums ?? 0}</span>
          <span class="dh-stat-l">Podiums</span>
        </div>
        <div class="dh-stat">
          <span class="dh-stat-n">${summary?.total_points?.toLocaleString() ?? 0}</span>
          <span class="dh-stat-l">Points</span>
        </div>
        <div class="dh-stat">
          <span class="dh-stat-n">${summary?.total_races ?? 0}</span>
          <span class="dh-stat-l">Races</span>
        </div>
        <div class="dh-stat">
          <span class="dh-stat-n">${summary?.total_seasons ?? 0}</span>
          <span class="dh-stat-l">Seasons</span>
        </div>
      </div>
    </div>
  `);
}

function renderPerformance(seasons) {
  if (!seasons.length) {
    set('performanceGrid', '<p style="color:var(--text2)">No season data available.</p>');
    return;
  }
  const maxPts = Math.max(...seasons.map(s => s.total_points));
  const html = seasons.map(s => `
    <div class="perf-card" style="--accent:${s.wins > 0 ? 'var(--gold)' : 'var(--border2)'}">
      <div class="perf-year">${s.year}</div>
      <div class="perf-pts">${s.total_points.toFixed(1)}</div>
      <div class="perf-pts-l">points</div>
      <div class="perf-row">
        <span class="${s.wins > 0 ? 'perf-win' : ''}">${s.wins}W</span>
        <span>${s.podiums}P</span>
        <span>${s.dnfs} DNF</span>
      </div>
      <div style="margin-top:8px;height:3px;background:var(--bg);border-radius:99px;overflow:hidden">
        <div style="width:${(s.total_points/maxPts)*100}%;height:100%;background:var(--red);border-radius:99px"></div>
      </div>
    </div>
  `).join('');
  set('performanceGrid', html);
}

async function loadDriverResults(driverId) {
  set('resultsTable', '<div class="spinner" style="margin:32px auto"></div>');
  try {
    const data = await apiFetch('/results', { driver_id: driverId, limit: 30 });
    if (!data.items.length) {
      set('resultsTable', '<p style="color:var(--text2)">No results found.</p>');
      return;
    }
    const rows = data.items.map(r => {
      let posBadge;
      if (r.position === 1) posBadge = `<span class="pos-badge pos-1">1</span>`;
      else if (r.position === 2) posBadge = `<span class="pos-badge pos-2">2</span>`;
      else if (r.position === 3) posBadge = `<span class="pos-badge pos-3">3</span>`;
      else if (r.position === null) posBadge = `<span class="pos-badge pos-dnf">DNF</span>`;
      else posBadge = `<span class="pos-badge pos-n">${r.position}</span>`;

      return `<tr>
        <td>${posBadge}</td>
        <td>${r.race_id}</td>
        <td><span class="pts-pill">${r.points}</span></td>
        <td style="color:var(--text2)">${r.laps ?? '—'}</td>
        <td style="color:var(--text3);font-size:0.8rem">${r.status ?? '—'}</td>
      </tr>`;
    }).join('');

    set('resultsTable', `
      <table class="results-table">
        <thead><tr>
          <th>Pos</th><th>Race ID</th><th>Points</th><th>Laps</th><th>Status</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `);
  } catch(e) {
    set('resultsTable', `<p class="error-msg">Error: ${e.message}</p>`);
  }
}

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const which = tab.dataset.tab;
    if (which === 'performance') {
      show('tabPerformance'); hide('tabResults');
    } else {
      hide('tabPerformance'); show('tabResults');
      const driverId = el('tabResults')._driverId;
      if (driverId && !el('tabResults')._loaded) {
        el('tabResults')._loaded = true;
        loadDriverResults(driverId);
      }
    }
  });
});

// Back button
el('backBtn')?.addEventListener('click', () => {
  hide('driverDetail');
  show('driverGrid');
});

// ─────────────────────────────────────────────────────────
// Analytics: Season Highlights
// ─────────────────────────────────────────────────────────

window.loadSeasonHighlights = async function() {
  const year = el('seasonYear').value;
  const res = el('seasonResult');
  res.innerHTML = '<div class="spinner" style="margin:8px auto"></div>';
  show('seasonResult');
  try {
    const d = await apiFetch(`/analytics/seasons/${year}/highlights`);
    res.innerHTML = `
      <div class="res-champion">
        <div class="res-row">
          <div>
            <div class="res-label">Driver Champion 🏆</div>
            <div class="res-value">${d.champion_driver?.name ?? '—'}</div>
          </div>
          <div class="res-pts">${d.champion_driver?.points?.toFixed(1) ?? ''} pts</div>
        </div>
        <div class="res-row">
          <div>
            <div class="res-label">Constructor Champion</div>
            <div class="res-value">${d.champion_constructor?.name ?? '—'}</div>
          </div>
          <div class="res-pts">${d.champion_constructor?.points?.toFixed(1) ?? ''} pts</div>
        </div>
        <div class="res-row">
          <div class="res-label">Most wins</div>
          <div class="res-value">${d.most_race_wins?.driver ?? '—'} — ${d.most_race_wins?.wins ?? 0} wins</div>
        </div>
        <div class="res-row">
          <div class="res-label">Races · Unique winners</div>
          <div class="res-value">${d.total_races} races · ${d.unique_race_winners} winners</div>
        </div>
      </div>
    `;
  } catch(e) {
    res.innerHTML = `<p class="error-msg">${e.message}</p>`;
  }
};

// ─────────────────────────────────────────────────────────
// Analytics: Constructor Standings
// ─────────────────────────────────────────────────────────

window.loadStandings = async function() {
  const year = el('standingsYear').value;
  const res = el('standingsResult');
  res.innerHTML = '<div class="spinner" style="margin:8px auto"></div>';
  show('standingsResult');
  try {
    const d = await apiFetch(`/analytics/teams/standings/${year}`);
    const rows = d.standings.slice(0,10).map(t => `
      <div class="standings-row">
        <span class="st-pos">${t.position}</span>
        <span class="st-name">${t.team_name}</span>
        <span class="st-wins">${t.wins}W</span>
        <span class="st-pts">${t.total_points.toFixed(1)}</span>
      </div>
    `).join('');
    res.innerHTML = `<div class="standings-list">${rows}</div>`;
  } catch(e) {
    res.innerHTML = `<p class="error-msg">${e.message}</p>`;
  }
};

// ─────────────────────────────────────────────────────────
// Analytics: Driver Comparison
// ─────────────────────────────────────────────────────────

window.loadComparison = async function() {
  const ids = el('compareIds').value.split(',').map(s => s.trim()).filter(Boolean);
  const res = el('compareResult');
  res.innerHTML = '<div class="spinner" style="margin:8px auto"></div>';
  show('compareResult');
  try {
    const params = ids.map(id => ['driver_ids', id]);
    const url = new URL(API + '/analytics/drivers/compare', window.location.origin);
    params.forEach(([k,v]) => url.searchParams.append(k, v));
    const r = await fetch(url);
    if (!r.ok) throw new Error((await r.json()).detail ?? `HTTP ${r.status}`);
    const d = await r.json();

    const maxWins = Math.max(...d.comparisons.map(c => c.stats.wins));
    const rows = d.comparisons.map(c => `
      <div class="cmp-row">
        <div class="cmp-name">${c.driver.name} ${flagEmoji(c.driver.nationality)}</div>
        <div class="cmp-stats">
          <div class="cmp-stat">
            <span class="cmp-stat-n" style="color:var(--gold)">${c.stats.wins}</span>
            <span class="cmp-stat-l">Wins</span>
          </div>
          <div class="cmp-stat">
            <span class="cmp-stat-n">${c.stats.podiums}</span>
            <span class="cmp-stat-l">Podiums</span>
          </div>
          <div class="cmp-stat">
            <span class="cmp-stat-n">${c.stats.total_points.toFixed(0)}</span>
            <span class="cmp-stat-l">Points</span>
          </div>
          <div class="cmp-stat">
            <span class="cmp-stat-n">${c.stats.win_rate_pct}%</span>
            <span class="cmp-stat-l">Win Rate</span>
          </div>
          <div class="cmp-stat">
            <span class="cmp-stat-n">${c.stats.points_per_race}</span>
            <span class="cmp-stat-l">Pts/Race</span>
          </div>
        </div>
      </div>
    `).join('');
    res.innerHTML = `<div class="compare-list">${rows}</div>`;
  } catch(e) {
    res.innerHTML = `<p class="error-msg">${e.message}</p>`;
  }
};

// ─────────────────────────────────────────────────────────
// Analytics: Head-to-Head
// ─────────────────────────────────────────────────────────

window.loadH2H = async function() {
  const a = el('h2hDriver').value;
  const b = el('h2hRival').value;
  const res = el('h2hResult');
  res.innerHTML = '<div class="spinner" style="margin:8px auto"></div>';
  show('h2hResult');
  try {
    const d = await apiFetch(`/analytics/drivers/${a}/head-to-head/${b}`);
    const pctA = d.head_to_head.driver_win_pct;
    const pctB = d.head_to_head.rival_win_pct;
    res.innerHTML = `
      <div class="h2h-wrap">
        <div class="h2h-names">
          <span>${d.driver.name}</span>
          <span>${d.rival.name}</span>
        </div>
        <div class="h2h-bar-wrap">
          <div class="h2h-bar-a" style="width:${pctA}%"></div>
        </div>
        <div class="h2h-pcts">
          <span style="color:var(--red)">${pctA}% (${d.head_to_head.driver_wins}W)</span>
          <span>${pctB}% (${d.head_to_head.rival_wins}W)</span>
        </div>
        <div class="h2h-meta">
          <span>${d.shared_races} shared races</span>
          <span>${d.points_in_shared_races.driver_points.toFixed(1)} vs ${d.points_in_shared_races.rival_points.toFixed(1)} pts</span>
        </div>
      </div>
    `;
  } catch(e) {
    res.innerHTML = `<p class="error-msg">${e.message}</p>`;
  }
};

// ─────────────────────────────────────────────────────────
// Analytics: Circuit Stats
// ─────────────────────────────────────────────────────────

window.loadCircuit = async function() {
  const id = el('circuitId').value;
  const res = el('circuitResult');
  res.innerHTML = '<div class="spinner" style="margin:8px auto"></div>';
  show('circuitResult');
  try {
    const d = await apiFetch(`/analytics/circuits/${id}/stats`);
    const winners = (d.top_winners ?? []).slice(0,5).map((w, i) => `
      <div class="winner-row">
        <span class="winner-medal">${medal(i)}</span>
        <span class="winner-name">${w.driver}</span>
        <span class="winner-wins">${w.wins} wins</span>
      </div>
    `).join('');
    res.innerHTML = `
      <div class="circuit-wrap">
        <div class="circuit-name">${d.circuit.name}</div>
        <div class="circuit-meta">
          ${flagEmoji(d.circuit.country)} ${d.circuit.location ?? ''}, ${d.circuit.country ?? ''}
          · ${d.total_races_hosted} races (${d.first_race_year}–${d.last_race_year})
        </div>
        ${d.most_successful_constructor ? `
        <div class="res-row" style="margin-top:4px">
          <div class="res-label">Best constructor</div>
          <div class="res-value">${d.most_successful_constructor.name} — ${d.most_successful_constructor.wins} wins</div>
        </div>` : ''}
        <div class="res-label" style="margin-top:8px">Top winners</div>
        <div class="winners-list">${winners}</div>
      </div>
    `;
  } catch(e) {
    res.innerHTML = `<p class="error-msg">${e.message}</p>`;
  }
};

// ─────────────────────────────────────────────────────────
// Analytics: Driver Performance (mini)
// ─────────────────────────────────────────────────────────

window.loadPerformance = async function() {
  const id = el('perfDriver').value;
  const start = el('perfStart').value;
  const end = el('perfEnd').value;
  const res = el('perfResult');
  res.innerHTML = '<div class="spinner" style="margin:8px auto"></div>';
  show('perfResult');
  try {
    const d = await apiFetch(`/analytics/drivers/${id}/performance`, {
      start_year: start, end_year: end,
    });
    const maxPts = Math.max(...d.seasons.map(s => s.total_points), 1);
    const rows = d.seasons.map(s => `
      <div class="perf-mini-row">
        <span class="pm-year">${s.year}</span>
        <span class="pm-pts">${s.total_points.toFixed(1)}</span>
        <span class="pm-wins">${s.wins}W · ${s.podiums}P</span>
        <div class="pm-bar-wrap">
          <div class="pm-bar" style="width:${(s.total_points/maxPts)*100}%"></div>
        </div>
      </div>
    `).join('');

    const s = d.career_summary;
    res.innerHTML = `
      <div style="margin-bottom:10px;font-size:0.82rem;color:var(--text2)">
        <strong style="color:var(--text)">${d.driver.name}</strong>
        · ${s.total_wins} wins · ${s.total_podiums} podiums · ${s.total_points.toFixed(1)} pts
      </div>
      <div class="perf-mini-grid">${rows}</div>
    `;
  } catch(e) {
    res.innerHTML = `<p class="error-msg">${e.message}</p>`;
  }
};

// ─────────────────────────────────────────────────────────
// Auto-load defaults on page ready
// ─────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Pre-load 2023 highlights silently so the card feels instant
  setTimeout(() => {
    loadSeasonHighlights();
    loadStandings();
  }, 300);
});
