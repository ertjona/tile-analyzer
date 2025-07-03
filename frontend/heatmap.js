// frontend/heatmap.js

window.onload = function() {
    // This object will store the rules we load from the config file.
    let rulesConfig = null;

    // --- Helper function to fetch the rules configuration ---
    async function loadRulesConfig() {
        try {
            const response = await fetch('/config/heatmap_rules.json');
            if (!response.ok) throw new Error('Failed to load rules configuration.');
            rulesConfig = await response.json();
            console.log("Successfully loaded heatmap rules:", rulesConfig);
        } catch (error) {
            console.error(error);
            alert('Error: Could not load heatmap_rules.json from the /config folder.');
        }
    }

    // --- Helper function to fetch the list of JSON filenames ---
    async function fetchSourceFiles() {
        try {
            const response = await fetch('/api/source_files');
            if (!response.ok) throw new Error('Failed to fetch source files.');
            const filenames = await response.json();
            
            const selectElement = document.getElementById('filename-select');
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

    // --- Main function to generate the heatmap ---
    async function generateHeatmap() {
        if (!rulesConfig) {
            alert('Rules configuration is not loaded.');
            return;
        }

        const selectedFilename = document.getElementById('filename-select').value;
        if (!selectedFilename) {
            alert('Please select a source file.');
            return;
        }

        const canvas = document.getElementById('heatmap-canvas');
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height); // Clear previous drawing
        document.getElementById('loading-message').style.display = 'block';

        const requestBody = {
            json_filename: selectedFilename,
            rules_config: rulesConfig
        };

        try {
            const response = await fetch('/api/heatmap', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) throw new Error(`HTTP Error: ${response.statusText}`);
            const data = await response.json();
            
            renderHeatmap(data);

        } catch (error) {
            console.error('Error generating heatmap:', error);
            alert('Failed to generate heatmap. Check the console for details.');
        } finally {
            document.getElementById('loading-message').style.display = 'none';
        }
    }

    // --- Function to draw the heatmap data onto the canvas ---
    function renderHeatmap(data) {
        const canvas = document.getElementById('heatmap-canvas');
        const ctx = canvas.getContext('2d');
        const tileSize = 3; // Size of each tile in pixels on the canvas

        if (data.grid_width === 0) {
            console.log("No data to render.");
            return;
        }

        // Set the canvas size based on the data
        canvas.width = data.grid_width * tileSize;
        canvas.height = data.grid_height * tileSize;

        for (let row = 0; row < data.grid_height; row++) {
            for (let col = 0; col < data.grid_width; col++) {
                const index = row * data.grid_width + col;
                const color = data.heatmap_data[index];
                
                ctx.fillStyle = color;
                ctx.fillRect(col * tileSize, row * tileSize, tileSize, tileSize);
            }
        }
    }


    // --- Initial Setup ---
    document.getElementById('generate-btn').addEventListener('click', generateHeatmap);
    loadRulesConfig();
    fetchSourceFiles();
};