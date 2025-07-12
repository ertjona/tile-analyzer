// frontend/heatmap.js

window.onload = function() {
    // --- Initial Setup ---
    fetchSourceFiles();
    setupEventListeners();
    addRuleBlock(); // Add the first rule by default
    fetchAndPopulateRulesDropdown(); // NEW: Fetch saved rules on page load
};

function setupEventListeners() {
    document.getElementById('generate-btn').addEventListener('click', generateHeatmap);
    document.getElementById('add-rule-btn').addEventListener('click', addRuleBlock);

    // NEW: Event listener for 'Download Current Heatmap' button
    document.getElementById('download-btn').addEventListener('click', downloadCurrentHeatmap); // NEW LINE

    // NEW: Event listener for 'Generate All Heatmaps' button
    document.getElementById('generate-all-btn').addEventListener('click', generateAllHeatmaps); // NEW LINE

	// NEW: Event listeners for Save/Load/Delete Rules
    document.getElementById('save-rules-btn').addEventListener('click', saveCurrentRules); // NEW
    document.getElementById('load-rules-btn').addEventListener('click', loadSelectedRule); // NEW
    document.getElementById('delete-rule-btn').addEventListener('click', deleteSelectedRule); // NEW


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

// ... (rest of your existing code) ...

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

function addRuleBlock() {
    const container = document.getElementById('rule-builder-container');
    const ruleBlock = document.createElement('div');
    ruleBlock.className = 'rule-block';

    // No longer using ruleId as it's not needed by the backend
    ruleBlock.innerHTML = `
        <div class="rule-header">
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

            // Only add condition if value is not empty, otherwise it's an incomplete rule
            if (value !== '') {
                conditions.push({ key, op, value: parseFloat(value) });
            }
        });

        // Only add rule if it has at least one valid condition
        if (conditions.length > 0) {
            const rule = {
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


// --- NEW FUNCTION: Populate Rule Builder UI ---
function populateRuleBuilderUI(rulesConfig) {
    const container = document.getElementById('rule-builder-container');
    container.innerHTML = ''; // Clear existing rule blocks

    rulesConfig.rules.forEach(rule => {
        const ruleBlock = document.createElement('div');
        ruleBlock.className = 'rule-block';
        ruleBlock.innerHTML = `
            <div class="rule-header">
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
    // Ensure at least one rule block is present if the loaded config had none
    if (rulesConfig.rules.length === 0) {
        addRuleBlock();
    }
}


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
        
        // NEW: Calculate effective TILE_SIZE based on grid dimensions
        let effectiveTileSize = DEFAULT_TILE_SIZE;
        if (data.grid_width > 0 && data.grid_height > 0) {
            const minGridDim = Math.min(data.grid_width, data.grid_height);
            // If current dimensions with DEFAULT_TILE_SIZE are too small, scale up
            if (minGridDim * DEFAULT_TILE_SIZE < MIN_HEATMAP_DIMENSION) {
                effectiveTileSize = Math.max(DEFAULT_TILE_SIZE, Math.floor(MIN_HEATMAP_DIMENSION / minGridDim));
            }
        }

        // --- MODIFIED LINE BELOW: Pass effectiveTileSize to renderHeatmap ---
        renderHeatmap(data.heatmap_data, data.grid_width, data.grid_height, data.rules_config, data.rule_match_counts, effectiveTileSize); // MODIFIED: Added effectiveTileSize

    } catch (error) {
        console.error('Error generating heatmap:', error);
        alert('Failed to generate heatmap. Check console for details.');
    } finally {
        document.getElementById('loading-message').style.display = 'none';
    }
}

// frontend/heatmap.js

// ... (existing code, including downloadCurrentHeatmap function) ...

// --- renderHeatmap function (MODIFIED TO USE DYNAMIC TILE_SIZE) ---
function renderHeatmap(heatmap_data, grid_width, grid_height, rules_config, rule_match_counts, effectiveTileSize = DEFAULT_TILE_SIZE) { // MODIFIED: Added effectiveTileSize with default
    const canvas = document.getElementById('heatmap-canvas');
    const ctx = canvas.getContext('2d');
    const downloadBtn = document.getElementById('download-btn');

    // Use the passed effectiveTileSize
    const currentTileSize = effectiveTileSize; // NEW: Use the dynamic size

    if (grid_width === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height); // Clear canvas if no data
        document.getElementById('legend-content').innerHTML = ''; // Clear the HTML legend
        document.getElementById('stats-list').innerHTML = ''; // Clear stats list
        downloadBtn.disabled = true;
        return;
    }

    // Calculate heatmap dimensions using currentTileSize
    const heatmapCanvasWidth = grid_width * currentTileSize; // MODIFIED
    const heatmapCanvasHeight = grid_height * currentTileSize; // MODIFIED

    // Determine legend dimensions (based on heatmapCanvasWidth)
    const numLegendItems = rules_config.rules.length + 1; // +1 for default color
    let legendCanvasHeight = 0;
    let legendMaxItemWidth = 0;

    ctx.font = LEGEND_FONT;
    const legendTexts = [
        `Default (No Rule Matched)`,
        ...rules_config.rules.map(rule => formatRuleConditions(rule.rule_group))
    ];
    
    legendTexts.forEach(text => {
        const textWidth = ctx.measureText(text).width;
        const currentItemWidth = LEGEND_COLOR_BOX_SIZE + LEGEND_TEXT_MARGIN + textWidth;
        if (currentItemWidth > legendMaxItemWidth) {
            legendMaxItemWidth = currentItemWidth;
        }
    });

    let numLegendColumns = Math.floor(heatmapCanvasWidth / (legendMaxItemWidth + LEGEND_ITEM_PADDING_LEFT * 2));
    if (numLegendColumns === 0) numLegendColumns = 1; // At least one column
    
    const numLegendRows = Math.ceil(numLegendItems / numLegendColumns);
    legendCanvasHeight = (numLegendRows * LEGEND_ITEM_HEIGHT) + LEGEND_PADDING_TOP;

    // Set final canvas dimensions
    canvas.width = heatmapCanvasWidth;
    canvas.height = heatmapCanvasHeight + legendCanvasHeight;

    // --- Draw the Heatmap ---
    for (let row = 0; row < grid_height; row++) {
        for (let col = 0; col < grid_width; col++) {
            const index = row * grid_width + col;
            ctx.fillStyle = heatmap_data[index];
            ctx.fillRect(col * currentTileSize, row * currentTileSize, currentTileSize, currentTileSize); // MODIFIED
        }
    }

    // --- Draw the Legend on Canvas ---
    ctx.fillStyle = '#FFFFFF'; // White background for the legend area
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
        ctx.fillText(formatRuleConditions(rule.rule_group), currentX + LEGEND_COLOR_BOX_SIZE + LEGEND_TEXT_MARGIN, currentY);
        itemCounter++;
    });

    // Optionally, clear the HTML-based legend now that it's on canvas
    document.getElementById('legend-content').innerHTML = '';

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
            listItem.innerHTML = `
                <strong>${formatRuleConditions(rule.rule_group)}:</strong> <span>${ruleCount} tiles</span> (<span>${rulePercentage.toFixed(2)}%</span>)
            `;
            statsList.appendChild(listItem);
        });
    }

    downloadBtn.disabled = false; // Enable download button after successful render
}

// ... (rest of heatmap.js including formatRuleConditions helper) ...

// --- formatRuleConditions helper function ---
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
        return `${displayKey} ${cond.op} ${cond.value.toFixed(6)}`;
    });
    
    const logicalOpDisplay = ruleGroup.logical_op.toUpperCase() === 'AND' ? 'AND' : 'OR';
    if (conditions.length > 1) {
        return `(${conditions.join(` ${logicalOpDisplay} `)})`;
    }
    return conditions.join('');
}

// frontend/heatmap.js

// ... (existing code including renderHeatmap and formatRuleConditions) ...

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
                
                // --- MODIFIED LINE BELOW: Pass effectiveTileSize to renderHeatmap ---
                renderHeatmap(data.heatmap_data, data.grid_width, data.grid_height, data.rules_config, data.rule_match_counts, effectiveTileSize); // MODIFIED: Added effectiveTileSize
				
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

// ... (existing code including generateAllHeatmaps function) ...

// --- NEW FUNCTION: Download Current Heatmap ---
function downloadCurrentHeatmap(filenameToUse) { // MODIFIED: Accepts filename as argument
    const canvas = document.getElementById('heatmap-canvas');
    // const selectedFilename = document.getElementById('filename-select').value; // REMOVE OR COMMENT OUT THIS LINE
    const selectedFilename = filenameToUse; // MODIFIED: Use the passed argument
	
    if (!selectedFilename || canvas.width === 0 || canvas.height === 0) {
        alert('No heatmap to download. Please generate one first.');
        return;
    }

    // Get image data as a PNG Data URL
    const imageDataURL = canvas.toDataURL('image/png');

    // Create a temporary link element
    const downloadLink = document.createElement('a');
    downloadLink.href = imageDataURL;

    // Construct filename: remove .json, add _heatmap.png
    const baseFilename = selectedFilename.replace(/\.json$/i, '');
    downloadLink.download = `${baseFilename}_heatmap.png`;

    // Programmatically click the link to trigger download
    document.body.appendChild(downloadLink); // Append to body is good practice for programmatic clicks
    downloadLink.click();
    document.body.removeChild(downloadLink); // Clean up
}


// ... (rest of heatmap.js including renderHeatmap) ...