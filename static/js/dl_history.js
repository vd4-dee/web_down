// dl_history.js
// Chứa toàn bộ logic lịch sử tải tách từ script.js

document.addEventListener('DOMContentLoaded', () => {
    const logTableContainer = document.getElementById('log-table-container');
    const logDataTableBody = document.querySelector("#log-data-table tbody");
    const refreshLogButton = document.getElementById('refresh-log-button');
    const logTableSearchInput = document.getElementById('log-table-search');

    function showNotification(message, type = 'info', duration = 4000) {
        const notificationPopup = document.getElementById('notification');
        const notificationMessage = document.getElementById('notification-message');
        if (!notificationPopup || !notificationMessage) return;
        notificationMessage.textContent = message;
        notificationPopup.className = `notification ${type}`;
        notificationPopup.style.display = 'block';
        setTimeout(() => {
            notificationPopup.style.display = 'none';
        }, duration);
    }

    // --- Log Table Search ---
    if (logTableSearchInput && logDataTableBody) {
        logTableSearchInput.disabled = false;
        logTableSearchInput.addEventListener('input', function() {
            const filter = logTableSearchInput.value.toLowerCase();
            Array.from(logDataTableBody.rows).forEach(row => {
                row.style.display = row.textContent.toLowerCase().includes(filter) ? '' : 'none';
            });
        });
    }

    // --- Refresh Log Button (giả lập) ---
    if (refreshLogButton) {
        refreshLogButton.addEventListener('click', () => {
            showNotification('Logs refreshed.', 'success');
            // Simulate fetch logs
            if (logDataTableBody) logDataTableBody.innerHTML = '<tr><td>2025-04-21</td><td>Download A</td><td>Success</td></tr>';
        });
    }
});
