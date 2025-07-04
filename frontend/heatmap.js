// frontend/heatmap.js

window.onload = function() {
    // --- Initial Setup ---
    fetchSourceFiles();
    setupEventListeners();
    addRuleBlock(); // Add the first rule by default
};

function setupEventListeners() {
    document.getElementById('generate-btn').addEventListener('click', generateHeatmap);
    document.getElementById('add-rule-btn').addEventListener('click', addRuleBlock);

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

    const ruleId = `rule-${Date.now()}`;
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
            <option value="entropy">Entropy</option>
            <option value="laplacian">Laplacian</option>
            <option value="avg_brightness">Avg. Brightness</option>
            <option value="size">Size</option>
        </select>
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

// --- Main function to generate the heatmap ---
async function generateHeatmap() {
    const selectedFilename = document.getElementById('filename-select').value;
    if (!selectedFilename) {
        alert('Please select a source file.');
        return;
    }

    // --- NEW: Build the rules object dynamically from the UI ---
    const rulesConfig = {
        default_color: "#CCCCCC",
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

    if (rulesConfig.rules.length === 0) {
        alert('Please define at least one valid rule with a condition.');
        return;
    }

    // --- (The rest of the function is the same as before) ---
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
        
        renderHeatmap(data);

    } catch (error) {
        console.error('Error generating heatmap:', error);
        alert('Failed to generate heatmap. Check the console for details.');
    } finally {
        document.getElementById('loading-message').style.display = 'none';
    }
}

// --- (renderHeatmap function is the same as before) ---
function renderHeatmap(data) {
    const canvas = document.getElementById('heatmap-canvas');
    const ctx = canvas.getContext('2d');
    const tileSize = 1;

    if (data.grid_width === 0) return;

    canvas.width = data.grid_width * tileSize;
    canvas.height = data.grid_height * tileSize;

    for (let row = 0; row < data.grid_height; row++) {
        for (let col = 0; col < data.grid_width; col++) {
            const index = row * data.grid_width + col;
            ctx.fillStyle = data.heatmap_data[index];
            ctx.fillRect(col * tileSize, row * tileSize, tileSize, tileSize);
        }
    }
}