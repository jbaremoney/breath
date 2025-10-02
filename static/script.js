// Load data on page load
document.addEventListener('DOMContentLoaded', function() {
    loadLeaderboard();
    loadRecentReading();
    
    // Refresh data every 3 seconds
    setInterval(() => {
        loadLeaderboard();
        loadRecentReading();
    }, 3000);
});

document.addEventListener("DOMContentLoaded", () => {
  const readyBtn = document.getElementById("readyBtn");
  const form = document.getElementById("form");

  readyBtn.addEventListener("click", () => {
    const isOpen = form.classList.toggle("open"); // toggles .open on/off
    readyBtn.setAttribute("aria-expanded", isOpen);
  });
});

async function checkStatus() {
    const statusEl = document.getElementById('status');
    const formEl = document.getElementById('form');
    const readyBtn = document.getElementById('readyBtn');
    
    // Clear previous status classes
    statusEl.className = '';
    
    statusEl.textContent = 'Checking...';
    readyBtn.disabled = true;
    
    try {
        const res = await fetch('/status');
        const text = await res.text();
        
        if (text.includes('READY')) {
            statusEl.textContent = "✅ Ready! Please enter your name.";
            statusEl.className = 'status-ready';
            formEl.classList.remove('hidden');
        } else if (text.includes('WAIT')) {
            // Extract wait time from status message
            const match = text.match(/(\d+) min ago/);
            if (match) {
                const minutesAgo = parseInt(match[1]);
                const waitTime = Math.max(0, 15 - minutesAgo);
                if (waitTime > 0) {
                    statusEl.textContent = `⏳ Please wait ${waitTime} more minute${waitTime === 1 ? '' : 's'} before next reading.`;
                } else {
                    statusEl.textContent = "✅ Ready! Please enter your name.";
                    statusEl.className = 'status-ready';
                    formEl.classList.remove('hidden');
                }
            } else {
                statusEl.textContent = `⏳ ${text}`;
            }
            statusEl.className = 'status-wait';
            formEl.classList.add('hidden');
        } else {
            statusEl.textContent = `⏳ ${text}`;
            statusEl.className = 'status-wait';
            formEl.classList.add('hidden');
        }
    } catch (error) {
        statusEl.textContent = '❌ Error checking status';
        statusEl.className = 'status-error';
        formEl.classList.add('hidden');
    } finally {
        readyBtn.disabled = false;
    }
}

// async function loadLeaderboard() {
//     const leaderboardEl = document.getElementById('leaderboard');
    
//     try {
//         const res = await fetch('/leaderboard');
//         const html = await res.text();
        
//         // Extract table from HTML response
//         const parser = new DOMParser();
//         const doc = parser.parseFromString(html, 'text/html');
//         const table = doc.querySelector('table');
        
//         if (table) {
//             leaderboardEl.innerHTML = table.outerHTML;
//         } else {
//             leaderboardEl.innerHTML = '<p>No readings yet</p>';
//         }
//     } catch (error) {
//         leaderboardEl.innerHTML = '<p>Error loading leaderboard</p>';
//     }
// }

async function loadLeaderboard() {
  const mount = document.getElementById('leaderboard');
  mount.innerHTML = 'Loading...';

  try {
    const res = await fetch('/leaderboard', { cache: 'no-store' });
    const html = await res.text();

    mount.innerHTML = renderKahootLeaderboard(html); // ⬅️ render custom layout
  } catch (e) {
    mount.innerHTML = '<p class="muted">Error loading leaderboard.</p>';
  }
}

// Parse the server’s HTML table and render podium + rest
function renderKahootLeaderboard(html) {
  // Parse the HTML string
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const table = doc.querySelector('table');
  if (!table) return '<p class="muted">No readings yet.</p>';

  // Get header labels & rows
  const headers = Array.from(table.querySelectorAll('thead th, tr:first-child th')).map(h => h.textContent.trim().toLowerCase());
  const rows = Array.from(table.querySelectorAll('tbody tr, table tr')).filter(r => r.querySelectorAll('td').length);

  // Heuristics: find columns for name and bac
  let nameCol = headers.findIndex(h => /name/i.test(h));
  let bacCol  = headers.findIndex(h => /\bbac\b/i.test(h) || /blood|alcohol/i.test(h));
  if (nameCol === -1) nameCol = 0;
  if (bacCol  === -1) bacCol  = 1;

  // Extract data in order (assuming server already sorted)
  const data = rows.map(r => {
    const tds = r.querySelectorAll('td');
    const name = (tds[nameCol]?.textContent || '').trim();
    const bacRaw = (tds[bacCol]?.textContent || '').trim();
    const bacNum = parseFloat(bacRaw.replace('%','')) || 0;
    return { name, bacRaw, bacNum };
  }).filter(d => d.name);

  if (!data.length) return '<p class="muted">No readings yet.</p>';

  const top3 = data.slice(0, 3);
  const rest = data.slice(3, 10); // ⬅️ was (3, 6)

  // Build podium HTML
  const podium = `
    <section class="podium">
      ${[2,0,1].map((idx,col) => { // order: #2, #1, #3 like Kahoot (center is tallest)
        const item = top3[idx];
        const place = [2,1,3][col]; // labels 2,1,3
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

  // Build small table for 4–6
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

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}


async function loadRecentReading() {
    const bannerEl = document.getElementById('recentBanner');
    const nameEl = document.getElementById('recentName');
    const bacEl = document.getElementById('recentBAC');
    const rankEl = document.getElementById('recentRank');
    
    try {
        const res = await fetch('/recent');
        const data = await res.json();
        
        if (data.name && data.bac > 0) {
            nameEl.textContent = data.name;
            bacEl.textContent = `${data.bac.toFixed(3)}%`;
            rankEl.textContent = `#${data.rank + 1}`;
            bannerEl.classList.remove('hidden');
        } else {
            bannerEl.classList.add('hidden');
        }
    } catch (error) {
        console.error('Error loading recent reading:', error);
        bannerEl.classList.add('hidden');
    }
}

// Handle form submission
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('nameForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(form);
            const name = formData.get('name');
            
            if (!name.trim()) {
                alert('Please enter your name');
                return;
            }
            
            // Submit name to cache
            fetch('/cache-name', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (response.ok) {
                    // Hide form and show success message
                    document.getElementById('form').classList.add('hidden');
                    document.getElementById('status').textContent = '✅ Name cached! Please blow into the breathalyzer now.';
                    document.getElementById('status').className = 'status-ready';
                    
                    // Reset after 5 seconds
                    setTimeout(() => {
                        document.getElementById('status').textContent = '';
                        document.getElementById('status').className = '';
                    }, 5000);
                } else {
                    alert('Error caching name');
                }
            })
            .catch(error => {
                alert('Network error');
            });
        });
    }
});



//test

// ===== QUICK MOCK MODE =====
// Use by opening the page with ?mock=1
const MOCK = new URLSearchParams(location.search).get('mock') === '1';

// Hook into your existing loader:
const _origLoadLeaderboard = (typeof loadLeaderboard === 'function') ? loadLeaderboard : null;
loadLeaderboard = async function() {
  if (!MOCK) return _origLoadLeaderboard && _origLoadLeaderboard();

  const mount = document.getElementById('leaderboard');
  if (!mount) return;
  // Generate 8 fake rows (change count as you like)
  const html = buildMockTableHTML(8);
  // Reuse your existing renderer (from my previous message)
  mount.innerHTML = renderKahootLeaderboard(html);
};

// Optional: mock /recent banner & status flow too
const _origLoadRecent = (typeof loadRecentReading === 'function') ? loadRecentReading : null;
loadRecentReading = async function() {
  if (!MOCK) return _origLoadRecent && _origLoadRecent();
  const top = _mockDataSorted[0];
  if (!top) return;
  document.getElementById('recentName').textContent = top.name;
  document.getElementById('recentBAC').textContent = top.bacRaw;
  document.getElementById('recentRank').textContent = '#1';
  document.getElementById('recentBanner').classList.remove('hidden');
};

const _origCheckStatus = (typeof checkStatus === 'function') ? checkStatus : null;
checkStatus = async function() {
  if (!MOCK) return _origCheckStatus && _origCheckStatus();
  const minutesAgo = Math.floor(Math.random() * 15); // 0..14
  const statusEl = document.getElementById('status');
  const formEl = document.getElementById('form');
  if (minutesAgo >= 15 || Math.random() < 0.5) {
    statusEl.className = 'status-ready';
    statusEl.textContent = '✅ Ready! Enter your name below.';
    formEl.classList.remove('hidden');
  } else {
    statusEl.className = 'status-wait';
    statusEl.textContent = `⏳ WAIT: ${minutesAgo} min ago`;
    formEl.classList.add('hidden');
  }
};

// ===== Helpers to fabricate a server-like <table> =====
const _mockNames = ['Avery','Sam','Jordan','Taylor','Riley','Casey','Alex','Quinn','Morgan','Jamie','Kai','Rowan','Cameron'];
let _mockDataSorted = [];

function buildMockTableHTML(n = 8) {
  const rows = Array.from({ length: n }, () => {
    const name = _mockNames[Math.floor(Math.random() * _mockNames.length)];
    const bacNum = +(Math.random() * 0.12).toFixed(3); // 0.000 .. 0.120
    return { name, bacNum, bacRaw: `${bacNum.toFixed(3)}%` };
  });
  // Sort desc by BAC, like a real leaderboard
  _mockDataSorted = rows.sort((a, b) => b.bacNum - a.bacNum);

  const tr = _mockDataSorted
    .map(r => `<tr><td>${escapeHtml(r.name)}</td><td>${escapeHtml(r.bacRaw)}</td></tr>`)
    .join('');

  return `
    <!doctype html><html><body>
      <table>
        <thead><tr><th>Name</th><th>BAC</th></tr></thead>
        <tbody>${tr}</tbody>
      </table>
    </body></html>`;
}

// If you don't already have escapeHtml available:
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
  ));
}


const formWrap = document.getElementById('form');
const readyBtn = document.getElementById('readyBtn');
const statusEl = document.getElementById('status');
let lastStatus = null; // 'READY' | 'WAIT' | 'ERROR' | null

function setFormOpen(open) {
  if (!formWrap) return;
  formWrap.classList.toggle('open', open);
  readyBtn?.setAttribute('aria-expanded', open ? 'true' : 'false');
}

// Intercept clicks: if already READY, just toggle. Otherwise, check status.
readyBtn?.addEventListener('click', async (e) => {
  if (lastStatus === 'READY') {
    setFormOpen(readyBtn.getAttribute('aria-expanded') !== 'true');
  } else {
    await checkStatus(); // will open if READY, close if WAIT/ERROR
  }
});

// --- Your existing checkStatus, lightly modified ---
async function checkStatus() {
  try {
    statusEl.className = '';
    statusEl.textContent = 'Checking…';
    readyBtn.disabled = true;

    const res = await fetch('/status', { cache: 'no-store' });
    const text = (await res.text()).trim();

    if (text.includes('READY')) {
      lastStatus = 'READY';
      statusEl.className = 'status-ready';
      statusEl.textContent = '✅ Ready! Enter your name below.';
      setFormOpen(true); // open the dropdown
      document.querySelector('#nameForm input[name="name"]')?.focus();
    } else {
      // Parse minutes if present (optional)
      const m = text.match(/(\d+)\s*min\s*ago/i);
      const remaining = m ? Math.max(0, 15 - parseInt(m[1], 10)) : null;

      lastStatus = 'WAIT';
      statusEl.className = 'status-wait';
      statusEl.textContent = remaining != null && remaining > 0
        ? `⏳ Please wait ${remaining} more minute${remaining === 1 ? '' : 's'}.`
        : `⏳ ${text}`;

      setFormOpen(false); // keep closed if not ready
    }
  } catch (err) {
    lastStatus = 'ERROR';
    statusEl.className = 'status-error';
    statusEl.textContent = '❌ Error checking status';
    setFormOpen(false);
  } finally {
    readyBtn.disabled = false;
  }
}
