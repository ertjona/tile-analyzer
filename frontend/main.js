// frontend/main.js

// --- State Management ---
let currentPage = 1;
let currentRequestState = {
    filters: [],
    sort: [{ key: "id", order: "asc" }],
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
	{ key: 'avg_saturation', label: 'Saturation' },
    { key: 'laplacian', label: 'Laplacian' },
    { key: 'avg_brightness', label: 'Avg Brightness' },
    { key: 'edge_density', label: 'Edge Density' }
];

// --- Main Setup ---
window.onload = function() {
    setupEventListeners();
    populateDisplayOptions();
    addFilterRow();
    fetchAndDisplayTiles();
};

function setupEventListeners() {
    document.getElementById('filter-form').addEventListener('submit', handleFilterSubmit);
    document.getElementById('add-filter-btn').addEventListener('click', addFilterRow);
    document.getElementById('prev-button').addEventListener('click', handlePrevClick);
    document.getElementById('next-button').addEventListener('click', handleNextClick);
    document.getElementById('results-body').addEventListener('click', handleRowClick);

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
}

// --- All Helper Functions ---

function populateDisplayOptions() {
    const defaultVisible = ['json_filename', 'webp_filename', 'edge_density', 'avg_brightness'];
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
    newFilterRow.className = 'filter-row';
    newFilterRow.innerHTML = `
        <label>Filter by:</label>
        <select class="filter-key">
            <option value="edge_density">Edge Density</option>
            <option value="entropy">Entropy</option>
            <option value="laplacian">Laplacian</option>
            <option value="avg_brightness">Avg. Brightness</option>
			<option value="avg_saturation">Avg. Saturation</option>
        </select>
        <select class="filter-op">
            <option value=">=">&ge;</option>
            <option value="<=">&le;</option>
            <option value="==">==</option>
            <option value=">">&gt;</option>
            <option value="<">&lt;</option>
            <option value="!=">!=</option>
        </select>
        <input type="number" class="filter-value" step="any" placeholder="Enter value">
        <button type="button" class="remove-filter-btn" style="margin-left: 10px;">&times;</button>
    `;
    container.appendChild(newFilterRow);
}

function handleFilterSubmit(event) {
    event.preventDefault(); 
    currentPage = 1; 

    const filters = [];
    document.querySelectorAll('.filter-row').forEach(row => {
        const key = row.querySelector('.filter-key').value;
        const op = row.querySelector('.filter-op').value;
        const value = row.querySelector('.filter-value').value;
        if (value !== '') {
            filters.push({ key, op, value: parseFloat(value) });
        }
    });
    
    const sortKey = document.getElementById('sort-key').value;
    const sortOrder = document.getElementById('sort-order').value;

    currentRequestState = {
        filters: filters,
        sort: [{ key: sortKey, order: sortOrder }],
        page: currentPage,
        limit: 100
    };
    
    fetchAndDisplayTiles();
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
    tableBody.innerHTML = '';

    const visibleColumns = Array.from(document.querySelectorAll('.column-toggle:checked')).map(cb => cb.value);

    tableHead.innerHTML = `<tr><th>Thumbnail</th>${visibleColumns.map(key => `<th>${ALL_COLUMNS.find(c => c.key === key).label}</th>`).join('')}</tr>`;

    if (data.results && data.results.length > 0) {
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
        const columnCount = document.querySelectorAll('.column-toggle:checked').length + 1;
        tableBody.innerHTML = `<tr><td colspan="${columnCount}">No results found.</td></tr>`;
        document.getElementById('page-info').textContent = 'Page 1 of 1';
    }
}
