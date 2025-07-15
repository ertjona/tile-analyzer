// frontend/heatmap.js

window.onload = function() {
    // --- Initial Setup ---
    fetchAndPopulateRulesDropdown(); // NEW: Fetch saved rules on page load
	fetchSourceFiles();
	setupEventListeners();
	addRuleBlock(); // Add the first rule by default
};

function setupEventListeners() {
    document.getElementById('generate-btn').addEventListener('click', generateHeatmap);
    document.getElementById('add-rule-btn').addEventListener('click', addRuleBlock);

    // NEW: Add event listener for the Tile Size dropdown
    document.getElementById('tile-size-select').addEventListener('change', (event) => {
        userSelectedTileSize = parseInt(event.target.value, 10); // Update global variable
        generateHeatmap(); // Regenerate heatmap with new size
    });
	
	// MODIFIED: Use an arrow function to ensure no arguments are passed on direct click
    document.getElementById('download-btn').addEventListener('click', () => downloadCurrentHeatmap()); // MODIFIED LINE

    // NEW: Event listener for 'Generate All Heatmaps' button
    document.getElementById('generate-all-btn').addEventListener('click', generateAllHeatmaps); // NEW LINE

	// NEW: Event listeners for Save/Load/Delete Rules
    document.getElementById('save-rules-btn').addEventListener('click', saveCurrentRules); // NEW
    document.getElementById('load-rules-btn').addEventListener('click', loadSelectedRule); // NEW
    document.getElementById('delete-rule-btn').addEventListener('click', deleteSelectedRule); // NEW
	
	// ... (existing save/load/delete rule listeners) ...

    // NEW: Add click listener to the heatmap canvas
    document.getElementById('heatmap-canvas').addEventListener('click', handleHeatmapClick); // ADD THIS LINE

    // NEW: Add click listener for the new modal close button
    document.querySelector('#heatmap-inspector-modal .close-button').onclick = () => {
        document.getElementById('heatmap-inspector-modal').style.display = "none";
    };
    window.addEventListener('click', (event) => {
        const modal = document.getElementById('heatmap-inspector-modal');
        if (event.target == modal) {
            modal.style.display = "none";
        }
    });

    // NEW: Event listener for "Define Heatmap Rules" collapsible header
    document.getElementById('define-rules-header').addEventListener('click', () => {
        toggleCollapsibleSection('define-rules-header', 'define-rules-content');
    });


    // Use event delegation to handle clicks on dynamically added buttons
    document.getElementById('rule-builder-container').addEventListener('click', function(event) {
        if (event.target.classList.contains('add-condition-btn')) {
            addConditionRow(event.target.closest('.rule-block'));
        }
        if (event.target.classList.contains('remove-condition-btn')) {
            event.target.closest('.condition-row').remove();
        }
        if (event.target.classList.contains('remove-rule-btn')) {
            event.target.closest('.rule-block').remove();
        }
    });
}

// frontend/heatmap.js

// ... (existing window.onload and setupEventListeners) ...

// --- Heatmap/Legend Drawing Constants ---
const DEFAULT_TILE_SIZE = 2; // MODIFIED: Renamed for clarity, this is the base tile size
const MIN_HEATMAP_DIMENSION = 512; // NEW: Minimum desired pixel dimension for heatmap area
const LEGEND_ITEM_HEIGHT = 25; // Height for each legend entry (color box + text)
const LEGEND_PADDING_TOP = 15; // Padding between heatmap and legend
const LEGEND_ITEM_PADDING_LEFT = 10; // Left padding for each legend item
const LEGEND_COLOR_BOX_SIZE = 20; // Size of the color swatch in the legend
const LEGEND_TEXT_MARGIN = 8; // Space between color box and text in legend
const LEGEND_FONT = '12px Arial'; // Font for legend text
const MAX_LEGEND_WIDTH = 300; // Max width for a legend column, for multi-column layout (can adjust)

// frontend/heatmap.js

// ... (existing constants like DEFAULT_TILE_SIZE, MIN_HEATMAP_DIMENSION, etc.) ...

// NEW: Global variable to store user's selected tile size
let userSelectedTileSize = DEFAULT_TILE_SIZE; // Initialize with the default from your options

// ... (rest of your global variables, e.g., lastHeatmapData, lastGridWidth) ...

async function fetchSourceFiles() {
    // ... (This function is the same as before)
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

// frontend/heatmap.js

// ... (previous code) ...

function addRuleBlock() {
    const container = document.getElementById('rule-builder-container');
    const ruleBlock = document.createElement('div');
    ruleBlock.className = 'rule-block';

    ruleBlock.innerHTML = `
        <div class="rule-header">
            <label>Name:</label>
            <input type="text" class="rule-name" placeholder="Optional Rule Name" style="flex-grow: 1; margin-right: 10px;">
            <label>Color:</label>
            <input type="color" class="rule-color" value="#FFFF00">
            <label>Logic:</label>
            <select class="rule-logical-op">
                <option value="AND">All conditions must match (AND)</option>
                <option value="OR">Any condition can match (OR)</option>
            </select>
            <button type="button" class="remove-rule-btn" style="margin-left: auto;">Remove Rule</button>
        </div>
        <div class="conditions-container">
        </div>
        <button type="button" class="add-condition-btn">+ Add Condition</button>
    `;
    container.appendChild(ruleBlock);
    // Add the first condition row to the new rule block automatically
    addConditionRow(ruleBlock);
}

// ... (rest of the file) ...

function addConditionRow(ruleBlock) {
    const container = ruleBlock.querySelector('.conditions-container');
    const conditionRow = document.createElement('div');
    conditionRow.className = 'condition-row';
    conditionRow.innerHTML = `
        <select class="condition-key">
            <option value="edge_density">Edge Density</option>
            <option value="foreground_ratio">Foreground Ratio</option>
			<option value="max_subject_area">Max Subject Area</option>
            <option value="laplacian">Laplacian</option>
            <option value="avg_brightness">Avg. Brightness</option>
            <option value="size">Size</option>
            <option value="entropy">Entropy</option> <option value="avg_saturation">Avg. Saturation</option> </select>
        <select class="condition-op">
            <option value=">=">&ge;</option>
            <option value="<=">&le;</option>
            <option value="==">==</option>
            <option value=">">&gt;</option>
            <option value="<">&lt;</option>
            <option value="!=">!=</option>
        </select>
        <input type="number" class="condition-value" step="any" placeholder="Enter value">
        <button type="button" class="remove-condition-btn">&times;</button>
    `;
    container.appendChild(conditionRow);
}

// frontend/heatmap.js

// ... (previous code) ...

// --- NEW FUNCTION: Helper to get current rules from UI ---
function getCurrentRulesConfigFromUI() {
    const rulesConfig = {
        default_color: "#CCCCCC", // You might want to make this configurable too later
        rules: []
    };

    document.querySelectorAll('.rule-block').forEach(ruleBlock => {
        const conditions = [];
        ruleBlock.querySelectorAll('.condition-row').forEach(condRow => {
            const key = condRow.querySelector('.condition-key').value;
            const op = condRow.querySelector('.condition-op').value;
            const value = condRow.querySelector('.condition-value').value;

            if (value !== '') {
                conditions.push({ key, op, value: parseFloat(value) });
            }
        });

        if (conditions.length > 0) {
            // NEW: Get the rule name from the input field
            const ruleNameInput = ruleBlock.querySelector('.rule-name');
            const ruleName = ruleNameInput ? ruleNameInput.value.trim() : ''; // Get value, trim, default to empty string

            const rule = {
                name: ruleName || undefined, // Include name, set to undefined if empty to avoid sending empty string
                color: ruleBlock.querySelector('.rule-color').value,
                rule_group: {
                    logical_op: ruleBlock.querySelector('.rule-logical-op').value,
                    conditions: conditions
                }
            };
            rulesConfig.rules.push(rule);
        }
    });
    return rulesConfig;
}

// ... (rest of the file) ...

// --- NEW FUNCTION: Save Current Rules ---
async function saveCurrentRules() {
    const ruleNameInput = document.getElementById('rule-name-input');
    const ruleName = ruleNameInput.value.trim();

    if (!ruleName) {
        alert('Please enter a name for your rule set.');
        return;
    }

    const rulesConfig = getCurrentRulesConfigFromUI();

    if (rulesConfig.rules.length === 0) {
        alert('Please define at least one valid rule with a condition before saving.');
        return;
    }

    try {
        const response = await fetch('/api/heatmap/rules/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rule_name: ruleName, rules_config: rulesConfig })
        });

        // --- MODIFIED ERROR HANDLING BELOW ---
        if (response.ok) {
            const result = await response.json();
            alert(result.message);
            ruleNameInput.value = ''; // Clear input
            fetchAndPopulateRulesDropdown(); // Refresh dropdown
        } else {
            // Attempt to parse JSON error message from the backend
            let errorDetail = 'Unknown error';
            try {
                const errorData = await response.json();
                if (errorData && errorData.detail) {
                    errorDetail = errorData.detail;
                } else {
                    // Fallback if backend JSON is not as expected
                    errorDetail = `Server responded with status ${response.status}`;
                }
            } catch (jsonError) {
                // If response is not JSON (e.g., plain text error, HTML error page)
                const textError = await response.text(); // Try to get as plain text
                errorDetail = `Server responded with status ${response.status}. Response: ${textError.substring(0, 100)}...`;
                console.error("Failed to parse error response as JSON:", jsonError, "Raw response:", textError);
            }
            alert(`Error saving rules: ${errorDetail}`);
        }
        // --- END MODIFIED ERROR HANDLING ---

    } catch (error) {
        // This catch block handles network errors or other issues before response is received
        console.error("Network or unexpected error saving rules:", error);
        alert('Failed to save rule set due to a network or unexpected error. Check browser console for details.');
    }
}


// --- NEW FUNCTION: Fetch and Populate Rules Dropdown ---
async function fetchAndPopulateRulesDropdown() {
    const selectElement = document.getElementById('load-rule-select');
    // Clear existing options, keeping the default one
    selectElement.innerHTML = '<option value="">-- Select a saved rule set --</option>';

    try {
        const response = await fetch('/api/heatmap/rules/list');
        if (!response.ok) throw new Error('Failed to fetch saved rule list.');
        const ruleNames = await response.json();

        ruleNames.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            selectElement.appendChild(option);
        });
    } catch (error) {
        console.error("Error fetching saved rules:", error);
        // Optionally, display an error message in the dropdown or elsewhere
    }
}

// --- NEW FUNCTION: Load Selected Rule ---
async function loadSelectedRule() {
    const selectElement = document.getElementById('load-rule-select');
    const ruleName = selectElement.value;

    if (!ruleName) {
        alert('Please select a rule set to load.');
        return;
    }

    try {
        const response = await fetch(`/api/heatmap/rules/load/${ruleName}`);
        if (!response.ok) throw new Error('Failed to load selected rule set.');
        const rulesConfig = await response.json();
        
        populateRuleBuilderUI(rulesConfig); // NEW: Function to populate UI
        alert(`Rule set '${ruleName}' loaded successfully.`);
    } catch (error) {
        console.error("Error loading rule set:", error);
        alert('Failed to load rule set. Check console for details.');
    }
}

// --- NEW FUNCTION: Delete Selected Rule ---
async function deleteSelectedRule() {
    const selectElement = document.getElementById('load-rule-select');
    const ruleName = selectElement.value;

    if (!ruleName) {
        alert('Please select a rule set to delete.');
        return;
    }

    if (!confirm(`Are you sure you want to delete the rule set '${ruleName}'? This action cannot be undone.`)) {
        return; // User cancelled
    }

    try {
        const response = await fetch(`/api/heatmap/rules/delete/${ruleName}`, {
            method: 'DELETE'
        });

        const result = await response.json();
        if (response.ok) {
            alert(result.message);
            fetchAndPopulateRulesDropdown(); // Refresh dropdown
        } else {
            alert(`Error deleting rules: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error("Error deleting rules:", error);
        alert('Failed to delete rule set. Check console for details.');
    }
}


// frontend/heatmap.js

// ... (previous code) ...

// --- NEW FUNCTION: Populate Rule Builder UI ---
function populateRuleBuilderUI(rulesConfig) {
    const container = document.getElementById('rule-builder-container');
    container.innerHTML = ''; // Clear existing rule blocks

    rulesConfig.rules.forEach(rule => {
        const ruleBlock = document.createElement('div');
        ruleBlock.className = 'rule-block';
        ruleBlock.innerHTML = `
            <div class="rule-header">
                <label>Name:</label>
                <input type="text" class="rule-name" placeholder="Optional Rule Name" style="flex-grow: 1; margin-right: 10px;" value="${rule.name || ''}">
                <label>Color:</label>
                <input type="color" class="rule-color" value="${rule.color}">
                <label>Logic:</label>
                <select class="rule-logical-op">
                    <option value="AND" ${rule.rule_group.logical_op === 'AND' ? 'selected' : ''}>All conditions must match (AND)</option>
                    <option value="OR" ${rule.rule_group.logical_op === 'OR' ? 'selected' : ''}>Any condition can match (OR)</option>
                </select>
                <button type="button" class="remove-rule-btn" style="margin-left: auto;">Remove Rule</button>
            </div>
            <div class="conditions-container">
            </div>
            <button type="button" class="add-condition-btn">+ Add Condition</button>
        `;
        container.appendChild(ruleBlock);

        const conditionsContainer = ruleBlock.querySelector('.conditions-container');
        rule.rule_group.conditions.forEach(condition => {
            const conditionRow = document.createElement('div');
            conditionRow.className = 'condition-row';
            conditionRow.innerHTML = `
                <select class="condition-key">
                    <option value="edge_density" ${condition.key === 'edge_density' ? 'selected' : ''}>Edge Density</option>
                    <option value="foreground_ratio" ${condition.key === 'foreground_ratio' ? 'selected' : ''}>Foreground Ratio</option>
                    <option value="max_subject_area" ${condition.key === 'max_subject_area' ? 'selected' : ''}>Max Subject Area</option>
                    <option value="laplacian" ${condition.key === 'laplacian' ? 'selected' : ''}>Laplacian</option>
                    <option value="avg_brightness" ${condition.key === 'avg_brightness' ? 'selected' : ''}>Avg. Brightness</option>
                    <option value="size" ${condition.key === 'size' ? 'selected' : ''}>Size</option>
                    <option value="entropy" ${condition.key === 'entropy' ? 'selected' : ''}>Entropy</option>
                    <option value="avg_saturation" ${condition.key === 'avg_saturation' ? 'selected' : ''}>Avg. Saturation</option>
                </select>
                <select class="condition-op">
                    <option value=">=" ${condition.op === '>=' ? 'selected' : ''}>&ge;</option>
                    <option value="<=" ${condition.op === '<=' ? 'selected' : ''}>&le;</option>
                    <option value="==" ${condition.op === '==' ? 'selected' : ''}>==</option>
                    <option value=">" ${condition.op === '>' ? 'selected' : ''}>&gt;</option>
                    <option value="<" ${condition.op === '<' ? 'selected' : ''}>&lt;</option>
                    <option value="!=" ${condition.op === '!=' ? 'selected' : ''}>!=</option>
                </select>
                <input type="number" class="condition-value" step="any" placeholder="Enter value" value="${condition.value}">
                <button type="button" class="remove-condition-btn">&times;</button>
            `;
            conditionsContainer.appendChild(conditionRow);
        });
    });
    if (rulesConfig.rules.length === 0) {
        addRuleBlock();
    }
}

// ... (rest of the file) ...

// --- Main function to generate the heatmap ---
async function generateHeatmap() {
    const selectedFilename = document.getElementById('filename-select').value;
    if (!selectedFilename) {
        alert('Please select a source file.');
        return;
    }

    // --- REPLACED: Use helper function to get rules from UI ---
    const rulesConfig = getCurrentRulesConfigFromUI();

    if (rulesConfig.rules.length === 0) {
        alert('Please define at least one valid rule with a condition.');
        return;
    }

    const canvas = document.getElementById('heatmap-canvas');
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
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

        lastSelectedFilename = selectedFilename;
        // Pass the userSelectedTileSize directly
        renderHeatmap(data.heatmap_data, data.grid_width, data.grid_height, data.rules_config, data.rule_match_counts, userSelectedTileSize);

    } catch (error) {
        console.error('Error generating heatmap:', error);
        alert('Failed to generate heatmap. Check console for details.');
    } finally {
        document.getElementById('loading-message').style.display = 'none';
    }
}

// NEW: Store the last generated heatmap's data and dimensions for click handling
let lastHeatmapData = null; // To store the heatmap_data array (colors)
let lastGridWidth = 0;
let lastGridHeight = 0;
let lastRulesConfig = null; // Store rules config for displaying details if needed
let lastSelectedFilename = ''; // Store the filename that generated the current heatmap
let currentEffectiveTileSize = DEFAULT_TILE_SIZE; // Store the effective tile size

// MODIFIED: renderHeatmap now uses the passed effectiveTileSize (which is userSelectedTileSize)
function renderHeatmap(heatmap_data, grid_width, grid_height, rules_config, rule_match_counts, effectiveTileSize = DEFAULT_TILE_SIZE) {
    const canvas = document.getElementById('heatmap-canvas');
    const ctx = canvas.getContext('2d');
    const downloadBtn = document.getElementById('download-btn');

    // MODIFIED: Use the passed effectiveTileSize directly.
    // The global currentEffectiveTileSize will be set here, for click handling.
    currentEffectiveTileSize = effectiveTileSize; // Update the global variable
    const currentTileSize = effectiveTileSize; // Use this for drawing

    if (grid_width === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height); // Clear canvas if no data
        document.getElementById('legend-content').innerHTML = ''; // Clear the HTML legend
        document.getElementById('stats-list').innerHTML = ''; // Clear stats list
        downloadBtn.disabled = true;
        return;
    }

    const heatmapCanvasWidth = grid_width * currentTileSize;
    const heatmapCanvasHeight = grid_height * currentTileSize;

    const numLegendItems = rules_config.rules.length + 1; // +1 for default color
    let legendCanvasHeight = 0;
    let legendMaxItemWidth = 0;
	
	// Store data for click handling BEFORE clearing canvas
    lastHeatmapData = heatmap_data;
    lastGridWidth = grid_width;
    lastGridHeight = grid_height;
    lastRulesConfig = rules_config;
	// lastSelectedFilename = selectedFilename; // This line is not needed here if it's stored globally in generateHeatmap
    currentEffectiveTileSize = effectiveTileSize; // Store this

    ctx.font = LEGEND_FONT;

    // MODIFIED: Prepare legend texts using rule names or formatted conditions
    const legendTexts = [
        `Default (No Rule Matched)`,
        ...rules_config.rules.map(rule => rule.name && rule.name.trim() !== '' ? rule.name.trim() : formatRuleConditions(rule.rule_group))
    ];
    
    legendTexts.forEach(text => {
        const textWidth = ctx.measureText(text).width;
        const currentItemWidth = LEGEND_COLOR_BOX_SIZE + LEGEND_TEXT_MARGIN + textWidth;
        if (currentItemWidth > legendMaxItemWidth) {
            legendMaxItemWidth = currentItemWidth;
        }
    });

    let numLegendColumns = Math.floor(heatmapCanvasWidth / (legendMaxItemWidth + LEGEND_ITEM_PADDING_LEFT * 2));
    if (numLegendColumns === 0) numLegendColumns = 1;
    
    const numLegendRows = Math.ceil(numLegendItems / numLegendColumns);
    legendCanvasHeight = (numLegendRows * LEGEND_ITEM_HEIGHT) + LEGEND_PADDING_TOP;

    canvas.width = heatmapCanvasWidth;
    canvas.height = heatmapCanvasHeight + legendCanvasHeight;

    // --- Draw the Heatmap ---
    for (let row = 0; row < grid_height; row++) {
        for (let col = 0; col < grid_width; col++) {
            const index = row * grid_width + col;
            ctx.fillStyle = heatmap_data[index];
            ctx.fillRect(col * currentTileSize, row * currentTileSize, currentTileSize, currentTileSize);
        }
    }

    // --- Draw the Legend on Canvas ---
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, heatmapCanvasHeight, canvas.width, legendCanvasHeight); 

    ctx.font = LEGEND_FONT;
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#000000';

    let currentX = LEGEND_ITEM_PADDING_LEFT;
    let currentY = heatmapCanvasHeight + LEGEND_PADDING_TOP + (LEGEND_ITEM_HEIGHT / 2);

    // Draw default color item
    ctx.fillStyle = rules_config.default_color;
    ctx.fillRect(currentX, currentY - (LEGEND_COLOR_BOX_SIZE / 2), LEGEND_COLOR_BOX_SIZE, LEGEND_COLOR_BOX_SIZE);
    ctx.fillStyle = '#000000';
    ctx.fillText(`Default (No Rule Matched)`, currentX + LEGEND_COLOR_BOX_SIZE + LEGEND_TEXT_MARGIN, currentY);

    let itemCounter = 1;

    // Draw rule items
    rules_config.rules.forEach(rule => {
        if (itemCounter % numLegendColumns === 0) {
            currentX = LEGEND_ITEM_PADDING_LEFT;
            currentY += LEGEND_ITEM_HEIGHT;
        } else {
            currentX += legendMaxItemWidth + LEGEND_ITEM_PADDING_LEFT * 2;
        }

        ctx.fillStyle = rule.color;
        ctx.fillRect(currentX, currentY - (LEGEND_COLOR_BOX_SIZE / 2), LEGEND_COLOR_BOX_SIZE, LEGEND_COLOR_BOX_SIZE);
        ctx.fillStyle = '#000000';
        // MODIFIED: Use rule.name if available, otherwise fallback to formatted conditions
        const legendItemText = rule.name && rule.name.trim() !== '' ? rule.name.trim() : formatRuleConditions(rule.rule_group);
        ctx.fillText(legendItemText, currentX + LEGEND_COLOR_BOX_SIZE + LEGEND_TEXT_MARGIN, currentY);
        itemCounter++;
    });

    //document.getElementById('legend-content').innerHTML = ''; // Clear the old HTML legend section

    // --- Display Rule Match Statistics ---
    const statsList = document.getElementById('stats-list');
    statsList.innerHTML = ''; // Clear previous statistics

    let totalMatchedTiles = 0;
    for (const key in rule_match_counts) {
        totalMatchedTiles += rule_match_counts[key];
    }

    if (totalMatchedTiles === 0 && rules_config.rules.length > 0) {
        const listItem = document.createElement('li');
        listItem.innerHTML = `<strong>No tiles matched any rules or were processed successfully.</strong>`;
        statsList.appendChild(listItem);
    } else if (totalMatchedTiles === 0) {
        const listItem = document.createElement('li');
        listItem.innerHTML = `<strong>No tiles found for this JSON file.</strong>`;
        statsList.appendChild(listItem);
    } else {
        // Display stats for default (unmatched) tiles
        const defaultCount = rule_match_counts['default'] || 0;
        const defaultPercentage = (defaultCount / totalMatchedTiles) * 100;
        let listItem = document.createElement('li');
        listItem.innerHTML = `
            <strong>Default (No Rule Matched):</strong> <span>${defaultCount} tiles</span> (<span>${defaultPercentage.toFixed(2)}%</span>)
        `;
        statsList.appendChild(listItem);

        // Display stats for each defined rule
        rules_config.rules.forEach((rule, index) => {
            const ruleCount = rule_match_counts[String(index)] || 0;
            const rulePercentage = (ruleCount / totalMatchedTiles) * 100;
            listItem = document.createElement('li');
            // MODIFIED: Use rule.name if available, otherwise fallback to formatted conditions for stats
            const statsItemText = rule.name && rule.name.trim() !== '' ? rule.name.trim() : formatRuleConditions(rule.rule_group);
            listItem.innerHTML = `
                <strong>${statsItemText}:</strong> <span>${ruleCount} tiles</span> (<span>${rulePercentage.toFixed(2)}%</span>)
            `;
            statsList.appendChild(listItem);
        });
    }

    downloadBtn.disabled = false;
}

// NEW: handleHeatmapClick function
function handleHeatmapClick(event) {
    // Ensure we have data to work with
    if (!lastHeatmapData || lastGridWidth === 0 || lastGridHeight === 0) {
        console.warn("No heatmap data available to inspect.");
        return;
    }

    const canvas = document.getElementById('heatmap-canvas');
    const rect = canvas.getBoundingClientRect(); // Get canvas position relative to viewport
    const x = event.clientX - rect.left; // X position within the canvas
    const y = event.clientY - rect.top;  // Y position within the canvas

    // Calculate clicked column and row based on effective tile size
    const clickedCol = Math.floor(x / currentEffectiveTileSize);
    const clickedRow = Math.floor(y / currentEffectiveTileSize);

    // Check if the click was within the heatmap area (not the legend)
    if (clickedRow >= lastGridHeight) {
        console.log("Clicked on legend area, not a tile.");
        return; // Clicked in the legend area
    }

    // Basic boundary check
    if (clickedCol < 0 || clickedCol >= lastGridWidth || clickedRow < 0 || clickedRow >= lastGridHeight) {
        console.warn("Click outside valid heatmap tile area.");
        return;
    }

    console.log(`Clicked tile at Column: ${clickedCol}, Row: ${clickedRow}`);

    // NEW: Call the function to fetch details and display the modal
    fetchTileDetailsAndDisplayModal(lastSelectedFilename, clickedCol, clickedRow); // ADD/UNCOMMENT THIS LINE
}

// frontend/heatmap.js

// ... (previous code, ensure you have global variables like lastSelectedFilename, etc.) ...

// NEW: Function to fetch tile details and display in modal
async function fetchTileDetailsAndDisplayModal(jsonFilename, col, row) {
    const modal = document.getElementById('heatmap-inspector-modal');
    const img = document.getElementById('heatmap-inspector-image');
    const metadata = document.getElementById('heatmap-inspector-metadata');
    
    // Clear previous content and show loading message
    img.src = ''; // Clear image
    metadata.textContent = 'Loading tile details...';
    modal.style.display = 'block'; // Show modal with loading state

    try {
        const response = await fetch(`/api/tile_details?json_filename=${jsonFilename}&col=${col}&row=${row}`);
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `Failed to fetch tile details. Status: ${response.status}`);
        }
        
        const tile = await response.json();

        // Construct image URL: /images/{source_file_id}/{webp_filename}
        // Assuming your backend serves images from /images endpoint
        img.src = `/images/${tile.source_file_id}/${tile.webp_filename}`;
        img.alt = `Tile: ${tile.webp_filename}`;

        // Populate metadata
        let detailsHtml = '';
        for (const [key, value] of Object.entries(tile)) {
            // Format numbers for display, similar to main.js inspector
            let displayValue = value;
            if (typeof value === 'number' && !['id', 'col', 'row', 'size', 'source_file_id'].includes(key)) {
                // Apply adaptive formatting as previously discussed for heatmap legend
                if (Number.isInteger(value)) {
                    displayValue = value.toString();
                } else {
                    displayValue = parseFloat(value.toFixed(6)).toString(); // Format to 6 decimal places then trim
                }
            } else if (value === null || value === undefined) {
                displayValue = 'N/A';
            }
            detailsHtml += `${key.padEnd(20)}: ${displayValue}\n`;
        }
        metadata.textContent = detailsHtml;

    } catch (error) {
        console.error('Error fetching tile details:', error);
        metadata.textContent = `Failed to load tile details: ${error.message}`;
        img.src = ''; // Clear any broken image icon
    }
}

// frontend/heatmap.js

// ... (previous code) ...

// --- NEW FUNCTION: Helper to toggle collapsible sections ---
function toggleCollapsibleSection(headerId, contentId) {
    const header = document.getElementById(headerId);
    const content = document.getElementById(contentId);
    const icon = header.querySelector('.collapsible-icon');

    if (content.classList.contains('hidden')) {
        // Show content
        content.classList.remove('hidden');
        header.classList.remove('collapsed'); // Remove collapsed state from header
        icon.innerHTML = '&#9660;'; // Down arrow
    } else {
        // Hide content
        content.classList.add('hidden');
        header.classList.add('collapsed'); // Add collapsed state to header
        icon.innerHTML = '&#9658;'; // Right arrow
    }
}

// ... (rest of your file, e.g., formatRuleConditions) ...
// --- formatRuleConditions helper function (MODIFIED for adaptive decimal places) ---
function formatRuleConditions(ruleGroup) {
    const conditions = ruleGroup.conditions.map(cond => {
        // Mapping for display names of keys
        const keyMap = {
            'edge_density': 'Edge Density',
            'foreground_ratio': 'Foreground Ratio',
            'max_subject_area': 'Max Subject Area',
            'laplacian': 'Laplacian',
            'avg_brightness': 'Avg. Brightness',
            'size': 'Size',
            'entropy': 'Entropy',
            'avg_saturation': 'Avg. Saturation'
        };
        const displayKey = keyMap[cond.key] || cond.key;
        
        let formattedValue;
        // Check if the value is a number to apply formatting
        if (typeof cond.value === 'number') {
            // If it's an integer (or very close to one), display without decimals
            if (Number.isInteger(cond.value)) {
                formattedValue = cond.value.toString();
            } else {
                // For floating-point numbers, use an adaptive approach
                // to show enough precision without excessive zeros.
                // This example uses a default of 3 decimal places,
                // but you can adjust the logic further for very small numbers.
                formattedValue = cond.value.toFixed(6); // Start with higher precision
                // Remove trailing zeros and unnecessary decimal point
                formattedValue = parseFloat(formattedValue).toString();
            }
        } else {
            formattedValue = cond.value; // Fallback for non-numeric values
        }

        return `${displayKey} ${cond.op} ${formattedValue}`;
    });
    
    const logicalOpDisplay = ruleGroup.logical_op.toUpperCase() === 'AND' ? 'AND' : 'OR';
    if (conditions.length > 1) {
        return `(${conditions.join(` ${logicalOpDisplay} `)})`;
    }
    return conditions.join('');
}

// --- NEW FUNCTION: Generate All Heatmaps ---
async function generateAllHeatmaps() {
    const generateBtn = document.getElementById('generate-btn');
    const generateAllBtn = document.getElementById('generate-all-btn');
    const filenameSelect = document.getElementById('filename-select');
    const loadingMessage = document.getElementById('loading-message');
    const originalLoadingMessage = loadingMessage.textContent;

    generateBtn.disabled = true;
    generateAllBtn.disabled = true;
    loadingMessage.style.display = 'block';

    try {
        // Fetch all source filenames
        const response = await fetch('/api/source_files');
        if (!response.ok) throw new Error('Failed to fetch source files for batch generation.');
        const allFilenames = await response.json(); //

        if (allFilenames.length === 0) {
            alert('No source files found to generate heatmaps for.');
            return;
        }

        const rulesConfig = getCurrentRulesConfigFromUI();
        if (rulesConfig.rules.length === 0) {
            alert('Please define at least one valid rule with a condition before generating all heatmaps.');
            return;
        }

        for (let i = 0; i < allFilenames.length; i++) {
            const filename = allFilenames[i];
            loadingMessage.textContent = `Generating heatmap for ${filename} (${i + 1}/${allFilenames.length})...`;
            
            // Set the dropdown to the current filename for visual feedback
            filenameSelect.value = filename;

            // Prepare the request body for generateHeatmap
            const requestBody = {
                json_filename: filename,
                rules_config: rulesConfig
            };

            try {
                const heatmapResponse = await fetch('/api/heatmap', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestBody)
                });

                if (!heatmapResponse.ok) {
                    const errorText = await heatmapResponse.text();
                    console.error(`Error generating heatmap for ${filename}: Status ${heatmapResponse.status}, Response: ${errorText}`);
                    // Optionally, alert the user about specific file failures
                    // alert(`Failed to generate heatmap for ${filename}. Check console for details.`);
                    continue; // Continue to the next file even if one fails
                }

                const data = await heatmapResponse.json();
                // NEW: Calculate effective TILE_SIZE based on grid dimensions
                let effectiveTileSize = DEFAULT_TILE_SIZE;
                if (data.grid_width > 0 && data.grid_height > 0) {
                    const minGridDim = Math.min(data.grid_width, data.grid_height);
                    if (minGridDim * DEFAULT_TILE_SIZE < MIN_HEATMAP_DIMENSION) {
                        effectiveTileSize = Math.max(DEFAULT_TILE_SIZE, Math.floor(MIN_HEATMAP_DIMENSION / minGridDim));
                    }
                }
                
                // MODIFIED: Pass userSelectedTileSize directly
                // Remove the previous effectiveTileSize calculation logic here too.
                renderHeatmap(data.heatmap_data, data.grid_width, data.grid_height, data.rules_config, data.rule_match_counts, userSelectedTileSize);
                
                // NEW: Trigger download after rendering each heatmap
                downloadCurrentHeatmap(filename); // Call the modified download function
				
                // Pause briefly to allow the user to see each heatmap (optional)
                await new Promise(resolve => setTimeout(resolve, 500)); 

            } catch (innerError) {
                console.error(`Network or unexpected error for ${filename}:`, innerError);
                // alert(`Unexpected error generating heatmap for ${filename}. Check console.`);
                continue;
            }
        }
        alert('Batch heatmap generation complete!');

    } catch (error) {
        console.error("Error during batch heatmap generation:", error);
        alert('An error occurred during batch heatmap generation. Check console for details.');
    } finally {
        generateBtn.disabled = false;
        generateAllBtn.disabled = false;
        loadingMessage.textContent = originalLoadingMessage;
        loadingMessage.style.display = 'none';
    }
}

// frontend/heatmap.js

// ... (previous code before downloadCurrentHeatmap) ...

// --- NEW FUNCTION: Download Current Heatmap (with enhanced debugging) ---
function downloadCurrentHeatmap(filenameToUse) {
    console.log("downloadCurrentHeatmap called. filenameToUse (argument):", filenameToUse, "Type:", typeof filenameToUse); // NEW LOG 1

    const canvas = document.getElementById('heatmap-canvas');
    
    const filenameSelectElement = document.getElementById('filename-select');
    // Safely get the dropdown value. If element is null, dropdownValue will be null.
    const dropdownValue = filenameSelectElement ? filenameSelectElement.value : null;
    console.log("Dropdown element found:", !!filenameSelectElement, "Dropdown value:", dropdownValue, "Type:", typeof dropdownValue); // NEW LOG 2

    // Determine the filename to use: prioritize argument, then dropdown value
    const finalFilename = filenameToUse || dropdownValue;
    console.log("Final filename resolved:", finalFilename, "Type:", typeof finalFilename); // NEW LOG 3

    // MODIFIED: Add a strict type check for finalFilename
    if (!finalFilename || typeof finalFilename !== 'string' || canvas.width === 0 || canvas.height === 0) {
        alert('No heatmap to download. Please ensure a source file is selected and a heatmap is generated.'); // More specific alert
        console.error("Download aborted. Reasons:", {
            isFinalFilenameTruthy: !!finalFilename,
            isFinalFilenameString: typeof finalFilename === 'string',
            canvasWidth: canvas.width,
            canvasHeight: canvas.height,
            resolvedFilename: finalFilename
        });
        return;
    }

    // Get image data as a PNG Data URL
    const imageDataURL = canvas.toDataURL('image/png');

    // Create a temporary link element
    const downloadLink = document.createElement('a');
    downloadLink.href = imageDataURL;

    // Construct filename: remove .json, add _heatmap.png
    const baseFilename = finalFilename.replace(/\.json$/i, ''); // THIS IS LIKELY LINE 880
    downloadLink.download = `${baseFilename}_heatmap.png`;

    // Programmatically click the link to trigger download
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
}

// ... (rest of heatmap.js) ...