document.addEventListener('DOMContentLoaded', () => {
    // Get references to DOM elements
    const form = document.getElementById('download-form');
    // Helper: fill options for a select element
    function fillReportOptions(selectElement, reportNames) {
        selectElement.innerHTML = '<option value="">-- Choose --</option>';
        reportNames.forEach(reportName => {
            const option = document.createElement('option');
            option.value = reportName;
            option.textContent = reportName;
            selectElement.appendChild(option);
        });
    }

    // No longer use a fixed id for report select
    // const reportSelect = document.getElementById('report_type');
    const regionSelectionDiv = document.getElementById('region-selection');
    const downloadButton = document.getElementById('download-button');
    const loadingIndicator = document.getElementById('loading-indicator');
    const statusMessagesDiv = document.getElementById('status-messages');
    const logTableContainer = document.getElementById('log-table-container');
    const refreshLogButton = document.getElementById('refresh-log-button');

    let reportDataCache = null; // Cache for report/region data from backend
    let sseConnection = null; // Variable to hold the Server-Sent Events connection

    // --- Function to fetch report and region data ---
    function fetchReportData() {
        fetch('/get-reports-regions')
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                reportDataCache = data; // Store the fetched data
                populateAllReportDropdowns(data.reports);
                // Gọi lại sau 200ms để chắc chắn các select đã render xong
                setTimeout(() => {
                    if (reportDataCache && reportDataCache.reports) {
                        populateAllReportDropdowns(reportDataCache.reports);
                    }
                }, 200);
            })
            .catch(error => {
                console.error('Error fetching report data:', error);
                addStatusMessage("Error loading report list from backend.", true);
            });
    }

    // --- Populate all report_type[] selects (initial and new rows) ---
    function populateAllReportDropdowns(reportNames) {
        console.log('Populating report dropdowns with:', reportNames);
        const selects = document.querySelectorAll("select[name='report_type[]']");
        console.log('Found selects:', selects);
        selects.forEach(sel => {
            fillReportOptions(sel, reportNames);
        });
    }

    // --- Function to update visibility and content of region selection ---
    function updateRegionSelectionVisibility(e) {
        // Lấy select vừa thay đổi, fallback về null nếu không có event
        const select = e && e.target ? e.target : null;
        // Nếu không có select, không làm gì
        if (!select) return;
        const selectedReportKey = select.value;
        regionSelectionDiv.innerHTML = '<label>Select Region(s):</label><br>'; // Reset content
        regionSelectionDiv.style.display = 'none'; // Hide by default

        if (!selectedReportKey || !reportDataCache) return;

        const reportUrl = reportDataCache.report_urls_map[selectedReportKey];

        // Check if the selected report's URL requires region selection
        if (reportDataCache.region_required_urls.includes(reportUrl)) {
            regionSelectionDiv.style.display = 'block'; // Show the div
            // Populate with checkboxes
            for (const [index, name] of Object.entries(reportDataCache.regions)) {
                const checkboxId = `region-${index}`;
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.id = checkboxId;
                checkbox.name = 'regions'; // Group checkboxes
                checkbox.value = index;    // The value sent to backend is the index

                const label = document.createElement('label');
                label.htmlFor = checkboxId;
                label.textContent = name;
                label.style.marginLeft = '5px'; // Add some spacing

                regionSelectionDiv.appendChild(checkbox);
                regionSelectionDiv.appendChild(label);
                regionSelectionDiv.appendChild(document.createElement('br'));
            }
        }
    }

    // --- Function to handle form submission ---
    async function handleDownloadFormSubmit(event) {
        event.preventDefault(); // Prevent default form submission

        // Null check cho form nếu cần
        if (!form) {
            addStatusMessage("Form not found!", true);
            return;
        }

        // Close any existing SSE connection
        if (sseConnection) {
            sseConnection.close();
            console.log("Closed previous SSE connection.");
        }

        downloadButton.disabled = true;
        loadingIndicator.style.display = 'inline';
        statusMessagesDiv.innerHTML = '<p>Submitting request...</p>'; // Initial status

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries()); // Convert form data to object

        // Collect selected region indices
        const selectedRegionCheckboxes = regionSelectionDiv.querySelectorAll('input[name="regions"]:checked');
        data.regions = Array.from(selectedRegionCheckboxes).map(cb => cb.value);

        // Ensure chunk_size is sent (even if empty, backend handles default)
        data.chunk_size = document.getElementById('chunk_size').value.trim();


        try {
            const response = await fetch('/start-download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data), // Send data as JSON
            });

            const result = await response.json(); // Parse JSON response from backend

            if (response.ok && result.status === 'started') {
                addStatusMessage("Request accepted. Waiting for status updates...");
                initializeSSEListener(); // Start listening for status updates
            } else {
                throw new Error(result.message || `Server responded with status ${response.status}`);
            }
        } catch (error) {
            console.error('Error initiating download:', error);
            addStatusMessage(`Error: ${error.message}`, true);
            downloadButton.disabled = false; // Re-enable button on error
            loadingIndicator.style.display = 'none';
        }
    }

    // --- Function to initialize the Server-Sent Events listener ---
    function initializeSSEListener() {
        statusMessagesDiv.innerHTML = ''; // Clear previous messages
        sseConnection = new EventSource('/stream-status'); // Connect to the SSE endpoint

        sseConnection.onopen = function() {
             console.log("SSE connection established.");
             addStatusMessage("Connected to status stream...");
         };

        sseConnection.onmessage = function(event) {
            // Handle received status messages
            const message = event.data;
            if (message === "FINISHED") {
                addStatusMessage("--- PROCESS COMPLETED ---");
                sseConnection.close(); // Close connection on finish signal
                downloadButton.disabled = false; // Re-enable button
                loadingIndicator.style.display = 'none';
                fetchLogs(); // Refresh logs when finished
            } else {
                addStatusMessage(message); // Display the status message
            }
        };

        sseConnection.onerror = function(error) {
            console.error('SSE Error:', error);
            addStatusMessage("Status stream connection error. Check console.", true);
            if (sseConnection) sseConnection.close(); // Close on error
            downloadButton.disabled = false; // Re-enable button
            loadingIndicator.style.display = 'none';
        };
    }

     // --- Function to add a message to the status display area ---
     function addStatusMessage(message, isError = false) {
         const p = document.createElement('p');
         p.textContent = message;
         if (isError) {
             p.style.color = 'red';
             p.style.fontWeight = 'bold';
         }
         statusMessagesDiv.appendChild(p);
         // Auto-scroll to the bottom
         statusMessagesDiv.scrollTop = statusMessagesDiv.scrollHeight;
     }

    // --- Function to fetch and display download logs ---
    function fetchLogs() {
        logTableContainer.innerHTML = '<p>Loading logs...</p>'; // Indicate loading
        fetch('/get-logs')
            .then(response => {
                 if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                 return response.json();
            })
            .then(data => {
                logTableContainer.innerHTML = ''; // Clear loading message or previous table
                if (data.status === 'success' && data.logs && data.logs.length > 0) {
                    createLogTable(data.logs);
                } else if (data.status === 'success' || data.status === 'warning') {
                    logTableContainer.innerHTML = `<p>${data.message || 'No log entries found.'}</p>`;
                }
                 else { // Handle error status from backend
                    throw new Error(data.message || 'Unknown error fetching logs');
                }
            })
            .catch(error => {
                console.error('Error fetching logs:', error);
                logTableContainer.innerHTML = `<p style="color: red;">Error loading logs: ${error.message}</p>`;
            });
    }

    // --- Function to create and populate the log table ---
    function createLogTable(logData) {
        const table = document.createElement('table');
        table.className = 'log-table'; // Add class for styling

        // Create table header
        const thead = table.createTHead();
        const headerRow = thead.insertRow();
        // Assuming all log entries have the same keys, use the first entry to get headers
        const headers = Object.keys(logData[0]);
        headers.forEach(headerText => {
            const th = document.createElement('th');
            th.textContent = headerText;
            headerRow.appendChild(th);
        });

        // Create table body
        const tbody = table.createTBody();
        logData.forEach(logEntry => {
            const row = tbody.insertRow();
            headers.forEach(header => {
                const cell = row.insertCell();
                cell.textContent = logEntry[header] !== null ? logEntry[header] : ''; // Handle null values
            });
        });

        logTableContainer.appendChild(table);
    }

    // --- Attach Event Listeners ---
    // Lắng nghe thay đổi trên tất cả các select[name='report_type[]'] trong bảng bằng event delegation
    document.getElementById('report-table').addEventListener('change', function(e) {
        if (e.target && e.target.name === 'report_type[]') {
            updateRegionSelectionVisibility(e);
        }
    });
    form.addEventListener('submit', handleDownloadFormSubmit);       // Handle form submission
    refreshLogButton.addEventListener('click', fetchLogs);             // Handle log refresh button click

    // --- Initial Setup ---
    fetchReportData(); // Fetch report list on page load
    fetchLogs();       // Fetch initial logs on page load
});