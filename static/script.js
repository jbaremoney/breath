// =================== CONFIG / STATE ===================
const POLL_MS = 3000;
let pollId = null;
let firstLeaderboardLoad = true;
let lastLeaderboardHTML = null;
let lastStatus = null; // 'READY' | 'WAIT' | 'ERROR' | null
const MOCK = new URLSearchParams(location.search).get('mock') === '1';

// =================== UTILITIES ===================
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
  ));
}

// =================== DOM READY ===================
document.addEventListener('DOMContentLoaded', () => {
  // Cache elements
  const readyBtn = document.getElementById('readyBtn');
  const formWrap = document.getElementById('form');
  const statusEl = document.getElementById('status');

  // If the form still has "hidden" from old code, convert it to collapsible/closed
  if (formWrap && formWrap.classList.contains('hidden')) {
    formWrap.classList.remove('hidden');
    formWrap.classList.add('collapsible');
  }

  // Button click: if already READY, just toggle; else checkStatus
  readyBtn?.addEventListener('click', async () => {
    if (lastStatus === 'READY') {
      setFormOpen(formWrap, readyBtn, readyBtn.getAttribute('aria-expanded') !== 'true');
    } else {
      await checkStatus(statusEl, formWrap, readyBtn);
    }
  });

  // Initial load + polling
  loadLeaderboard();
  loadRecentReading();
  startPolling();
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopPolling(); else startPolling();
  });
});

// =================== COLLAPSIBLE HELPERS ===================
function setFormOpen(formWrap, readyBtn, open) {
  if (!formWrap) return;
  formWrap.classList.toggle('open', open);
  readyBtn?.setAttribute('aria-expanded', open ? 'true' : 'false');
}

// =================== POLLING ===================
function startPolling() {
  if (pollId) return;
  pollId = setInterval(() => {
    loadLeaderboard();
    loadRecentReading();
  }, POLL_MS);
}
function stopPolling() {
  clearInterval(pollId);
  pollId = null;
}

// =================== STATUS FLOW ===================
async function checkStatus(statusEl, formWrap, readyBtn) {
  try {
    statusEl.className = '';
    statusEl.textContent = 'Checking…';
    readyBtn.disabled = true;

    if (MOCK) {
      // --- mock: randomly ready or wait
      const minutesAgo = Math.floor(Math.random() * 15);
      if (minutesAgo >= 15 || Math.random() < 0.5) {
        lastStatus = 'READY';
        statusEl.className = 'status-ready';
        statusEl.textContent = '✅ Ready! Enter your name below.';
        setFormOpen(formWrap, readyBtn, true);
      } else {
        lastStatus = 'WAIT';
        statusEl.className = 'status-wait';
        statusEl.textContent = `⏳ WAIT: ${minutesAgo} min ago`;
        setFormOpen(formWrap, readyBtn, false);
      }
      return;
    }

    const res = await fetch('/status', { cache: 'no-store' });
    const text = (await res.text()).trim();

    if (text.includes('READY')) {
      lastStatus = 'READY';
      statusEl.className = 'status-ready';
      statusEl.textContent = '✅ Ready! Enter your name below.';
      setFormOpen(formWrap, readyBtn, true);
      document.querySelector('#nameForm input[name="name"]')?.focus();
    } else {
      const m = text.match(/(\d+)\s*min\s*ago/i);
      const remaining = m ? Math.max(0, 15 - parseInt(m[1], 10)) : null;

      lastStatus = 'WAIT';
      statusEl.className = 'status-wait';
      statusEl.textContent = remaining != null && remaining > 0
        ? `⏳ Please wait ${remaining} more minute${remaining === 1 ? '' : 's'}.`
        : `⏳ ${text}`;

      setFormOpen(formWrap, readyBtn, false);
    }
  } catch (err) {
    lastStatus = 'ERROR';
    statusEl.className = 'status-error';
    statusEl.textContent = '❌ Error checking status';
    setFormOpen(formWrap, readyBtn, false);
  } finally {
    readyBtn.disabled = false;
  }
}

// =================== LEADERBOARD ===================
async function loadLeaderboard() {
  const mount = document.getElementById('leaderboard');
  if (!mount) return;

  if (firstLeaderboardLoad) mount.textContent = 'Loading...';

  try {
    let html;
    if (MOCK) {
      html = buildMockTableHTML(10);
    } else {
      const res = await fetch('/leaderboard', { cache: 'no-store' });
      html = await res.text();
    }

    const next = renderKahootLeaderboard(html);
    if (next !== lastLeaderboardHTML) {
      mount.innerHTML = next;
      lastLeaderboardHTML = next;
    }
  } catch {
    if (firstLeaderboardLoad) mount.innerHTML = '<p class="muted">Error loading leaderboard.</p>';
  } finally {
    firstLeaderboardLoad = false;
  }
}

// Parse the server’s HTML table and render podium + 4–10
function renderKahootLeaderboard(html) {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const table = doc.querySelector('table');
  if (!table) return '<p class="muted">No readings yet.</p>';

  const headers = Array.from(table.querySelectorAll('thead th, tr:first-child th')).map(h => h.textContent.trim().toLowerCase());
  const rows = Array.from(table.querySelectorAll('tbody tr, table tr')).filter(r => r.querySelectorAll('td').length);

  let nameCol = headers.findIndex(h => /name/i.test(h));
  let bacCol  = headers.findIndex(h => /\bbac\b/i.test(h) || /blood|alcohol/i.test(h));
  if (nameCol === -1) nameCol = 0;
  if (bacCol  === -1) bacCol  = 1;

  const data = rows.map(r => {
    const tds = r.querySelectorAll('td');
    const name = (tds[nameCol]?.textContent || '').trim();
    const bacRaw = (tds[bacCol]?.textContent || '').trim();
    const bacNum = parseFloat(bacRaw.replace('%','')) || 0;
    return { name, bacRaw, bacNum };
  }).filter(d => d.name);

  if (!data.length) return '<p class="muted">No readings yet.</p>';

  const top3 = data.slice(0, 3);
  const rest = data.slice(3, 10); // 4–10

  const podium = `
    <section class="podium">
      ${[2,0,1].map((idx,col) => {
        const item = top3[idx];
        const place = [2,1,3][col];
        if (!item) return `<article class="podium-item placeholder"></article>`;
        return `
          <article class="podium-item place-${place}">
            <div class="medal">${place}</div>
            <div class="podium-name">${escapeHtml(item.name)}</div>
            <div class="podium-bac">${escapeHtml(item.bacRaw)}</div>
          </article>
        `;
      }).join('')}
    </section>
  `;

  const lower = `
    <div class="lower-board">
      <table class="lower-table">
        <thead><tr><th>Rank</th><th>Name</th><th>BAC</th></tr></thead>
        <tbody>
          ${rest.map((r, i) => `
            <tr>
              <td>${i + 4}</td>
              <td>${escapeHtml(r.name)}</td>
              <td>${escapeHtml(r.bacRaw)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  return podium + lower;
}

// =================== RECENT BANNER (Voltage-preferred) ===================
async function loadRecentReading() {
  const bannerEl = document.getElementById('recentBanner');
  const nameEl = document.getElementById('recentName');
  const bacEl  = document.getElementById('recentBAC');
  const rankEl = document.getElementById('recentRank');

  try {
    let data;
    if (MOCK) {
      // Use top of mock data if present
      data = { name: 'Avery', bac: 0.089, rank: 0, voltage: 1.14 };
    } else {
      const res = await fetch('/recent', { cache: 'no-store' });
      data = await res.json();
    }

    // Accept number or numeric string; support several keys
    const vRaw =
      data.voltage ?? data.volts ?? data.v ??
      (typeof data.mv === 'number' ? data.mv / 1000 : data.mv);

    const vParsed = (vRaw != null)
      ? parseFloat(String(vRaw).replace(/[^\d.+-eE]/g, ''))
      : NaN;

    let metricText = '';
    if (!Number.isNaN(vParsed)) {
      metricText = `${vParsed.toFixed(2)} V`;
    } else if (typeof data.bac === 'number') {
      metricText = `${data.bac.toFixed(3)}%`;
    } else if (data.value != null) {
      metricText = String(data.value);
    }

    if (data.name && metricText) {
      nameEl.textContent = data.name;
      bacEl.textContent = metricText;
      rankEl.textContent = (data.rank != null) ? `#${Number(data.rank) + 1}` : '';
      bannerEl.classList.remove('hidden');
    } else {
      bannerEl.classList.add('hidden');
    }
  } catch (e) {
    console.error('Error loading recent reading:', e);
    bannerEl.classList.add('hidden');
  }
}

// =================== MOCK TABLE (for ?mock=1) ===================
const mockNames = ['Avery','Sam','Jordan','Taylor','Riley','Casey','Alex','Quinn','Morgan','Jamie','Kai','Rowan','Cameron'];
function buildMockTableHTML(n = 10) {
  const rows = Array.from({ length: n }, () => {
    const name = mockNames[Math.floor(Math.random() * mockNames.length)];
    const bacNum = +(Math.random() * 0.12).toFixed(3);
    return { name, bacNum, bacRaw: `${bacNum.toFixed(3)}%` };
  }).sort((a, b) => b.bacNum - a.bacNum);

  const tr = rows.map(r => `<tr><td>${escapeHtml(r.name)}</td><td>${escapeHtml(r.bacRaw)}</td></tr>`).join('');

  return `
    <!doctype html><html><body>
      <table>
        <thead><tr><th>Name</th><th>BAC</th></tr></thead>
        <tbody>${tr}</tbody>
      </table>
    </body></html>`;
}
