// static/js/dl_active.js
// Logic for active downloads panel

document.addEventListener('DOMContentLoaded', () => {
    let activeSessions = [];
    let activeSessionsTimer = null;
    const list = document.getElementById('active-downloads-list');

    function renderActiveSessions() {
        if (!list) return;
        if (activeSessions.length === 0) {
            list.innerHTML = '<tr><td colspan="4" class="subtext">No active downloads.</td></tr>';
            return;
        }
        list.innerHTML = '';
        activeSessions.forEach((session, idx) => {
            const elapsed = Math.floor((Date.now() - session.startTime) / 1000);
            const hour = Math.floor(elapsed / 3600).toString().padStart(2, '0');
            const min = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
            const sec = (elapsed % 60).toString().padStart(2, '0');
            const tr = document.createElement('tr');
            tr.className = 'session-row';
            tr.innerHTML = `
                <td><button class="expand-btn" data-idx="${idx}">${session.expanded ? '▼' : '▶'}</button></td>
                <td>${session.sessionId}</td>
                <td>${new Date(session.startTime).toLocaleString()}</td>
                <td>${hour}:${min}:${sec}</td>
            `;
            list.appendChild(tr);
            // Detail row
            const detailTr = document.createElement('tr');
            detailTr.className = 'session-detail-row';
            detailTr.style.display = session.expanded ? '' : 'none';
            detailTr.innerHTML = `<td colspan="4">
                <div class="report-list-detail">
                    <strong>Reports being downloaded:</strong>
                    <table class="data-table report-list-table">
                        <thead><tr><th>Report Name</th><th>From Date</th><th>To Date</th><th>Chunk Size</th></tr></thead>
                        <tbody>
                            ${session.reports && session.reports.length > 0 ? session.reports.map(r => `
                                <tr><td>${r.report_type}</td><td>${r.from_date}</td><td>${r.to_date}</td><td>${r.chunk_size}</td></tr>
                            `).join('') : '<tr><td colspan="4" class="subtext">No reports</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </td>`;
            list.appendChild(detailTr);
        });
        // Add expand/collapse event listeners
        list.querySelectorAll('.expand-btn').forEach(btn => {
            btn.onclick = function() {
                const idx = parseInt(btn.getAttribute('data-idx'));
                activeSessions[idx].expanded = !activeSessions[idx].expanded;
                renderActiveSessions();
            };
        });
    }

    // Dummy: Add a session for demo. Replace with real logic (SSE or polling)
    window.addActiveSession = function(sessionId, startTime, reports) {
        activeSessions.push({ sessionId, startTime, reports, expanded: false });
        renderActiveSessions();
        if (!activeSessionsTimer) {
            activeSessionsTimer = setInterval(renderActiveSessions, 1000);
        }
    };
    window.removeActiveSession = function(sessionId) {
        activeSessions = activeSessions.filter(s => s.sessionId !== sessionId);
        renderActiveSessions();
        if (activeSessions.length === 0 && activeSessionsTimer) {
            clearInterval(activeSessionsTimer);
            activeSessionsTimer = null;
        }
    };
    renderActiveSessions();
});
