document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('download-form');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const reportTableBody = document.querySelector("#report-table tbody");
    const addRowButton = document.getElementById('add-row-button');
    const reportTable = document.getElementById("report-table");
    const regionSelectionDiv = document.getElementById('region-selection');
    const downloadButton = document.getElementById('download-button');
    const loadingIndicator = document.getElementById('loading-indicator');
    const statusMessagesDiv = document.getElementById('status-messages');
    const logTableContainer = document.getElementById('log-table-container');
    const refreshLogButton = document.getElementById('refresh-log-button');
    const configNameInput = document.getElementById('config-name');
    const saveConfigButton = document.getElementById('save-config-button');
    const savedConfigsDropdown = document.getElementById('saved-configs-dropdown');
    const loadConfigButton = document.getElementById('load-config-button');
    const deleteConfigButton = document.getElementById('delete-config-button');
    const scheduleConfigSelect = document.getElementById('schedule-config-select');
    const scheduleDateTimeInput = document.getElementById('schedule-datetime');
    const scheduleButton = document.getElementById('schedule-button');
    const schedulesList = document.getElementById('schedules-list');
    const notification = document.getElementById('notification');

    let reportDataCache = null;
    let eventSource = null;
    let statusChart = null;

    function showNotification(message) {
        if (notification) {
            notification.textContent = message;
            notification.style.display = 'block';
            setTimeout(() => { notification.style.display = 'none'; }, 3000);
        }
    }

    function addStatusMessage(message, isError = false, isSuccess = false) {
        if (!statusMessagesDiv) return;
        const p = document.createElement('p');
        p.textContent = message;
        if (isError) {
            p.style.color = '#dc3545';
            p.style.fontWeight = '600';
        } else if (isSuccess) {
            p.style.color = '#00A1B7';
            p.style.fontWeight = '600';
        }
        const defaultMsg = statusMessagesDiv.querySelector('p');
        const defaultTexts = ['No activity yet.', 'Đang gửi yêu cầu tải xuống...'];
        if (defaultMsg && defaultTexts.includes(defaultMsg.textContent)) {
            statusMessagesDiv.innerHTML = '';
        }
        statusMessagesDiv.appendChild(p);
        statusMessagesDiv.scrollTop = statusMessagesDiv.scrollHeight;
    }

    async function fetchData(url, options = {}) {
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status} ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.message || errorMsg;
                } catch (e) {}
                throw new Error(errorMsg);
            }
            const contentType = response.headers.get("content-type");
            if (response.status === 204) {
                return { status: 'success', message: 'Operation successful (No Content)' };
            }
            if (contentType && contentType.includes("application/json")) {
                return await response.json();
            } else {
                return { status: 'success', message: await response.text() || 'Operation successful' };
            }
        } catch (error) {
            console.error(`Error fetching ${url}:`, error);
            addStatusMessage(`API Error: ${error.message || 'Network error or server unavailable'}`, true);
            throw error;
        }
    }

    function fillSelectOptions(selectElement, optionsList, includeDefault = true, defaultText = "-- Select --") {
        if (!selectElement) return;
        const currentValue = selectElement.value;
        selectElement.innerHTML = '';
        if (includeDefault) {
            const defaultOption = document.createElement('option');
            defaultOption.value = "";
            defaultOption.textContent = defaultText;
            selectElement.appendChild(defaultOption);
        }
        optionsList.forEach(optionValue => {
            const option = document.createElement('option');
            if (typeof optionValue === 'object' && optionValue !== null && optionValue.value !== undefined) {
                option.value = optionValue.value;
                option.textContent = optionValue.text || optionValue.value;
            } else {
                option.value = String(optionValue);
                option.textContent = String(optionValue);
            }
            selectElement.appendChild(option);
        });
        const exists = optionsList.some(opt => (typeof opt === 'object' ? opt.value : String(opt)) === currentValue);
        if (currentValue && exists) {
            selectElement.value = currentValue;
        } else if (!includeDefault && optionsList.length > 0) {
            selectElement.selectedIndex = 0;
        }
    }

    function populateAllReportDropdowns(reportNames) {
        const selects = document.querySelectorAll("select[name='report_type[]']");
        if (selects.length === 0) return;
        selects.forEach(sel => {
            const currentValue = sel.value;
            fillSelectOptions(sel, reportNames, true, '-- Select Report --');
            if (reportNames.includes(currentValue)) {
                sel.value = currentValue;
            }
            if (!sel.dataset.listenerAttached) {
                sel.addEventListener('change', updateRegionSelectionVisibilityBasedOnAllRows);
                sel.dataset.listenerAttached = 'true';
            }
        });
        updateRegionSelectionVisibilityBasedOnAllRows();
    }

    function formatDate(date) {
        if (!(date instanceof Date) || isNaN(date)) return "";
        try {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        } catch (e) {
            return "";
        }
    }

    function setDefaultDates(rowElement) {
        if (!rowElement) return;
        const fromDateInput = rowElement.querySelector("input[name='from_date[]']");
        const toDateInput = rowElement.querySelector("input[name='to_date[]']");
        try {
            const now = new Date();
            const firstDayOfMonth = new Date(Date.UTC(now.getFullYear(), now.getMonth(), 1));
            const yesterday = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate() - 1));
            if (fromDateInput) fromDateInput.value = formatDate(firstDayOfMonth);
            if (toDateInput) toDateInput.value = formatDate(yesterday);
        } catch (e) {}
    }

    async function fetchAndPopulateReportData() {
        try {
            const data = await fetchData('/get-reports-regions');
            if (data && data.reports) {
                reportDataCache = data;
                populateAllReportDropdowns(data.reports);
                const initialRow = reportTableBody?.querySelector("tr");
                if (initialRow) {
                    setDefaultDates(initialRow);
                }
            } else {
                addStatusMessage("Error: Could not parse report data from backend.", true);
            }
        } catch (error) {}
    }

    function updateRegionSelectionVisibilityBasedOnAllRows() {
        if (!reportDataCache || !regionSelectionDiv) return;
        const reportSelects = document.querySelectorAll("select[name='report_type[]']");
        let requiresRegion = false;
        reportSelects.forEach(select => {
            const selectedReportKey = select.value;
            if (selectedReportKey && reportDataCache.report_urls_map && reportDataCache.region_required_urls) {
                const reportUrl = reportDataCache.report_urls_map[selectedReportKey];
                if (reportDataCache.region_required_urls.includes(reportUrl)) {
                    requiresRegion = true;
                }
            }
        });
        regionSelectionDiv.innerHTML = '';
        if (requiresRegion) {
            regionSelectionDiv.style.display = 'block';
            const label = document.createElement('label');
            label.textContent = 'Select Region(s):';
            label.style.display = 'block';
            label.style.fontSize = '14px';
            label.style.color = '#333333';
            label.style.marginBottom = '8px';
            regionSelectionDiv.appendChild(label);
            if (reportDataCache.regions && Object.keys(reportDataCache.regions).length > 0) {
                for (const [index, name] of Object.entries(reportDataCache.regions)) {
                    const checkboxId = `region-${index}`;
                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.id = checkboxId;
                    checkbox.name = 'regions';
                    checkbox.value = index;
                    const checkLabel = document.createElement('label');
                    checkLabel.htmlFor = checkboxId;
                    checkLabel.textContent = name;
                    checkLabel.style.marginRight = '16px';
                    checkLabel.style.fontSize = '14px';
                    checkLabel.style.color = '#333333';
                    const div = document.createElement('div');
                    div.appendChild(checkbox);
                    div.appendChild(checkLabel);
                    regionSelectionDiv.appendChild(div);
                }
            } else {
                regionSelectionDiv.innerHTML += '<p style="font-size:14px;color:#6B7280;">No region data available.</p>';
            }
        } else {
            regionSelectionDiv.style.display = 'none';
        }
    }

    async function handleDownloadFormSubmit(event) {
        event.preventDefault();
        if (!form) return;
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        downloadButton.disabled = true;
        loadingIndicator.style.display = 'inline';
        statusMessagesDiv.innerHTML = '';
        addStatusMessage("Sending download request...");
        const currentData = getCurrentFormData();
        let validationError = false;
        if (!currentData.email || !currentData.password) {
            addStatusMessage("Error: Please enter Email and Password.", true);
            validationError = true;
        }
        if (!currentData.reports || currentData.reports.length === 0) {
            addStatusMessage("Error: Please configure at least one valid report.", true);
            validationError = true;
        }
        let requiresRegion = false;
        if (reportDataCache && currentData.reports) {
            requiresRegion = currentData.reports.some(report => {
                const reportUrl = reportDataCache.report_urls_map[report.report_type];
                return reportDataCache.region_required_urls.includes(reportUrl);
            });
        }
        if (requiresRegion && currentData.regions.length === 0) {
            addStatusMessage("Error: The selected report(s) require at least one region to be selected.", true);
            validationError = true;
        }
        if (validationError) {
            downloadButton.disabled = false;
            loadingIndicator.style.display = 'none';
            return;
        }
        try {
            const dataToSend = {
                email: currentData.email,
                password: currentData.password,
                otp_secret: document.getElementById('otp-secret')?.value || '',
                driver_path: document.getElementById('driver-path')?.value || '',
                download_base_path: document.getElementById('download-base_path')?.value || '',
                reports: currentData.reports,
                regions: currentData.regions
            };
            const result = await fetchData('/start-download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dataToSend),
            });
            if (result && result.status === 'started') {
                addStatusMessage("Request accepted. Waiting for status updates...");
                setupEventSource();
            } else {
                downloadButton.disabled = false;
                loadingIndicator.style.display = 'none';
            }
        } catch (error) {
            downloadButton.disabled = false;
            loadingIndicator.style.display = 'none';
        }
    }

    function setupEventSource() {
        if (eventSource) {
            eventSource.close();
        }
        eventSource = new EventSource('/stream-status');
        const keepAliveTimeout = 3600000;
        let lastEventTime = Date.now();
        const keepAliveTimer = setInterval(() => {
            if (Date.now() - lastEventTime > keepAliveTimeout) {
                eventSource.close();
                setupEventSource();
            }
        }, 30000);
        eventSource.onmessage = function(event) {
            lastEventTime = Date.now();
            const message = event.data;
            if (message === "FINISHED") {
                addStatusMessage("--- PROCESS COMPLETED ---", false, true);
                if (eventSource) eventSource.close();
                eventSource = null;
                downloadButton.disabled = false;
                loadingIndicator.style.display = 'none';
                fetchLogs();
            } else {
                addStatusMessage(message);
            }
        };
        eventSource.onerror = function(error) {
            setTimeout(() => {
                setupEventSource();
            }, 5000);
        };
    }

    async function fetchLogs() {
        if (!logTableContainer) return;
        logTableContainer.innerHTML = '<p style="font-size:14px;color:#6B7280;">Loading logs...</p>';
        try {
            const data = await fetchData('/get-logs');
            logTableContainer.innerHTML = '';
            if (data.status === 'success' && data.logs && data.logs.length > 0) {
                createLogTable(data.logs);
            } else {
                logTableContainer.innerHTML = `<p style="font-size:14px;color:#6B7280;">${data.message || 'No log entries found.'}</p>`;
            }
        } catch (error) {
            logTableContainer.innerHTML = `<p style="font-size:14px;color:#dc3545;">Failed to load logs.</p>`;
        }
    }

    function createLogTable(logData) {
        if (!logTableContainer || !Array.isArray(logData) || logData.length === 0) return;
        logData.sort((a, b) => new Date(b.Timestamp) - new Date(a.Timestamp));
        const headers = ['SessionID', 'Timestamp', 'File Name', 'Start Date', 'End Date', 'Status', 'Error Message'];
        const table = document.createElement('table');
        table.style.width = '100%';
        table.style.borderCollapse = 'collapse';
        const thead = table.createTHead();
        const headerRow = thead.insertRow();
        headers.forEach(headerText => {
            const th = document.createElement('th');
            th.textContent = headerText;
            th.style.padding = '12px';
            th.style.fontSize = '14px';
            th.style.color = '#333333';
            th.style.fontWeight = '600';
            th.style.textAlign = 'left';
            th.style.borderBottom = '1px solid #E5E7EB';
            th.style.background = '#F8F9FA';
            headerRow.appendChild(th);
        });
        const tbody = table.createTBody();
        logData.forEach(logEntry => {
            const row = tbody.insertRow();
            headers.forEach(header => {
                const cell = row.insertCell();
                const value = logEntry[header];
                cell.textContent = (value === null || value === undefined) ? '' : String(value);
                cell.style.padding = '12px';
                cell.style.fontSize = '14px';
                cell.style.color = '#333333';
                cell.style.borderBottom = '1px solid #E5E7EB';
            });
        });
        logTableContainer.appendChild(table);
        updateSummaryAndChart(logData);
    }

    function updateSummaryAndChart(logData) {
        const total = logData.length;
        const successCount = logData.filter(e => e['Status'] && e['Status'].toLowerCase().startsWith('success')).length;
        const failedCount = total - successCount;
        document.getElementById('total-count').textContent = total;
        document.getElementById('success-count').textContent = successCount;
        document.getElementById('failed-count').textContent = failedCount;
        const ctx = document.getElementById('status-chart').getContext('2d');
        if (statusChart) statusChart.destroy();
        statusChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Success', 'Failed'],
                datasets: [{ data: [successCount, failedCount], backgroundColor: ['#00A1B7', '#dc3545'] }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }

    function getCurrentFormData() {
        const formData = new FormData(form);
        const reportRows = reportTableBody.querySelectorAll('tr');
        const configData = {
            email: formData.get('email'),
            password: formData.get('password'),
            reports: [],
            regions: []
        };
        reportRows.forEach(row => {
            const reportTypeSelect = row.querySelector('select[name="report_type[]"]');
            const fromDateInput = row.querySelector('input[name="from_date[]"]');
            const toDateInput = row.querySelector('input[name="to_date[]"]');
            const chunkSizeInput = row.querySelector('input[name="chunk_size[]"]');
            if (reportTypeSelect && reportTypeSelect.value) {
                configData.reports.push({
                    report_type: reportTypeSelect.value,
                    from_date: fromDateInput ? fromDateInput.value : '',
                    to_date: toDateInput ? toDateInput.value : '',
                    chunk_size: chunkSizeInput ? (chunkSizeInput.value.trim() || '5') : '5',
                });
            }
        });
        if (regionSelectionDiv && regionSelectionDiv.style.display === 'block') {
            const selectedRegionCheckboxes = regionSelectionDiv.querySelectorAll('input[name="regions"]:checked');
            configData.regions = Array.from(selectedRegionCheckboxes).map(cb => cb.value);
        }
        return configData;
    }

    function applyConfiguration(configData) {
        if (!configData || typeof configData !== 'object') {
            addStatusMessage("Error: Invalid configuration data received.", true);
            return;
        }
        if (emailInput) emailInput.value = configData.email || '';
        if (passwordInput) passwordInput.value = configData.password || '';
        if (!reportTableBody) return;
        while (reportTableBody.rows.length > 1) {
            reportTableBody.deleteRow(1);
        }
        const firstRow = reportTableBody.rows[0];
        if (!firstRow) return;
        const firstSelect = firstRow.querySelector('select[name="report_type[]"]');
        const firstFromDate = firstRow.querySelector('input[name="from_date[]"]');
        const firstToDate = firstRow.querySelector('input[name="to_date[]"]');
        const firstChunk = firstRow.querySelector('input[name="chunk_size[]"]');
        if (firstSelect) firstSelect.value = '';
        setDefaultDates(firstRow);
        if (firstChunk) firstChunk.value = '5';
        if (configData.reports && Array.isArray(configData.reports) && configData.reports.length > 0) {
            configData.reports.forEach((reportInfo, index) => {
                let targetRow;
                if (index === 0) {
                    targetRow = firstRow;
                } else {
                    targetRow = firstRow.cloneNode(true);
                    reportTableBody.appendChild(targetRow);
                    setDefaultDates(targetRow);
                    const newSelect = targetRow.querySelector("select[name='report_type[]']");
                    if (newSelect && !newSelect.dataset.listenerAttached) {
                        newSelect.addEventListener('change', updateRegionSelectionVisibilityBasedOnAllRows);
                        newSelect.dataset.listenerAttached = 'true';
                    }
                }
                const typeSelect = targetRow.querySelector('select[name="report_type[]"]');
                const fromInput = targetRow.querySelector('input[name="from_date[]"]');
                const toInput = targetRow.querySelector('input[name="to_date[]"]');
                const chunkInput = targetRow.querySelector('input[name="chunk_size[]"]');
                if (typeSelect) typeSelect.value = reportInfo.report_type || '';
                if (fromInput) fromInput.value = reportInfo.from_date || '';
                if (toInput) toInput.value = reportInfo.to_date || '';
                if (chunkInput) chunkInput.value = reportInfo.chunk_size || '5';
            });
        }
        updateRegionSelectionVisibilityBasedOnAllRows();
        setTimeout(() => {
            if (regionSelectionDiv && regionSelectionDiv.style.display === 'block') {
                if (configData.regions && Array.isArray(configData.regions)) {
                    const regionCheckboxes = regionSelectionDiv.querySelectorAll('input[name="regions"]');
                    regionCheckboxes.forEach(checkbox => {
                        checkbox.checked = configData.regions.includes(checkbox.value);
                    });
                }
            }
        }, 100);
        addStatusMessage("Configuration loaded successfully.", false, true);
        showNotification("New items saved");
    }

    async function fetchAndPopulateConfigs() {
        try {
            const data = await fetchData('/get-configs');
            if (data.status === 'success') {
                const configNames = data.configs || [];
                fillSelectOptions(savedConfigsDropdown, configNames, true, '-- Select Configuration --');
                fillSelectOptions(scheduleConfigSelect, configNames, true, '-- Select Config to Schedule --');
            } else {
                addStatusMessage(data.message || "Error loading configuration list.", true);
            }
        } catch (error) {}
    }

    async function fetchAndDisplaySchedules() {
        if (!schedulesList) return;
        schedulesList.innerHTML = '<li style="font-size:14px;color:#6B7280;">Loading schedules...</li>';
        try {
            const data = await fetchData('/get-schedules');
            schedulesList.innerHTML = '';
            if (data.status === 'success' && data.schedules && data.schedules.length > 0) {
                data.schedules.forEach(job => {
                    const li = document.createElement('li');
                    let nextRunText = 'N/A';
                    if (job.next_run_time) {
                        try {
                            nextRunText = new Date(job.next_run_time).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
                        } catch (e) {
                            nextRunText = job.next_run_time;
                        }
                    }
                    const configArg = job.args && job.args.length > 0 ? job.args[0] : 'Unknown Config';
                    const textSpan = document.createElement('span');
                    textSpan.textContent = `Config: "${configArg}" - Next Run: ${nextRunText}`;
                    textSpan.style.fontSize = '14px';
                    textSpan.style.color = '#333333';
                    const cancelButton = document.createElement('button');
                    cancelButton.textContent = 'Cancel';
                    cancelButton.className = 'delete-button';
                    cancelButton.dataset.jobId = job.id;
                    cancelButton.style.padding = '4px 8px';
                    cancelButton.style.fontSize = '12px';
                    li.appendChild(textSpan);
                    li.appendChild(cancelButton);
                    li.style.display = 'flex';
                    li.style.justifyContent = 'space-between';
                    li.style.alignItems = 'center';
                    li.style.padding = '8px 0';
                    schedulesList.appendChild(li);
                });
            } else {
                schedulesList.innerHTML = '<li style="font-size:14px;color:#6B7280;">No active schedules found.</li>';
            }
        } catch (error) {
            schedulesList.innerHTML = '<li style="font-size:14px;color:#dc3545;">Error loading schedules.</li>';
        }
    }

    if (form) {
        form.addEventListener('submit', handleDownloadFormSubmit);
    }

    if (refreshLogButton) {
        refreshLogButton.addEventListener('click', fetchLogs);
    }

    if (reportTable) {
        reportTable.addEventListener('change', (event) => {
            if (event.target && event.target.matches("select[name='report_type[]']")) {
                updateRegionSelectionVisibilityBasedOnAllRows();
            }
        });
    }

    if (saveConfigButton) {
        saveConfigButton.addEventListener('click', async () => {
            const configName = configNameInput.value.trim();
            if (!configName) {
                alert("Please enter a configuration name.");
                return;
            }
            const configData = getCurrentFormData();
            if (!configData.reports || configData.reports.length === 0) {
                alert("Please configure at least one valid report before saving.");
                return;
            }
            try {
                const result = await fetchData('/save-config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ config_name: configName, config_data: configData })
                });
                if (result.status === 'success') {
                    addStatusMessage(result.message, false, true);
                    showNotification("New items saved");
                    configNameInput.value = '';
                    fetchAndPopulateConfigs();
                }
            } catch (error) {}
        });
    }

    if (loadConfigButton) {
        loadConfigButton.addEventListener('click', async () => {
            const selectedConfigName = savedConfigsDropdown.value;
            if (!selectedConfigName) {
                alert("Please select a configuration to load.");
                return;
            }
            try {
                const result = await fetchData(`/load-config/${selectedConfigName}`);
                if (result.status === 'success' && result.config_data) {
                    applyConfiguration(result.config_data);
                } else {
                    addStatusMessage(result.message || `Could not load config ${selectedConfigName}.`, true);
                }
            } catch (error) {}
        });
    }

    if (deleteConfigButton) {
        deleteConfigButton.addEventListener('click', async () => {
            const selectedConfigName = savedConfigsDropdown.value;
            if (!selectedConfigName) {
                alert("Please select a configuration to delete.");
                return;
            }
            if (!confirm(`Are you sure you want to delete configuration "${selectedConfigName}"?`)) {
                return;
            }
            try {
                const result = await fetchData(`/delete-config/${selectedConfigName}`, { method: 'DELETE' });
                if (result && result.status === 'success') {
                    addStatusMessage(result.message || `Configuration "${selectedConfigName}" deleted.`, false, true);
                    fetchAndPopulateConfigs();
                }
            } catch (error) {}
        });
    }

    if (scheduleButton) {
        scheduleButton.addEventListener('click', async () => {
            const configName = scheduleConfigSelect.value;
            const runDateTime = scheduleDateTimeInput.value;
            if (!configName) {
                alert("Please select a saved configuration to schedule.");
                return;
            }
            if (!runDateTime) {
                alert("Please select a date and time to run the job.");
                return;
            }
            try {
                const selectedDate = new Date(runDateTime);
                const bufferMinutes = 1;
                const minDate = new Date(Date.now() + bufferMinutes * 60 * 1000);
                if (selectedDate <= minDate) {
                    alert(`Please select a time at least ${bufferMinutes} minute(s) in the future.`);
                    return;
                }
            } catch (e) {
                alert("Invalid date/time format.");
                return;
            }
            try {
                const result = await fetchData('/schedule-job', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        config_name: configName,
                        trigger_type: 'date',
                        run_datetime: runDateTime
                    })
                });
                if (result.status === 'success') {
                    addStatusMessage(result.message || `Job scheduled for ${configName}.`, false, true);
                    showNotification("New items saved");
                    fetchAndDisplaySchedules();
                    scheduleConfigSelect.value = '';
                    scheduleDateTimeInput.value = '';
                }
            } catch (error) {}
        });
    }

    if (schedulesList) {
        schedulesList.addEventListener('click', async (event) => {
            if (event.target && event.target.classList.contains('delete-button')) {
                const jobId = event.target.dataset.jobId;
                if (!jobId) return;
                if (!confirm(`Are you sure you want to cancel schedule ${jobId}?`)) return;
                try {
                    const result = await fetchData(`/cancel-schedule/${jobId}`, { method: 'DELETE' });
                    if (result && result.status === 'success') {
                        addStatusMessage(result.message || `Job ${jobId} cancelled.`, false, true);
                        fetchAndDisplaySchedules();
                    }
                } catch (error) {}
            }
        });
    }

    if (addRowButton) {
        addRowButton.addEventListener("click", function () {
            if (!reportTableBody) return;
            const firstRow = reportTableBody.querySelector("tr");
            if (!firstRow) return;
            const newRow = firstRow.cloneNode(true);
            const reportSelect = newRow.querySelector("select[name='report_type[]']");
            const chunkSizeInput = newRow.querySelector("input[name='chunk_size[]']");
            if (reportSelect) reportSelect.selectedIndex = 0;
            setDefaultDates(newRow);
            if (chunkSizeInput) chunkSizeInput.value = "5";
            const newSelect = newRow.querySelector("select[name='report_type[]']");
            if (newSelect && !newSelect.dataset.listenerAttached) {
                newSelect.addEventListener('change', updateRegionSelectionVisibilityBasedOnAllRows);
                newSelect.dataset.listenerAttached = 'true';
            }
            reportTableBody.appendChild(newRow);
            updateRegionSelectionVisibilityBasedOnAllRows();
        });
    }

    if (reportTable) {
        reportTable.addEventListener("click", function (event) {
            if (event.target.classList.contains("remove-row-button")) {
                const row = event.target.closest("tr");
                if (reportTableBody && reportTableBody.querySelectorAll("tr").length > 1) {
                    row.remove();
                    updateRegionSelectionVisibilityBasedOnAllRows();
                } else {
                    alert("Must have at least one report configuration row.");
                }
            }
        });
    }

    fetchAndPopulateReportData();
    fetchLogs();
    fetchAndPopulateConfigs();
    fetchAndDisplaySchedules();
});