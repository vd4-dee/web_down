// static/js/sc_manage.js
// Logic for schedule management panel
document.addEventListener('DOMContentLoaded', () => {
    const scheduleForm = document.getElementById('schedule-form');
    const scheduleConfigSelect = document.getElementById('schedule-config-select');
    const scheduleDateTimeInput = document.getElementById('schedule-datetime');
    const scheduleButton = document.getElementById('schedule-button');
    const schedulesListBody = document.querySelector('#schedules-list tbody');

    async function fetchAndPopulateConfigs() {
        if (!scheduleConfigSelect) return;
        scheduleConfigSelect.innerHTML = '<option value="">-- Select Configuration --</option><option disabled>Loading...</option>';
        try {
            const response = await fetch('/api/config/get-configs');
            const result = await response.json();
            if (result.status === 'success' && Array.isArray(result.configs)) {
                scheduleConfigSelect.innerHTML = '<option value="">-- Select Configuration --</option>';
                result.configs.forEach(cfg => {
                    const opt = document.createElement('option');
                    opt.value = cfg;
                    opt.textContent = cfg;
                    scheduleConfigSelect.appendChild(opt);
                });
            } else {
                scheduleConfigSelect.innerHTML = '<option value="">-- Select Configuration --</option><option disabled>Failed to load configs</option>';
            }
        } catch (error) {
            scheduleConfigSelect.innerHTML = '<option value="">-- Select Configuration --</option><option disabled>Failed to load configs</option>';
        }
    }

    async function fetchAndDisplaySchedules() {
        // Placeholder: Fetch schedules from backend
        // Replace with real API call
        if (!schedulesListBody) return;
        schedulesListBody.innerHTML = '<tr><td colspan="5" class="subtext">No schedules yet.</td></tr>';
    }

    if (scheduleForm && scheduleButton && scheduleConfigSelect && schedulesListBody) {
        scheduleForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            scheduleButton.disabled = true;
            // Placeholder: Call backend API to schedule job
            await new Promise(resolve => setTimeout(resolve, 1000));
            scheduleButton.disabled = false;
            fetchAndDisplaySchedules();
        });
        fetchAndPopulateConfigs();
        fetchAndDisplaySchedules();
    }
});
