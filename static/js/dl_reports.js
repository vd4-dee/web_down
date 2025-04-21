// dl_reports.js
// Chứa toàn bộ logic download, config, report table, trạng thái download, và config management tách từ script.js

// Import tiện ích chung
document.addEventListener('DOMContentLoaded', function() {
    // Nếu dùng module: import { showNotification, addStatusMessage, clearStatusMessages } from './utils.js';
    // Nếu dùng script thường: các hàm đã được include từ utils.js

    // KHAI BÁO BIẾN DUY NHẤT
    const downloadButton = document.getElementById('download-button');
    const loadingIndicator = document.getElementById('loading-indicator');
    const statusMessagesDiv = document.getElementById('status-messages');
    const reportTable = document.getElementById('report-table');
    const addRowBtn = document.getElementById('add-row-button');
    // ... các biến khác nếu cần ...

    // --- Download All Logic ---
    // --- Download All Logic ---
    
    
    

    if (downloadButton) {
        downloadButton.addEventListener('click', async function(e) {
            e.preventDefault();
            clearStatusMessages(statusMessagesDiv);
            addStatusMessage(statusMessagesDiv, 'Gathering data and validating...', 'info');
            if (loadingIndicator) loadingIndicator.style.display = 'inline-block';
            downloadButton.disabled = true;

            // 1. Get Form Data
            const formData = getCurrentFormData();

            // 2. Validate Form Data
            const validationErrors = validateFormData(formData);
            if (validationErrors.length > 0) {
                validationErrors.forEach(err => addStatusMessage(statusMessagesDiv, err, 'error'));
                showNotification('Please fix errors in the form.', 'error');
                if (loadingIndicator) loadingIndicator.style.display = 'none';
                downloadButton.disabled = false;
                return;
            }

            addStatusMessage(statusMessagesDiv, 'Sending download request...', 'info');
            try {
                const response = await fetch('/download/api/start-download', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(formData)
                });
                const result = await response.json();
                if (response.ok && result.status === 'started') {
                    addStatusMessage(statusMessagesDiv, 'Download process initiated. Waiting for status...', 'success');
                    showNotification('Download process initiated.', 'success');
                    // listenToStatusStream(); // Bổ sung nếu có SSE
                } else {
                    const errorMsg = result.message || `Failed to start download (Status: ${response.status})`;
                    addStatusMessage(statusMessagesDiv, errorMsg, 'error');
                    showNotification(errorMsg, 'error');
                    if (loadingIndicator) loadingIndicator.style.display = 'none';
                    downloadButton.disabled = false;
                }
            } catch (error) {
                addStatusMessage(statusMessagesDiv, 'Network or Server Error: ' + error.message, 'error');
                showNotification('Network or Server Error: ' + error.message, 'error');
                if (loadingIndicator) loadingIndicator.style.display = 'none';
                downloadButton.disabled = false;
            }
        });
    }

    // --- Form Data Gathering ---
    function getCurrentFormData() {
        const data = {
            email: document.getElementById('email')?.value || '',
            password: document.getElementById('password')?.value || '',
            reports: [],
            regions: []
        };
        const reportRows = document.querySelectorAll('#report-table tbody tr');
        reportRows.forEach(row => {
            const reportTypeSelect = row.querySelector('select[name="report_type[]"]');
            const fromDateInput = row.querySelector('input[name="from_date[]"]');
            const toDateInput = row.querySelector('input[name="to_date[]"]');
            const chunkSizeInput = row.querySelector('input[name="chunk_size[]"]');
            if (reportTypeSelect && reportTypeSelect.value) {
                data.reports.push({
                    report_type: reportTypeSelect.value,
                    from_date: fromDateInput?.value || '',
                    to_date: toDateInput?.value || '',
                    chunk_size: chunkSizeInput?.value.trim() || '5',
                });
            }
        });
        const regionCheckboxes = document.querySelectorAll('#region-selection input[name="regions"]:checked');
        data.regions = Array.from(regionCheckboxes).map(cb => cb.value);
        return data;
    }

    // --- Form Data Validation ---
    function validateFormData(data) {
        const errors = [];
        if (!data.email) errors.push('Email is required.');
        if (!data.password) errors.push('Password is required.');
        if (!data.reports || data.reports.length === 0) {
            errors.push('Please configure at least one report.');
        } else {
            data.reports.forEach((r, index) => {
                if (!r.report_type) errors.push(`Report type is missing for row ${index + 1}.`);
                if (!r.from_date) errors.push(`From date is missing for row ${index + 1}.`);
                if (!r.to_date) errors.push(`To date is missing for row ${index + 1}.`);
            });
        }
        // Nếu cần validate region, bổ sung tại đây
        return errors;
    }

    // Toggle password visibility
    const passwordInput = document.getElementById('password');
    const togglePasswordBtn = document.getElementById('toggle-password-visibility');
    if (togglePasswordBtn && passwordInput) {
    togglePasswordBtn.addEventListener('click', function() {
        if (passwordInput.type === 'password') {
            passwordInput.type = 'text';
            this.querySelector('i').classList.remove('fa-eye');
            this.querySelector('i').classList.add('fa-eye-slash');
        } else {
            passwordInput.type = 'password';
            this.querySelector('i').classList.remove('fa-eye-slash');
            this.querySelector('i').classList.add('fa-eye');
        }
    });
    }

    // Loading indicator: chỉ hiện khi submit
    const downloadForm = document.getElementById('download-form');
    
    if (downloadForm && loadingIndicator) {
        downloadForm.addEventListener('submit', function(e) {
            loadingIndicator.style.display = 'inline-block';
            // Có thể thêm logic submit AJAX hoặc để form submit bình thường
        });
    }

    // Add Report Row
    
    
    if (addRowBtn && reportTable) {
        addRowBtn.addEventListener('click', function() {
            const tbody = reportTable.querySelector('tbody');
            const firstRow = tbody.querySelector('tr');
            if (firstRow) {
                const newRow = firstRow.cloneNode(true);
                // Reset values
                newRow.querySelectorAll('input, select').forEach(function(input) {
                    if (input.tagName === 'SELECT') input.selectedIndex = 0;
                    else input.value = '';
                if (input.tagName === 'SELECT') input.selectedIndex = 0;
                else input.value = '';
            });
            tbody.appendChild(newRow);
        }
    });
    // Remove row handler (event delegation)
    reportTable.addEventListener('click', function(e) {
        if (e.target.closest('.remove-row-button')) {
            const row = e.target.closest('tr');
            if (row && reportTable.querySelectorAll('tbody tr').length > 1) {
                row.remove();
            }
        }
    });
}

    // Sidebar interaction (nếu sidebar dùng .sidebar-item)
    document.querySelectorAll('#sidebar .sidebar-item').forEach(function(item) {
    item.addEventListener('click', function() {
        document.querySelectorAll('#sidebar .sidebar-item').forEach(i => i.classList.remove('active'));
        this.classList.add('active');
        // Logic chuyển tab, hoặc chuyển trang nếu có href
        const target = this.getAttribute('data-target');
        if (target) {
            document.querySelectorAll('.main-panel').forEach(panel => panel.style.display = 'none');
            const showPanel = document.getElementById(target);
            if (showPanel) showPanel.style.display = 'block';
        }
    });
});


    // --- Element References ---
    const form = document.getElementById('download-form');
    const reportTableBody = document.querySelector("#report-table tbody");
    const addRowButton = document.getElementById('add-row-button');
    const regionSelectionDiv = document.getElementById('region-selection');
    
    
    
    const reportTableSearchInput = document.getElementById('report-table-search');
    const configNameInput = document.getElementById('config-name');
    const saveConfigButton = document.getElementById('save-config-button');
    const savedConfigsDropdown = document.getElementById('saved-configs-dropdown');
    const loadConfigButton = document.getElementById('load-config-button');
    const deleteConfigButton = document.getElementById('delete-config-button');

    // --- Download All Event ---
    if (downloadButton) {
        downloadButton.addEventListener('click', async (e) => {
            e.preventDefault();
            clearStatusMessages(statusMessagesDiv);
            addStatusMessage(statusMessagesDiv, 'Starting download...', 'info');
            try {
                const response = await fetch('/download/api/start-download', { method: 'POST' });
                const result = await response.json();
                if (result.status === 'success') {
                    addStatusMessage(statusMessagesDiv, 'Download started.', 'success');
                    showNotification('Download started.', 'success');
                    listenToStatusStream();
                } else {
                    addStatusMessage(statusMessagesDiv, result.message || 'Failed to start download.', 'error');
                    showNotification(result.message || 'Failed to start download.', 'error');
                }
            } catch (error) {
                addStatusMessage(statusMessagesDiv, 'Error: ' + error.message, 'error');
                showNotification('Error: ' + error.message, 'error');
            }
        });
    }

    // --- Status Stream (SSE) ---
    function listenToStatusStream() {
        if (window.eventSource) window.eventSource.close();
        window.eventSource = new EventSource('/stream-status');
        window.eventSource.onmessage = function(event) {
            addStatusMessage(statusMessagesDiv, event.data, 'log');
        };
        window.eventSource.onerror = function() {
            window.eventSource.close();
        };
    }

    // --- Config Management Events ---
    if (saveConfigButton) {
        saveConfigButton.addEventListener('click', async () => {
            const configName = configNameInput.value.trim();
            if (!configName) {
                showNotification('Please enter a configuration name.', 'error');
                return;
            }
            // Simulate save config
            showNotification('Config saved: ' + configName, 'success');
        });
    }
    if (loadConfigButton) {
        loadConfigButton.addEventListener('click', async () => {
            const selected = savedConfigsDropdown.value;
            if (!selected) {
                showNotification('Select a config to load.', 'error');
                return;
            }
            // Simulate load config
            showNotification('Config loaded: ' + selected, 'success');
        });
    }
    if (deleteConfigButton) {
        deleteConfigButton.addEventListener('click', async () => {
            const selected = savedConfigsDropdown.value;
            if (!selected) {
                showNotification('Select a config to delete.', 'error');
                return;
            }
            // Simulate delete config
            showNotification('Config deleted: ' + selected, 'success');
        });
    }

    // --- Report Table Search ---
    if (reportTableSearchInput && reportTableBody) {
        reportTableSearchInput.disabled = false;
        reportTableSearchInput.addEventListener('input', function() {
            const filter = reportTableSearchInput.value.toLowerCase();
            Array.from(reportTableBody.rows).forEach(row => {
                row.style.display = row.textContent.toLowerCase().includes(filter) ? '' : 'none';
            });
        });
    }

    // --- Initial Page Load Actions ---
    fetchAndPopulateConfigs();

    async function fetchAndPopulateConfigs() {
        if (!savedConfigsDropdown) return;
        savedConfigsDropdown.innerHTML = '<option value="">-- Select Configuration --</option><option disabled>Loading...</option>';
        try {
            const response = await fetch('/api/config/get-configs');
            const result = await response.json();
            if (result.status === 'success' && Array.isArray(result.configs)) {
                savedConfigsDropdown.innerHTML = '<option value="">-- Select Configuration --</option>';
                result.configs.forEach(cfg => {
                    const opt = document.createElement('option');
                    opt.value = cfg;
                    opt.textContent = cfg;
                    savedConfigsDropdown.appendChild(opt);
                });
            } else {
                savedConfigsDropdown.innerHTML = '<option value="">-- Select Configuration --</option><option disabled>Failed to load configs</option>';
            }
        } catch (error) {
            savedConfigsDropdown.innerHTML = '<option value="">-- Select Configuration --</option><option disabled>Failed to load configs</option>';
        }
    }
});