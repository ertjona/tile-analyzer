// frontend/main.js
console.log("main.js script loaded."); // <-- ADD THIS LINE

// --- State Management ---
let currentPage = 1;
let currentRequestState = {
    filters: [],
    sort: [{ key: "json_filename", order: "asc" }],
    page: 1,
    limit: 100
};
let currentResultsData = [];
let EXPORT_CSV_LIMIT = 50000; // Default fallback

const ALL_COLUMNS = [
    { key: 'id', label: 'ID' },
    { key: 'json_filename', label: 'JSON Filename' },
    { key: 'webp_filename', label: 'WebP Filename' },
    { key: 'status', label: 'Status' },
    { key: 'col', label: 'Column' },
    { key: 'row', label: 'Row' },
    { key: 'size', label: 'Size' },
    { key: 'entropy', label: 'Entropy' },
    { key: 'laplacian', label: 'Laplacian' },
    { key: 'avg_brightness', label: 'Avg Brightness' },
    { key: 'avg_saturation', label: 'Avg Saturation' },
    { key: 'edge_density', label: 'Edge Density' },
	{ key: 'edge_density_3060', label: 'Edge Density 3060' },
	{ key: 'foreground_ratio', label: 'Foreground Ratio' },
	{ key: 'max_subject_area', label: 'Max Subject Area' }
];

// --- Main Setup ---
window.onload = function() {
	console.log("window.onload is executing."); // <-- ADD THIS LINE
    setupEventListeners();
    populateDisplayOptions();
    addFilterRow();
	fetchSourceFiles(); 
	fetchExportLimits(); // Add this line
    fetchAndDisplayTiles();
};

// --- NEW Function to fetch export limits from backend ---
async function fetchExportLimits() {
    try {
        const response = await fetch('/api/export/limits');
        if (!response.ok) throw new Error('Failed to fetch export limits.');
        const limits = await response.json();
        EXPORT_CSV_LIMIT = limits.export_csv_limit;
    } catch (error) {
        console.error("Error fetching export limits:", error);
        // The default limit will be used as a fallback
    }
}

// --- NEW: Function to fetch filenames and populate the dropdown ---
async function fetchSourceFiles() {
    try {
        const response = await fetch('/api/source_files');
        if (!response.ok) throw new Error('Failed to fetch source files.');
        const filenames = await response.json();
        
        const selectElement = document.getElementById('filename-filter');
        filenames.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            selectElement.appendChild(option);
        });
    } catch (error) {
        console.error("Error fetching source files:", error);
    }
}

function handleFilterSubmit(event) {
    event.preventDefault(); 
    currentPage = 1; 

    const filters = [];
    
    // Check the dedicated filename filter
    const filenameFilter = document.getElementById('filename-filter').value;
    if (filenameFilter) {
        // MODIFIED: Send a clean key without the 'S.' prefix
        filters.push({ key: 'json_filename', op: '==', value: filenameFilter });
    }

    // Read from multiple metric filter rows
    document.querySelectorAll('.metric-filter-row').forEach(row => {
        const key = row.querySelector('.filter-key').value;
        const op = row.querySelector('.filter-op').value;
        const value = row.querySelector('.filter-value').value;

        const numericValue = parseFloat(value);
        if (!isNaN(numericValue)) {
            // MODIFIED: Send a clean key without the 'T.' prefix
            filters.push({ key: key, op: op, value: numericValue });
        }
    });
    
    // --- DELETE THE SORT LOGIC FROM HERE ---
	// const sortKey = document.getElementById('sort-key').value;
    // const sortOrder = document.getElementById('sort-order').value;

    currentRequestState = {
        filters: filters,
        // The sort state is now handled by handleSortClick, so we just keep the existing sort order
        sort: currentRequestState.sort,
        page: currentPage,
        limit: 100
    };
    
    fetchAndDisplayTiles();
}

function setupEventListeners() {
    // --- Listeners from the first original function ---
    document.getElementById('filter-form').addEventListener('submit', handleFilterSubmit);
    document.getElementById('add-filter-btn').addEventListener('click', addFilterRow);

    // --- Listeners from the second original function ---
    document.getElementById('prev-button').addEventListener('click', handlePrevClick);
    document.getElementById('next-button').addEventListener('click', handleNextClick);
    document.getElementById('results-body').addEventListener('click', handleRowClick);
    document.getElementById('go-to-page-btn').addEventListener('click', handleGoToPage);

    // Dynamic filter row removal
    document.getElementById('filter-container').addEventListener('click', function(event) {
        if (event.target.classList.contains('remove-filter-btn')) {
            event.target.parentElement.remove();
        }
    });

    // Display options dropdown
    const displayBtn = document.getElementById('display-options-btn');
    const displayDropdown = document.getElementById('display-options-dropdown');
    displayBtn.onclick = () => displayDropdown.classList.toggle('show');
    displayDropdown.addEventListener('change', () => renderTable(currentResultsData));

    window.addEventListener('click', (event) => {
        if (!event.target.matches('#display-options-btn')) {
            if (displayDropdown.classList.contains('show')) {
                displayDropdown.classList.remove('show');
            }
        }
    });

    // Modal close button
    const modal = document.getElementById('inspector-modal');
    const closeBtn = document.querySelector('.close-button');
    closeBtn.onclick = () => modal.style.display = "none";
    window.addEventListener('click', (event) => {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    });

    // Table header for sorting
    document.querySelector('#results-table thead').addEventListener('click', handleSortClick);

    // --- The new event listener for the export button ---
    document.getElementById('export-csv-btn').addEventListener('click', handleExportCsv);
}

// --- All Helper Functions ---

function populateDisplayOptions() {
    const defaultVisible = ['json_filename', 'webp_filename', 'edge_density', 'edge_density_3060', 'avg_brightness', 'size', 'laplacian', 'max_subject_area']; // MODIFIED
    const container = document.getElementById('display-options-dropdown');
    let content = '';
    ALL_COLUMNS.forEach(col => {
        const isChecked = defaultVisible.includes(col.key) ? 'checked' : '';
        content += `
            <label>
                <input type="checkbox" class="column-toggle" value="${col.key}" ${isChecked}>
                ${col.label}
            </label>
        `;
    });
    container.innerHTML = content;
}

function addFilterRow() {
    const container = document.getElementById('filter-container');
    const newFilterRow = document.createElement('div');
    // --- BEFORE ---
	// newFilterRow.className = 'filter-row';
	// --- AFTER ---
	newFilterRow.className = 'filter-row metric-filter-row'; // Add the new specific class
    newFilterRow.innerHTML = `
        <label>Filter by:</label>
        <select class="filter-key">
            <option value="col">Column</option>
			<option value="row">Row</option>
			<option value="edge_density">Edge Density</option>
			<option value="edge_density_3060">Edge Density 3060</option>
            <option value="entropy">Entropy</option>
            <option value="laplacian">Laplacian</option>
            <option value="avg_brightness">Avg. Brightness</option>
            <option value="avg_saturation">Avg. Saturation</option>
			<option value="size">Size</option>
			<option value="foreground_ratio">Foreground Ratio</option>
			<option value="max_subject_area">Max Subject Area</option>
        </select>
        <select class="filter-op">
            <option value=">">&gt;</option>
            <option value="<">&lt;</option>
			<option value=">=">&ge;</option>
            <option value="<=">&le;</option>
			<option value="==">==</option>
            <option value="!=">!=</option>
        </select>
        <input type="number" class="filter-value" step="any" placeholder="Enter value">
        <button type="button" class="remove-filter-btn" style="margin-left: 10px;">&times;</button>
    `;
    container.appendChild(newFilterRow);
}


function handlePrevClick() {
    if (currentPage > 1) {
        currentPage--;
        fetchAndDisplayTiles();
    }
}

function handleNextClick() {
    currentPage++;
    fetchAndDisplayTiles();
}

function handleRowClick(event) {
    const row = event.target.closest('tr');
    if (!row || !row.dataset.tileData) return;
    const tile = JSON.parse(row.dataset.tileData);
    const modal = document.getElementById('inspector-modal');
    const img = document.getElementById('inspector-image');
    const metadata = document.getElementById('inspector-metadata');
    img.src = `/images/${tile.source_file_id}/${tile.webp_filename}`;
    let detailsHtml = '';
    for (const [key, value] of Object.entries(tile)) {
        detailsHtml += `${key.padEnd(20)}: ${value}\n`;
    }
    metadata.textContent = detailsHtml;
    modal.style.display = "block";
}

// Add this new function to main.js

function handleSortClick(event) {
    const headerCell = event.target.closest('th');
    if (!headerCell || !headerCell.dataset.sortKey) return; // Exit if not a sortable header

    const sortKey = headerCell.dataset.sortKey;
    let sortOrder = 'asc';

    // If we're already sorting by this key, reverse the order
    const currentSort = currentRequestState.sort[0];
    if (currentSort && currentSort.key === sortKey) {
        sortOrder = currentSort.order === 'asc' ? 'desc' : 'asc';
    }

    // Update the state and re-fetch
    currentRequestState.sort = [{ key: sortKey, order: sortOrder }];
    fetchAndDisplayTiles();
}

// Add this new function to main.js

function handleGoToPage() {
    const pageInput = document.getElementById('page-input');
    const pageNum = parseInt(pageInput.value, 10);

    // Get the total number of pages from the page-info span
    const pageInfo = document.getElementById('page-info').textContent;
    const totalPages = parseInt(pageInfo.split(' of ')[1], 10);

    // Validate the user's input
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
        currentPage = pageNum;
        fetchAndDisplayTiles();
        pageInput.value = ''; // Clear the input box after jumping
    } else {
        alert(`Invalid page number. Please enter a number between 1 and ${totalPages}.`);
    }
}

// In frontend/main.js

async function handleExportCsv() {
    console.log("handleExportCsv function called."); // Log: Function starts

    const exportBtn = document.getElementById('export-csv-btn');
    exportBtn.disabled = true;
    exportBtn.textContent = 'Exporting...';

    const requestBody = {
        filters: currentRequestState.filters,
        sort: currentRequestState.sort
    };

    console.log("Sending export request to backend with state:", requestBody); // Log: What is being sent

    try {
        const response = await fetch('/api/export/csv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        console.log("Received response from backend with status:", response.status); // Log: Backend responded

        if (!response.ok) {
            // Try to get detailed error message from backend
            const errorData = await response.json().catch(() => ({ detail: "Unknown server error." }));
            throw new Error(errorData.detail || `Export failed with status: ${response.status}`);
        }

        // Create a blob from the response to trigger the download
        const blob = await response.blob();
        console.log("CSV data converted to blob with size:", blob.size); // Log: Blob created

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;

        // Get filename from Content-Disposition header
        const disposition = response.headers.get('Content-Disposition');
        let filename = 'tile_export.csv';
        if (disposition && disposition.includes('attachment')) {
            const filenameMatch = disposition.match(/filename="(.+?)"/);
            if (filenameMatch && filenameMatch.length > 1) {
                filename = filenameMatch[1];
            }
        }
        a.download = filename;
        console.log("Triggering download for file:", filename); // Log: Download initiated

        document.body.appendChild(a);
        a.click();

        // Cleanup
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

    } catch (error) {
        // This will now catch any error from the fetch or blob creation
        console.error('Error during CSV export:', error);
        alert(`Failed to export CSV: ${error.message}`);
    } finally {
        // Ensure the button is always re-enabled
        exportBtn.disabled = false;
        exportBtn.textContent = 'Export to CSV';
    }
}

// In tile-analyzer/frontend/main.js

async function fetchAndDisplayTiles() {
    const tableBody = document.getElementById('results-body');
    const exportBtn = document.getElementById('export-csv-btn');
    const summaryElement = document.getElementById('results-summary');

    // Reset UI for loading state
    tableBody.innerHTML = `<tr><td colspan="12">Loading...</td></tr>`;
    document.getElementById('prev-button').disabled = true;
    document.getElementById('next-button').disabled = true;
    exportBtn.disabled = true;
    summaryElement.textContent = 'Fetching data...';

    currentRequestState.page = currentPage;

    try {
        const response = await fetch('/api/tiles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentRequestState)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // The logic for the summary message has been REMOVED from here.

        currentResultsData = data;
        renderTable(currentResultsData); // This function will now handle the summary message.

    } catch (error) {
        console.error('Error fetching data:', error);
        tableBody.innerHTML = '<tr><td colspan="12" style="color: red;">Failed to load data. Check console for details.</td></tr>';
        summaryElement.textContent = 'Error loading data.';
    }
}

// In tile-analyzer/frontend/main.js

function renderTable(data) {
    const tableHead = document.querySelector('#results-table thead');
    const tableBody = document.getElementById('results-body');
    const summaryElement = document.getElementById('results-summary');
    const exportBtn = document.getElementById('export-csv-btn');
    tableBody.innerHTML = '';

    // --- Logic to get visible columns (Restored) ---
    const visibleColumns = Array.from(document.querySelectorAll('.column-toggle:checked')).map(cb => cb.value);
    const currentSort = currentRequestState.sort[0] || { key: 'id', order: 'asc' };

    // --- Logic to build table header (Restored) ---
    let headerHtml = '<tr><th>Thumbnail</th>';
    visibleColumns.forEach(key => {
        const column = ALL_COLUMNS.find(c => c.key === key);
        if (column) { // Check if column exists to prevent errors
            let sortIndicator = '';
            if (column.key === currentSort.key) {
                sortIndicator = currentSort.order === 'asc' ? ' &uarr;' : ' &darr;';
            }
            headerHtml += `<th data-sort-key="${column.key}" style="cursor: pointer;">${column.label}${sortIndicator}</th>`;
        }
    });
    headerHtml += '</tr>';
    tableHead.innerHTML = headerHtml;
    // --- End of restored logic ---

    // --- Centralized summary and button logic ---
    if (data.total_results > 0) {
        if (data.total_results > EXPORT_CSV_LIMIT) {
            exportBtn.disabled = true;
            summaryElement.innerHTML = `Found ${data.total_results.toLocaleString()} matching tiles. <strong style="color: red;">Please apply more filters to enable CSV export (limit: ${EXPORT_CSV_LIMIT.toLocaleString()}).</strong>`;
        } else {
            exportBtn.disabled = false;
            summaryElement.textContent = `Found ${data.total_results.toLocaleString()} matching tiles.`;
        }
    } else {
        exportBtn.disabled = true;
        summaryElement.textContent = 'Found 0 matching tiles.';
    }

    // --- Logic to build table body ---
    if (data.results && data.results.length > 0) {
        data.results.forEach(tile => {
            const row = document.createElement('tr');
            row.dataset.tileData = JSON.stringify(tile);

            // Start row with the thumbnail image
            let rowHtml = `<td><img src="/images/${tile.source_file_id}/${tile.webp_filename}" class="results-thumbnail" loading="lazy"></td>`;

            // Add the other visible columns (This will now work correctly)
            visibleColumns.forEach(key => {
                let value = tile[key];
                if (value == null) {
                    value = 'N/A';
                } else if (typeof value === 'number' && !['id', 'col', 'row', 'size', 'source_file_id'].includes(key)) {
                    value = value.toFixed(6);
                }
                rowHtml += `<td>${value}</td>`;
            });

            row.innerHTML = rowHtml;
            tableBody.appendChild(row);
        });

        // --- Pagination Logic ---
        const totalPages = Math.ceil(data.total_results / data.limit);
        document.getElementById('page-info').textContent = `Page ${data.page} of ${totalPages}`;
        document.getElementById('prev-button').disabled = data.page <= 1;
        document.getElementById('next-button').disabled = data.page >= totalPages;

    } else {
        const columnCount = visibleColumns.length + 1;
        tableBody.innerHTML = `<tr><td colspan="${columnCount}">No results found.</td></tr>`;
        document.getElementById('page-info').textContent = 'Page 1 of 1';
    }
}