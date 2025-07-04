// frontend/main.js

// --- State Management ---
let currentPage = 1;
let currentRequestState = {
    filters: [],
    sort: [{ key: "json_filename", order: "asc" }],
    page: 1,
    limit: 100
};
let currentResultsData = [];
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
	{ key: 'foreground_ratio', label: 'Foreground Ratio' }
];

// --- Main Setup ---
window.onload = function() {
    setupEventListeners();
    populateDisplayOptions();
    addFilterRow();
	fetchSourceFiles(); // NEW: Fetch filenames for the dropdown
    fetchAndDisplayTiles();
};


function setupEventListeners() {
    // ... (This function remains the same as before) ...
    document.getElementById('filter-form').addEventListener('submit', handleFilterSubmit);
    document.getElementById('add-filter-btn').addEventListener('click', addFilterRow);
    // ... etc.
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
    document.getElementById('filter-form').addEventListener('submit', handleFilterSubmit);
    document.getElementById('add-filter-btn').addEventListener('click', addFilterRow);
    document.getElementById('prev-button').addEventListener('click', handlePrevClick);
    document.getElementById('next-button').addEventListener('click', handleNextClick);
    document.getElementById('results-body').addEventListener('click', handleRowClick);
	document.getElementById('go-to-page-btn').addEventListener('click', handleGoToPage);

    document.getElementById('filter-container').addEventListener('click', function(event) {
        if (event.target.classList.contains('remove-filter-btn')) {
            event.target.parentElement.remove();
        }
    });

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
    
    const modal = document.getElementById('inspector-modal');
    const closeBtn = document.querySelector('.close-button');
    closeBtn.onclick = () => modal.style.display = "none";
    window.addEventListener('click', (event) => {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    });
	
	// NEW: Add a listener to the table header for sorting
    document.querySelector('#results-table thead').addEventListener('click', handleSortClick);
}

// --- All Helper Functions ---

function populateDisplayOptions() {
    const defaultVisible = ['json_filename', 'webp_filename', 'edge_density', 'avg_brightness', 'size'];
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
            <option value="edge_density">Edge Density</option>
            <option value="entropy">Entropy</option>
            <option value="laplacian">Laplacian</option>
            <option value="avg_brightness">Avg. Brightness</option>
            <option value="avg_saturation">Avg. Saturation</option>
			<option value="size">Size</option>
			<option value="foreground_ratio">Foreground Ratio</option>
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

async function fetchAndDisplayTiles() {
    const tableBody = document.getElementById('results-body');
    tableBody.innerHTML = `<tr><td colspan="12">Loading...</td></tr>`; 
    document.getElementById('prev-button').disabled = true;
    document.getElementById('next-button').disabled = true;

    currentRequestState.page = currentPage;

    try {
        const response = await fetch('/api/tiles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentRequestState)
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();

        currentResultsData = data; 
        renderTable(currentResultsData);

    } catch (error) {
        console.error('Error fetching data:', error);
        tableBody.innerHTML = '<tr><td colspan="12" style="color: red;">Failed to load data.</td></tr>';
    }
}

function renderTable(data) {
    const tableHead = document.querySelector('#results-table thead');
    const tableBody = document.getElementById('results-body');
    const summaryElement = document.getElementById('results-summary');
    tableBody.innerHTML = '';

    // Step 1: Get the currently active sort from our global state object.
    // If no sort is active yet, we default to sorting by 'id' ascending.
    const currentSort = currentRequestState.sort[0] || { key: 'id', order: 'asc' };

    // Step 2: Get the list of columns the user wants to see from the checkboxes.
    const visibleColumns = Array.from(document.querySelectorAll('.column-toggle:checked')).map(cb => cb.value);

    // --- This is the main new logic block ---
    // Step 3: Build the header HTML string dynamically.
    let headerHtml = '<tr><th>Thumbnail</th>'; // Start with the non-sortable Thumbnail column.

    visibleColumns.forEach(key => {
        // Find the full column object (which has the label) for the current key.
        const column = ALL_COLUMNS.find(c => c.key === key);
        let sortIndicator = ''; // Default to no arrow.

        // If the current column we are building is the one we are sorting by...
        if (column.key === currentSort.key) {
            // ...then add the correct up or down arrow.
            sortIndicator = currentSort.order === 'asc' ? ' &uarr;' : ' &darr;';
        }
        
        // Create the full <th> tag with the data-sort-key attribute, the label, and the arrow.
        headerHtml += `<th data-sort-key="${column.key}" style="cursor: pointer;">${column.label}${sortIndicator}</th>`;
    });
    headerHtml += '</tr>';
    
    // Step 4: Set the inner HTML of the table header to our newly created string.
    tableHead.innerHTML = headerHtml;
    // --- End of the main new logic block ---


    if (data.results && data.results.length > 0) {
        summaryElement.textContent = `Found ${data.total_results.toLocaleString()} matching tiles.`;

        // The rest of the function for creating the table body and pagination remains the same...
        data.results.forEach(tile => {
            const row = document.createElement('tr');
            row.dataset.tileData = JSON.stringify(tile);
            
            let rowHtml = `<td><img src="/images/${tile.source_file_id}/${tile.webp_filename}" class="results-thumbnail" loading="lazy"></td>`;

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

        const totalPages = Math.ceil(data.total_results / data.limit);
        document.getElementById('page-info').textContent = `Page ${data.page} of ${totalPages}`;
        document.getElementById('prev-button').disabled = data.page <= 1;
        document.getElementById('next-button').disabled = data.page >= totalPages;
    } else {
        summaryElement.textContent = 'Found 0 matching tiles.';
        const columnCount = document.querySelectorAll('.column-toggle:checked').length + 1;
        tableBody.innerHTML = `<tr><td colspan="${columnCount}">No results found.</td></tr>`;
        document.getElementById('page-info').textContent = 'Page 1 of 1';
    }
}
