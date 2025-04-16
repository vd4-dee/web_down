// static/js/script.js

// Wrap all code in DOMContentLoaded to ensure elements exist
document.addEventListener('DOMContentLoaded', () => {

    // --- DOM Element References ---
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

    // Configuration Management Elements
    const configNameInput = document.getElementById('config-name');
    const saveConfigButton = document.getElementById('save-config-button');
    const savedConfigsDropdown = document.getElementById('saved-configs-dropdown');
    const loadConfigButton = document.getElementById('load-config-button');
    const deleteConfigButton = document.getElementById('delete-config-button');

    // Scheduling Elements
    const scheduleConfigSelect = document.getElementById('schedule-config-select');
    const scheduleDateTimeInput = document.getElementById('schedule-datetime');
    const scheduleButton = document.getElementById('schedule-button');
    const schedulesList = document.getElementById('schedules-list');

    // --- Global Variables ---
    let reportDataCache = null; // Cache for report/region data (URLs, names, requirements)
    let sseConnection = null; // Holds the active Server-Sent Events connection

    // --- Helper Functions ---

    /**
     * Adds a message to the status display area.
     * @param {string} message - The message text.
     * @param {boolean} [isError=false] - True if the message indicates an error.
     * @param {boolean} [isSuccess=false] - True if the message indicates success.
     */
    function addStatusMessage(message, isError = false, isSuccess = false) {
        if (!statusMessagesDiv) return; // Exit if element doesn't exist
        const p = document.createElement('p');
        p.textContent = message;
        if (isError) {
            p.style.color = 'red';
            p.style.fontWeight = 'bold';
        } else if (isSuccess) {
             p.style.color = 'green';
             p.style.fontWeight = 'bold';
        }
        // Clear default message if it exists
        const defaultMsg = statusMessagesDiv.querySelector('p');
        const defaultTexts = ['No activity yet.', 'Đang gửi yêu cầu tải xuống...']; // Add Vietnamese default text
        if (defaultMsg && defaultTexts.includes(defaultMsg.textContent)) {
            statusMessagesDiv.innerHTML = '';
        }
        statusMessagesDiv.appendChild(p);
        // Auto-scroll to the bottom
        statusMessagesDiv.scrollTop = statusMessagesDiv.scrollHeight;
    }

    /**
     * Performs a fetch request and handles common errors.
     * @param {string} url - The URL to fetch.
     * @param {object} [options={}] - Fetch options (method, headers, body, etc.).
     * @returns {Promise<object>} - A promise resolving to the JSON response or a success indicator.
     */
    async function fetchData(url, options = {}) {
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status} ${response.statusText}`;
                try {
                    // Try to get more specific error from backend JSON response
                    const errorData = await response.json();
                    errorMsg = errorData.message || errorMsg;
                } catch (e) { /* Ignore if response body is not JSON */ }
                throw new Error(errorMsg);
            }
            // Handle successful responses that might not have JSON content (e.g., DELETE)
             const contentType = response.headers.get("content-type");
             if (response.status === 204) { // No Content success
                 return { status: 'success', message: 'Operation successful (No Content)' };
             }
             if (contentType && contentType.includes("application/json")) {
                 return await response.json(); // Parse JSON if available
             } else {
                 // Return success indicator for other successful non-JSON responses
                 return { status: 'success', message: await response.text() || 'Operation successful' };
             }
        } catch (error) {
            console.error(`Error fetching ${url}:`, error);
            // Display error to the user via status message
            addStatusMessage(`API Error: ${error.message || 'Network error or server unavailable'}`, true);
            throw error; // Re-throw for calling function to potentially handle
        }
    }

    /**
     * Populates a select dropdown with options.
     * @param {HTMLSelectElement} selectElement - The select element to populate.
     * @param {Array<string|object>} optionsList - Array of option values or objects {value, text}.
     * @param {boolean} [includeDefault=true] - Whether to include a default "-- Select --" option.
     * @param {string} [defaultText='-- Select --'] - Text for the default option.
     */
    function fillSelectOptions(selectElement, optionsList, includeDefault = true, defaultText = "-- Select --") {
        if (!selectElement) {
            console.error("fillSelectOptions: Provided selectElement is invalid.");
            return;
        }
        const currentValue = selectElement.value; // Preserve current value if possible
        selectElement.innerHTML = ''; // Clear existing options
        if (includeDefault) {
            const defaultOption = document.createElement('option');
            defaultOption.value = "";
            defaultOption.textContent = defaultText; // Use parameter for text
            selectElement.appendChild(defaultOption);
        }
        optionsList.forEach(optionValue => {
            const option = document.createElement('option');
            // Handle both string options and {value, text} objects
            if (typeof optionValue === 'object' && optionValue !== null && optionValue.value !== undefined) {
                 option.value = optionValue.value;
                 option.textContent = optionValue.text || optionValue.value; // Fallback text
            } else { // Assume string value
                 option.value = String(optionValue); // Ensure value is string
                 option.textContent = String(optionValue);
            }
            selectElement.appendChild(option);
        });
        // Try to restore the previously selected value if it still exists in the new list
        const exists = optionsList.some(opt => (typeof opt === 'object' ? opt.value : String(opt)) === currentValue);
        if (currentValue && exists) {
             selectElement.value = currentValue;
        } else if (!includeDefault && optionsList.length > 0) {
            // If no default and previous value gone, select the first option
            selectElement.selectedIndex = 0;
        }
    }

    /**
     * Populates all report type dropdowns in the table.
     * @param {Array<string>} reportNames - List of report names.
     */
     function populateAllReportDropdowns(reportNames) {
        const selects = document.querySelectorAll("select[name='report_type[]']");
        if (selects.length === 0) {
            console.warn("No report type dropdowns found to populate.");
            return;
        }
        selects.forEach(sel => {
            const currentValue = sel.value;
            fillSelectOptions(sel, reportNames, true, '-- Select Report --'); // Use specific default text
            if (reportNames.includes(currentValue)) {
                sel.value = currentValue;
            }
             // Attach change listener only once
             if (!sel.dataset.listenerAttached) {
                 sel.addEventListener('change', updateRegionSelectionVisibilityBasedOnAllRows);
                 sel.dataset.listenerAttached = 'true';
             }
        });
         // Update region visibility after populating all dropdowns
         updateRegionSelectionVisibilityBasedOnAllRows();
    }

    /**
     * Formats a Date object into YYYY-MM-DD string.
     * @param {Date} date - The date object.
     * @returns {string} - The formatted date string or empty string on error.
     */
    function formatDate(date) {
        if (!(date instanceof Date) || isNaN(date)) {
             console.error("Invalid date passed to formatDate:", date);
             return "";
        }
        try {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        } catch (e) {
            console.error("Error formatting date:", e, date);
            return "";
        }
    }

    /**
     * Sets the default 'From' and 'To' dates for a given table row element.
     * @param {HTMLTableRowElement} rowElement - The table row element.
     */
    function setDefaultDates(rowElement) {
        if (!rowElement) return;
        const fromDateInput = rowElement.querySelector("input[name='from_date[]']");
        const toDateInput = rowElement.querySelector("input[name='to_date[]']");
        try {
            // Use UTC dates internally then format to avoid timezone issues with input[type=date]
            const now = new Date(); // Current date/time
            const firstDayOfMonth = new Date(Date.UTC(now.getFullYear(), now.getMonth(), 1));
            const yesterday = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate() -1));

            if(fromDateInput) fromDateInput.value = formatDate(firstDayOfMonth);
            if(toDateInput) toDateInput.value = formatDate(yesterday);
        } catch(e) { console.error("Error setting default dates:", e); }
    }


    // --- Report and Region Data Handling ---

    /** Fetches report/region data and populates initial UI elements. */
    async function fetchAndPopulateReportData() {
        try {
            const data = await fetchData('/get-reports-regions');
            if (data && data.reports) { // Check if data and reports exist
                reportDataCache = data; // Store fetched data
                populateAllReportDropdowns(data.reports);
                // Set default dates for the initial row *after* reports are loaded
                const initialRow = reportTableBody?.querySelector("tr"); // Use optional chaining
                if (initialRow) {
                    setDefaultDates(initialRow);
                }
            } else {
                 addStatusMessage("Error: Could not parse report data from backend.", true);
            }
        } catch (error) {
            addStatusMessage("Error loading report list from backend. Check console.", true);
            // No need to log error again, fetchData does it
        }
    }

    /** Updates the visibility and content of the region selection div based on all selected reports. */
    function updateRegionSelectionVisibilityBasedOnAllRows() {
        if (!reportDataCache || !regionSelectionDiv) { // Check elements exist
            // console.warn("Skipping region update: Cache or element not ready.");
            return;
        }

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

        // Always clear previous content
        regionSelectionDiv.innerHTML = '';

        if (requiresRegion) {
            regionSelectionDiv.style.display = 'block';
            const label = document.createElement('label');
            label.textContent = 'Select Region(s) (for required reports):'; // Use English
            regionSelectionDiv.appendChild(label);
            regionSelectionDiv.appendChild(document.createElement('br'));

            if (reportDataCache.regions && Object.keys(reportDataCache.regions).length > 0) {
                for (const [index, name] of Object.entries(reportDataCache.regions)) {
                    const checkboxId = `region-${index}`;
                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.id = checkboxId;
                    checkbox.name = 'regions';
                    checkbox.value = index; // Value is the index (string)

                    const checkLabel = document.createElement('label');
                    checkLabel.htmlFor = checkboxId;
                    checkLabel.textContent = name; // Display region name

                    const div = document.createElement('div'); // Wrap checkbox and label for styling/spacing
                    div.appendChild(checkbox);
                    div.appendChild(checkLabel);
                    regionSelectionDiv.appendChild(div);
                }
            } else {
                 regionSelectionDiv.innerHTML += '<p>No region data available.</p>';
            }
        } else {
            regionSelectionDiv.style.display = 'none'; // Hide if no selected report requires regions
        }
    }

    // --- Download Logic ---

    /** Handles the submission of the main download form. */
    async function handleDownloadFormSubmit(event) {
        event.preventDefault(); // Prevent default HTML form submission
        if (!form) { addStatusMessage("Error: Download form not found!", true); return; }

        // Close any previous SSE connection
        if (sseConnection) {
            sseConnection.close();
            console.log("Closed previous SSE connection.");
            sseConnection = null; // Reset variable
        }

        // Disable button, show indicator, clear status
        downloadButton.disabled = true;
        loadingIndicator.style.display = 'inline';
        statusMessagesDiv.innerHTML = ''; // Clear previous status messages
        addStatusMessage("Sending download request..."); // Initial feedback

        // Get data using helper function
        const currentData = getCurrentFormData();

        // --- Frontend Validation ---
        let validationError = false;
        if (!currentData.email || !currentData.password) {
             addStatusMessage("Error: Please enter Email and Password.", true);
             validationError = true;
        }
        if (!currentData.reports || currentData.reports.length === 0) {
            addStatusMessage("Error: Please configure at least one valid report.", true);
            validationError = true;
        }
        // Check if any configured report requires region selection
        let requiresRegion = false;
        if (reportDataCache && currentData.reports) {
             requiresRegion = currentData.reports.some(report => {
                 const reportUrl = reportDataCache.report_urls_map[report.report_type];
                 return reportDataCache.region_required_urls.includes(reportUrl);
             });
        }
        // If region is required but none selected
        if (requiresRegion && currentData.regions.length === 0) {
            addStatusMessage("Error: The selected report(s) require at least one region to be selected.", true);
            validationError = true;
        }

        if (validationError) {
            downloadButton.disabled = false;
            loadingIndicator.style.display = 'none';
            return; // Stop submission
        }
        // --- End Validation ---

        try {
            // Backend expects flat lists, convert data structure
            const dataToSend = {
                email: currentData.email,
                password: currentData.password,
                report_type: currentData.reports.map(r => r.report_type),
                from_date: currentData.reports.map(r => r.from_date),
                to_date: currentData.reports.map(r => r.to_date),
                chunk_size: currentData.reports.map(r => r.chunk_size),
                regions: currentData.regions // Already a list of strings (indices)
            };

            console.log("Data sending to /start-download:", JSON.stringify(dataToSend));

            // Send request using fetchData
            const result = await fetchData('/start-download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dataToSend),
            });

            // Check backend response status
            if (result && result.status === 'started') {
                addStatusMessage("Request accepted. Waiting for status updates...");
                initializeSSEListener(); // Start listening for updates
            } else {
                // Error message should have been shown by fetchData
                downloadButton.disabled = false;
                loadingIndicator.style.display = 'none';
            }
        } catch (error) {
            // Network or other fetch errors handled by fetchData
            downloadButton.disabled = false;
            loadingIndicator.style.display = 'none';
        }
     }

    /** Initializes the Server-Sent Events (SSE) connection for status updates. */
    function initializeSSEListener() {
        if (sseConnection) { // Close existing connection if any
             sseConnection.close();
        }
        sseConnection = new EventSource('/stream-status'); // Connect to the SSE endpoint

        sseConnection.onopen = function() {
             console.log("SSE connection established.");
             addStatusMessage("Connected to status stream...");
         };

        sseConnection.onmessage = function(event) {
            const message = event.data;
            // Check for the special FINISHED signal
            if (message === "FINISHED") {
                addStatusMessage("--- PROCESS COMPLETED ---", false, true);
                if (sseConnection) sseConnection.close(); // Close connection
                sseConnection = null; // Reset variable
                downloadButton.disabled = false; // Re-enable button
                loadingIndicator.style.display = 'none';
                fetchLogs(); // Refresh logs automatically when finished
            } else {
                addStatusMessage(message); // Display the regular status message
            }
        };

        sseConnection.onerror = function(error) {
            console.error('SSE Error:', error);
            addStatusMessage("Status stream connection error. Please check console or try again.", true);
            if (sseConnection) sseConnection.close(); // Close on error
            sseConnection = null; // Reset variable
            downloadButton.disabled = false; // Re-enable button
            loadingIndicator.style.display = 'none';
        };
    }

    // --- Log Handling ---

    /** Fetches download logs from the backend and displays them. */
    async function fetchLogs() {
        if (!logTableContainer) return;
        logTableContainer.innerHTML = '<p>Loading logs...</p>';
        try {
            const data = await fetchData('/get-logs');
             logTableContainer.innerHTML = ''; // Clear loading message
             if (data.status === 'success' && data.logs && data.logs.length > 0) {
                 createLogTable(data.logs);
             } else {
                 // Display message from backend or default 'no logs' message
                 logTableContainer.innerHTML = `<p>${data.message || 'No log entries found.'}</p>`;
             }
        } catch (error) {
             // fetchData already showed API error message
             logTableContainer.innerHTML = `<p style="color: red;">Failed to load logs.</p>`;
        }
    }

    /**
     * Creates and populates the log table in the UI.
     * @param {Array<object>} logData - Array of log entry objects.
     */
    function createLogTable(logData) {
        if (!logTableContainer || !Array.isArray(logData) || logData.length === 0) return;

        const table = document.createElement('table');
        table.className = 'log-table'; // For styling

        // Create table header
        const thead = table.createTHead();
        const headerRow = thead.insertRow();
        const headers = Object.keys(logData[0]); // Get headers from first entry
        headers.forEach(headerText => {
            const th = document.createElement('th');
            th.textContent = headerText; // Display header text
            headerRow.appendChild(th);
        });

        // Create table body
        const tbody = table.createTBody();
        logData.forEach(logEntry => {
            const row = tbody.insertRow();
            headers.forEach(header => {
                const cell = row.insertCell();
                let value = logEntry[header];
                // Ensure value is displayed correctly (handle null/undefined)
                cell.textContent = (value === null || value === undefined) ? '' : String(value);
            });
        });

        // Clear container and append table
        logTableContainer.innerHTML = '';
        logTableContainer.appendChild(table);
    }

    // --- Configuration Management Logic ---

    /** Fetches saved config names and populates relevant dropdowns. */
    async function fetchAndPopulateConfigs() {
        try {
            const data = await fetchData('/get-configs');
            if (data.status === 'success') {
                const configNames = data.configs || [];
                // Populate both dropdowns
                fillSelectOptions(savedConfigsDropdown, configNames, true, '-- Select Configuration --');
                fillSelectOptions(scheduleConfigSelect, configNames, true, '-- Select Config to Schedule --');
            } else {
                 addStatusMessage(data.message || "Error loading configuration list.", true);
            }
        } catch (error) { /* Error handled by fetchData */ }
     }

    /**
     * Gets the current state of the download form as a structured object.
     * @returns {object} - The configuration data object.
     */
    function getCurrentFormData() {
         const formData = new FormData(form); // Gets email/password easily
         const reportRows = reportTableBody.querySelectorAll('tr');
         const configData = {
             email: formData.get('email'),
             password: formData.get('password'), // WARNING: Storing password insecurely
             reports: [], // Array of report config objects
             regions: [] // Array of selected region indices (strings)
         };

         reportRows.forEach(row => {
             const reportTypeSelect = row.querySelector('select[name="report_type[]"]');
             const fromDateInput = row.querySelector('input[name="from_date[]"]');
             const toDateInput = row.querySelector('input[name="to_date[]"]');
             const chunkSizeInput = row.querySelector('input[name="chunk_size[]"]');

             // Only include row if a valid report type is selected
             if (reportTypeSelect && reportTypeSelect.value) {
                 configData.reports.push({
                     report_type: reportTypeSelect.value,
                     from_date: fromDateInput ? fromDateInput.value : '',
                     to_date: toDateInput ? toDateInput.value : '',
                     chunk_size: chunkSizeInput ? (chunkSizeInput.value.trim() || '5') : '5', // Default 5 if empty
                 });
             }
         });

         // Get selected regions if the section is visible
         if (regionSelectionDiv && regionSelectionDiv.style.display === 'block') {
             const selectedRegionCheckboxes = regionSelectionDiv.querySelectorAll('input[name="regions"]:checked');
             // Store values (which are the indices as strings)
             configData.regions = Array.from(selectedRegionCheckboxes).map(cb => cb.value);
         }

         // console.log("Generated current form data:", configData); // For debugging
         return configData;
    }

    /**
     * Applies a loaded configuration object to the download form UI.
     * @param {object} configData - The configuration data object.
     */
    function applyConfiguration(configData) {
        // console.log("Applying configuration:", configData); // For debugging
        if (!configData || typeof configData !== 'object') {
            console.error("applyConfiguration received invalid configData:", configData);
            addStatusMessage("Error: Invalid configuration data received.", true);
            return;
        }

        // Set email and password
        if (emailInput) emailInput.value = configData.email || '';
        if (passwordInput) passwordInput.value = configData.password || ''; // WARNING: Password handling

        // Ensure reportTableBody exists
        if (!reportTableBody) {
            console.error("Cannot apply configuration: Report table body not found.");
            return;
        }

        // Clear existing rows except the first (template) row
        while (reportTableBody.rows.length > 1) {
            reportTableBody.deleteRow(1); // Delete second row repeatedly
        }
        const firstRow = reportTableBody.rows[0];
        if (!firstRow) {
            console.error("Cannot apply configuration: Template row not found.");
            // Potentially recreate the first row if necessary
            return;
        }

        // Reset the first row's content
        const firstSelect = firstRow.querySelector('select[name="report_type[]"]');
        const firstFromDate = firstRow.querySelector('input[name="from_date[]"]');
        const firstToDate = firstRow.querySelector('input[name="to_date[]"]');
        const firstChunk = firstRow.querySelector('input[name="chunk_size[]"]');
        if(firstSelect) firstSelect.value = '';
        setDefaultDates(firstRow); // Set default dates on reset
        if(firstChunk) firstChunk.value = '5';

        // Apply report data from the loaded configuration
        if (configData.reports && Array.isArray(configData.reports) && configData.reports.length > 0) {
            configData.reports.forEach((reportInfo, index) => {
                let targetRow;
                if (index === 0) {
                    targetRow = firstRow; // Use the reset first row
                } else {
                    targetRow = firstRow.cloneNode(true); // Clone the *original* template row
                    reportTableBody.appendChild(targetRow); // Add new row to table
                    // Reset dates for the cloned row (it inherits template values initially)
                    setDefaultDates(targetRow);
                    // Add listener to the new select
                    const newSelect = targetRow.querySelector("select[name='report_type[]']");
                     if (newSelect && !newSelect.dataset.listenerAttached) {
                         newSelect.addEventListener('change', updateRegionSelectionVisibilityBasedOnAllRows);
                         newSelect.dataset.listenerAttached = 'true';
                     }
                }

                // Populate the target row
                const typeSelect = targetRow.querySelector('select[name="report_type[]"]');
                const fromInput = targetRow.querySelector('input[name="from_date[]"]');
                const toInput = targetRow.querySelector('input[name="to_date[]"]');
                const chunkInput = targetRow.querySelector('input[name="chunk_size[]"]');

                if (typeSelect) typeSelect.value = reportInfo.report_type || '';
                if (fromInput) fromInput.value = reportInfo.from_date || '';
                if (toInput) toInput.value = reportInfo.to_date || '';
                if (chunkInput) chunkInput.value = reportInfo.chunk_size || '5';
            });
        } else {
             console.log("Loaded configuration has no reports.");
             // Ensure first row remains reset/empty
        }

        // Update region visibility based on the newly applied report types
        updateRegionSelectionVisibilityBasedOnAllRows();

        // Apply saved region selections (needs slight delay for DOM update)
        setTimeout(() => {
            if (regionSelectionDiv && regionSelectionDiv.style.display === 'block') {
                 if (configData.regions && Array.isArray(configData.regions)) {
                     const regionCheckboxes = regionSelectionDiv.querySelectorAll('input[name="regions"]');
                     regionCheckboxes.forEach(checkbox => {
                         // Check if checkbox value (string index) exists in the loaded regions array
                         checkbox.checked = configData.regions.includes(checkbox.value);
                     });
                     console.log("Applied saved regions:", configData.regions);
                 }
            }
        }, 100); // 100ms delay

        addStatusMessage("Configuration loaded successfully.", false, true);
    }

    // --- Scheduling Logic ---

    /** Fetches and displays the list of active schedules. */
    async function fetchAndDisplaySchedules() {
        if (!schedulesList) return; // Element check
        schedulesList.innerHTML = '<li>Loading schedules...</li>';
        try {
            const data = await fetchData('/get-schedules');
            schedulesList.innerHTML = ''; // Clear loading/previous list
            if (data.status === 'success' && data.schedules && data.schedules.length > 0) {
                data.schedules.forEach(job => {
                    const li = document.createElement('li');

                    // Format next run time (assuming ISO string from backend)
                    let nextRunText = 'N/A';
                    if (job.next_run_time) {
                        try {
                            // Display in local time using browser's locale
                            nextRunText = new Date(job.next_run_time).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
                        } catch (e) {
                            console.warn("Could not format next_run_time:", job.next_run_time, e);
                            nextRunText = job.next_run_time; // Fallback to ISO string
                        }
                    }

                    // Create text span with job info
                    const textSpan = document.createElement('span');
                    // Display config name from job args
                    const configArg = job.args && job.args.length > 0 ? job.args[0] : 'Unknown Config';
                    textSpan.textContent = `Config: "${configArg}" - Next Run: ${nextRunText}`;
                    textSpan.className = 'schedule-info'; // Add class for styling

                    // Create cancel button
                    const cancelButton = document.createElement('button');
                    cancelButton.textContent = 'Cancel';
                    cancelButton.className = 'delete-button cancel-schedule-button'; // Use classes for styling/selection
                    cancelButton.dataset.jobId = job.id; // Store job ID for cancellation
                    cancelButton.title = `Cancel schedule ${job.id}`;

                    li.appendChild(textSpan);
                    li.appendChild(cancelButton);
                    schedulesList.appendChild(li);
                });
            } else {
                schedulesList.innerHTML = '<li>No active schedules found.</li>';
            }
        } catch (error) {
            schedulesList.innerHTML = '<li>Error loading schedules.</li>';
            // Error message already shown by fetchData
        }
     }


    // --- Event Listeners ---

    // Download Form Submit
    if (form) {
        form.addEventListener('submit', handleDownloadFormSubmit);
    }

    // Refresh Log Button
    if (refreshLogButton) {
        refreshLogButton.addEventListener('click', fetchLogs);
    }

    // Report Type Change (Event Delegation on Table)
    if (reportTable) {
         reportTable.addEventListener('change', (event) => {
             if (event.target && event.target.matches("select[name='report_type[]']")) {
                 updateRegionSelectionVisibilityBasedOnAllRows();
             }
         });
    }

    // --- Configuration Management Buttons ---
    if (saveConfigButton) {
        saveConfigButton.addEventListener('click', async () => {
            const configName = configNameInput.value.trim();
            if (!configName) { alert("Please enter a configuration name."); return; }
            const configData = getCurrentFormData();
             if (!configData.reports || configData.reports.length === 0) {
                 alert("Please configure at least one valid report before saving."); return;
             }
            try {
                const result = await fetchData('/save-config', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ config_name: configName, config_data: configData })
                });
                if (result.status === 'success') {
                    addStatusMessage(result.message, false, true);
                    configNameInput.value = ''; // Clear name input
                    fetchAndPopulateConfigs(); // Refresh config dropdowns
                }
            } catch (error) { /* Handled by fetchData */ }
        });
     }

    if (loadConfigButton) {
         loadConfigButton.addEventListener('click', async () => {
            const selectedConfigName = savedConfigsDropdown.value;
            if (!selectedConfigName) { alert("Please select a configuration to load."); return; }
            try {
                 const result = await fetchData(`/load-config/${selectedConfigName}`);
                 if (result.status === 'success' && result.config_data) {
                     applyConfiguration(result.config_data);
                 } else {
                      // Handle case where config_data might be missing even if status is success (though API shouldn't do that)
                      addStatusMessage(result.message || `Could not load config ${selectedConfigName}.`, true);
                      console.error("Failed to load config or config_data missing:", result);
                 }
            } catch (error) { /* Handled by fetchData */ }
        });
    }

    if (deleteConfigButton) {
        deleteConfigButton.addEventListener('click', async () => {
            const selectedConfigName = savedConfigsDropdown.value;
            if (!selectedConfigName) { alert("Please select a configuration to delete."); return; }
            if (!confirm(`Are you sure you want to delete configuration "${selectedConfigName}"?`)) { return; }
            try {
                 // Use await with fetchData
                 const result = await fetchData(`/delete-config/${selectedConfigName}`, { method: 'DELETE' });
                 // Check result status explicitly
                 if (result && result.status === 'success') {
                     addStatusMessage(result.message || `Configuration "${selectedConfigName}" deleted.`, false, true);
                     fetchAndPopulateConfigs(); // Refresh config dropdowns
                 }
                 // No else needed, fetchData handles API errors
            } catch (error) { /* Handled by fetchData */ }
        });
     }

    // --- Scheduling Buttons ---
    if (scheduleButton) {
        scheduleButton.addEventListener('click', async () => {
            const configName = scheduleConfigSelect.value;
            const runDateTime = scheduleDateTimeInput.value; // Format: YYYY-MM-DDTHH:MM

            // Validation
            if (!configName) { alert("Please select a saved configuration to schedule."); return; }
            if (!runDateTime) { alert("Please select a date and time to run the job."); return; }
            try {
                const selectedDate = new Date(runDateTime);
                // Add a small buffer (e.g., 1 minute) to avoid scheduling exactly 'now'
                const bufferMinutes = 1;
                const minDate = new Date(Date.now() + bufferMinutes * 60 * 1000);
                if (selectedDate <= minDate) {
                    alert(`Please select a time at least ${bufferMinutes} minute(s) in the future.`);
                    return;
                }
            } catch (e) { alert("Invalid date/time format."); return; }

            console.log(`Scheduling config: ${configName} at ${runDateTime}`);
            try {
                const result = await fetchData('/schedule-job', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        config_name: configName,
                        trigger_type: 'date', // Only 'date' trigger supported currently
                        run_datetime: runDateTime
                    })
                });
                if (result.status === 'success') {
                    addStatusMessage(result.message || `Job scheduled for ${configName}.`, false, true);
                    fetchAndDisplaySchedules(); // Refresh the schedule list
                    // Optionally clear inputs
                    scheduleConfigSelect.value = '';
                    scheduleDateTimeInput.value = '';
                }
            } catch (error) { /* Handled by fetchData */ }
        });
     }

    // Cancel Schedule Button (Event Delegation)
    if (schedulesList) {
        schedulesList.addEventListener('click', async (event) => {
            // Check if the clicked element is a cancel button
            if (event.target && event.target.classList.contains('cancel-schedule-button')) {
                const jobId = event.target.dataset.jobId;
                if (!jobId) { console.error("Could not find job ID on cancel button."); return; }
                if (!confirm(`Are you sure you want to cancel schedule ${jobId}?`)) { return; }

                console.log(`Cancelling schedule: ${jobId}`);
                try {
                    const result = await fetchData(`/cancel-schedule/${jobId}`, { method: 'DELETE' });
                     // Check result status
                     if (result && result.status === 'success') {
                         addStatusMessage(result.message || `Job ${jobId} cancelled.`, false, true);
                         fetchAndDisplaySchedules(); // Refresh the list
                     }
                    // No else needed, fetchData handles API errors
                } catch (error) { /* Handled by fetchData */ }
            }
        });
     }

    // --- Event Listeners for Add/Remove Row (Moved from inline) ---
    if (addRowButton) {
        addRowButton.addEventListener("click", function () {
            if (!reportTableBody) return;
            const firstRow = reportTableBody.querySelector("tr");
            if (!firstRow) { console.error("Cannot add row: Template row not found."); return; }

            const newRow = firstRow.cloneNode(true); // Clone template

            // Reset values and set defaults for the new row
            const reportSelect = newRow.querySelector("select[name='report_type[]']");
            const chunkSizeInput = newRow.querySelector("input[name='chunk_size[]']");
            if(reportSelect) reportSelect.selectedIndex = 0;
            setDefaultDates(newRow); // Set default dates
            if(chunkSizeInput) chunkSizeInput.value = "5";

            // Add change listener to the *new* select dropdown
            const newSelect = newRow.querySelector("select[name='report_type[]']");
            if (newSelect && !newSelect.dataset.listenerAttached) {
                newSelect.addEventListener('change', updateRegionSelectionVisibilityBasedOnAllRows);
                newSelect.dataset.listenerAttached = 'true';
            }

            reportTableBody.appendChild(newRow);
            updateRegionSelectionVisibilityBasedOnAllRows(); // Update UI
        });
    }

    if (reportTable) { // Use table reference for delegation
        reportTable.addEventListener("click", function (event) {
            if (event.target.classList.contains("remove-row-button")) {
                const row = event.target.closest("tr");
                // Prevent removing the last row
                if (reportTableBody && reportTableBody.querySelectorAll("tr").length > 1) {
                    row.remove();
                    updateRegionSelectionVisibilityBasedOnAllRows(); // Update UI
                } else {
                    alert("Must have at least one report configuration row.");
                }
            }
        });
    }

    // --- Initial Page Setup ---
    console.log("Initializing page...");
    fetchAndPopulateReportData(); // Fetch reports & set initial dates
    fetchLogs();                  // Fetch download history
    fetchAndPopulateConfigs();    // Fetch saved configurations
    fetchAndDisplaySchedules();   // Fetch active schedules

}); // End DOMContentLoaded
