// frontend/dashboard.js
window.onload = function() {
    fetchSummary();
    fetchDistributionStats('edge_density');
	fetchDistributionStats('entropy');
	fetchDistributionStats('laplacian');
};

async function fetchSummary() {
    const content = document.getElementById('summary-content');
    try {
        const response = await fetch('/api/stats/summary');
        const data = await response.json();
        content.innerHTML = `
            <strong>Total JSON Files Ingested:</strong> ${data.total_source_files.toLocaleString()}<br>
            <strong>Total Image Tiles in Database:</strong> ${data.total_image_tiles.toLocaleString()}
        `;
    } catch (error) {
        content.textContent = 'Failed to load summary stats.';
        console.error('Error fetching summary:', error);
    }
}

// frontend/dashboard.js

async function fetchDistributionStats(columnName) {
    const content = document.getElementById(`${columnName}-content`);
    try {
        const response = await fetch(`/api/stats/distribution/${columnName}`);
        const data = await response.json();

        // --- NEW: Handle the case where there is no data ---
        if (data.count === 0) {
            content.textContent = 'No data available for this metric.';
            return; // Exit the function early
        }

        // This part will now only run if data exists
        let statsHtml = `Count       : ${data.count.toLocaleString()}\n`;
        statsHtml +=    `Mean        : ${data.mean.toFixed(6)}\n`;
        statsHtml +=    `Std. Dev.   : ${data.std_dev.toFixed(6)}\n\n`;
        statsHtml +=    `Min         : ${data.min.toFixed(6)}\n`;
        statsHtml +=    `25th Pctl.  : ${data.percentile_25.toFixed(6)}\n`;
        statsHtml +=    `Median      : ${data.median_50.toFixed(6)}\n`;
        statsHtml +=    `75th Pctl.  : ${data.percentile_75.toFixed(6)}\n`;
        statsHtml +=    `Max         : ${data.max.toFixed(6)}`;
        
        content.textContent = statsHtml;
    } catch (error) {
        content.textContent = `Failed to load stats for ${columnName}.`;
        console.error(`Error fetching stats for ${columnName}:`, error);
    }
}