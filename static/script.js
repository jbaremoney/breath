// Load leaderboard on page load
document.addEventListener('DOMContentLoaded', function() {
    loadLeaderboard();
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
        
        if (text.includes('OK')) {
            statusEl.textContent = "✅ Ready! Please enter your name.";
            statusEl.className = 'status-ready';
            formEl.classList.remove('hidden');
        } else if (text.includes('min ago')) {
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

async function loadLeaderboard() {
    const leaderboardEl = document.getElementById('leaderboard');
    
    try {
        const res = await fetch('/leaderboard');
        const html = await res.text();
        
        // Extract table from HTML response
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const table = doc.querySelector('table');
        
        if (table) {
            leaderboardEl.innerHTML = table.outerHTML;
        } else {
            leaderboardEl.innerHTML = '<p>No readings yet</p>';
        }
    } catch (error) {
        leaderboardEl.innerHTML = '<p>Error loading leaderboard</p>';
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
            
            // Submit the form
            fetch('/submit', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (response.ok) {
                    alert('Reading submitted successfully!');
                    loadLeaderboard(); // Refresh leaderboard
                    form.reset();
                    document.getElementById('form').classList.add('hidden');
                    document.getElementById('status').textContent = '';
                    document.getElementById('status').className = '';
                } else {
                    alert('Error submitting reading');
                }
            })
            .catch(error => {
                alert('Network error');
            });
        });
    }
});
