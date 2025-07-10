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
        
        renderHeatmap(data.heatmap_data, data.grid_width, data.grid_height, data.rules_config);

    } catch (error) {
        console.error('Error generating heatmap:', error);
        alert('Failed to generate heatmap. Check console for details.');
    } finally {
        document.getElementById('loading-message').style.display = 'none';
    }
}

// --- renderHeatmap function ---
function renderHeatmap(heatmap_data, grid_width, grid_height, rules_config) {
    const canvas = document.getElementById('heatmap-canvas');
    const ctx = canvas.getContext('2d');
    const tileSize = 2; // MODIFIED: Changed from 1 to 2

    if (grid_width === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height); // Clear canvas if no data
        document.getElementById('legend-content').innerHTML = ''; // Clear legend too
        return;
    }

    canvas.width = grid_width * tileSize;
    canvas.height = grid_height * tileSize;

    for (let row = 0; row < grid_height; row++) {
        for (let col = 0; col < grid_width; col++) {
            const index = row * grid_width + col;
            ctx.fillStyle = heatmap_data[index];
            ctx.fillRect(col * tileSize, row * tileSize, tileSize, tileSize);
        }
    }

    // --- NEW LOGIC FOR LEGEND RENDERING ---
    const legendContent = document.getElementById('legend-content');
    legendContent.innerHTML = ''; // Clear previous legend

    // Default color legend item
    const defaultColorDiv = document.createElement('div');
    defaultColorDiv.className = 'legend-item';
    defaultColorDiv.innerHTML = `
        <div class="legend-color-box" style="background-color: ${rules_config.default_color};"></div>
        <span>Default (No Rule Matched)</span>
    `;
    legendContent.appendChild(defaultColorDiv);


    rules_config.rules.forEach(rule => {
        const ruleDiv = document.createElement('div');
        ruleDiv.className = 'legend-item';
        ruleDiv.innerHTML = `
            <div class="legend-color-box" style="background-color: ${rule.color};"></div>
            <span>${formatRuleConditions(rule.rule_group)}</span>
        `;
        legendContent.appendChild(ruleDiv);
    });
}

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