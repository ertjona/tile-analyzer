// frontend/main.js

// --- State Management ---
let currentPage = 1;
let currentUrl = 'http://127.0.0.1:8000/api/tiles';

// --- Main Setup ---
window.onload = function() {
    fetchAndDisplayTiles(currentUrl);

    // --- Event Listeners ---
    document.getElementById('filter-form').addEventListener('submit', handleFilterSubmit);
    document.getElementById('prev-button').addEventListener('click', handlePrevClick);
    document.getElementById('next-button').addEventListener('click', handleNextClick);

    // --- NEW: Modal Listeners ---
    const modal = document.getElementById('inspector-modal');
    const closeBtn = document.querySelector('.close-button');
    closeBtn.onclick = () => modal.style.display = "none";
    window.onclick = (event) => {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    };
    
    // --- NEW: Event Delegation for table row clicks ---
    document.getElementById('results-body').addEventListener('click', handleRowClick);
};

// --- Helper Functions ---
function handleFilterSubmit(event) {
    event.preventDefault();
    currentPage = 1; 
    currentUrl = buildUrlWithPage();
    fetchAndDisplayTiles(currentUrl);
}

function handlePrevClick() {
    if (currentPage > 1) {
        currentPage--;
        fetchAndDisplayTiles(buildUrlWithPage());
    }
}

function handleNextClick() {
    currentPage++;
    fetchAndDisplayTiles(buildUrlWithPage());
}

function buildUrlWithPage() {
    // ... (This function remains unchanged from the previous step) ...
    const baseUrl = 'http://127.0.0.1:8000/api/tiles';
    const params = new URLSearchParams();
    const filterKey = document.getElementById('filter-key').value;
    const filterOp = document.getElementById('filter-op').value;
    const filterValue = document.getElementById('filter-value').value;
    const sortKey = document.getElementById('sort-key').value;
    const sortOrder = document.getElementById('sort-order').value;

    if (filterValue !== '') {
        params.append('filter_key', filterKey);
        params.append('filter_op', filterOp);
        params.append('filter_value', filterValue);
    }
    params.append('sort', `${sortKey}:${sortOrder}`);
    params.append('page', currentPage);

    return `${baseUrl}?${params.toString()}`;
}

function handleRowClick(event) {
    const row = event.target.closest('tr');
    if (!row || !row.dataset.tileData) return; // Exit if not a valid row click

    const tile = JSON.parse(row.dataset.tileData);
    
    // Populate the modal
    const modal = document.getElementById('inspector-modal');
    const img = document.getElementById('inspector-image');
    const metadata = document.getElementById('inspector-metadata');

    // Build the image URL to call our new backend endpoint
    img.src = `/images/${tile.source_file_id}/${tile.webp_filename}`;
    
    // Format and display all metadata
    let detailsHtml = '';
    for (const [key, value] of Object.entries(tile)) {
        detailsHtml += `${key.padEnd(20)}: ${value}\n`;
    }
    metadata.textContent = detailsHtml;

    // Show the modal
    modal.style.display = "block";
}

async function fetchAndDisplayTiles(apiUrl) {
    // ... (This function has one small change from the previous step) ...
    const tableBody = document.getElementById('results-body');
    tableBody.innerHTML = '<tr><td colspan="6">Loading...</td></tr>';
    document.getElementById('prev-button').disabled = true;
    document.getElementById('next-button').disabled = true;

    try {
        const response = await fetch(apiUrl);
        const data = await response.json();
        
        tableBody.innerHTML = ''; 

        if (data.results && data.results.length > 0) {
            data.results.forEach(tile => {
                const row = document.createElement('tr');
                // --- NEW: Store the full tile data on the row itself ---
                row.dataset.tileData = JSON.stringify(tile);
                
                row.innerHTML = `
                    <td>${tile.id}</td>
                    <td>${tile.source_file_id}</td>
                    <td>${tile.webp_filename}</td>
                    <td>${tile.status || 'N/A'}</td>
                    <td>${tile.entropy != null ? tile.entropy.toFixed(4) : 'N/A'}</td>
                    <td>${tile.edge_density != null ? tile.edge_density.toFixed(8) : 'N/A'}</td>
                `;
                tableBody.appendChild(row);
            });
            
            const totalPages = Math.ceil(data.total_results / data.limit);
            document.getElementById('page-info').textContent = `Page ${data.page} of ${totalPages}`;
            document.getElementById('prev-button').disabled = data.page <= 1;
            document.getElementById('next-button').disabled = data.page >= totalPages;
        } else {
            tableBody.innerHTML = '<tr><td colspan="6">No results found.</td></tr>';
            document.getElementById('page-info').textContent = 'Page 1 of 1';
        }

    } catch (error) {
        console.error('Error fetching data:', error);
        tableBody.innerHTML = '<tr><td colspan="6" style="color: red;">Failed to load data.</td></tr>';
    }
}