// dl_schedule.js
// Chứa toàn bộ logic lịch biểu tải tách từ script.js

document.addEventListener('DOMContentLoaded', () => {
    const scheduleConfigSelect = document.getElementById('schedule-config-select');
    const scheduleDateTimeInput = document.getElementById('schedule-datetime');
    const scheduleButton = document.getElementById('schedule-button');
    const schedulesListBody = document.getElementById('schedules-list');

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

    // --- Schedule Download Event ---
    if (scheduleButton) {
        scheduleButton.addEventListener('click', async () => {
            const config = scheduleConfigSelect.value;
            const datetime = scheduleDateTimeInput.value;
            if (!config || !datetime) {
                showNotification('Please select config and datetime.', 'error');
                return;
            }
            // Simulate schedule
            showNotification(`Scheduled ${config} at ${datetime}`, 'success');
        });
    }

    // --- Fetch and Display Schedules (giả lập) ---
    function fetchAndDisplaySchedules() {
        // Simulate fetch schedules
        schedulesListBody.innerHTML = '<tr><td>Example Job</td><td>2025-04-22 09:00</td><td><button>Cancel</button></td></tr>';
    }
    if (schedulesListBody) fetchAndDisplaySchedules();
});
