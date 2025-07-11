// frontend/dashboard.js

// Add a mapping for display names of keys
const KEY_DISPLAY_MAP = {
    'edge_density': 'Edge Density',
    'foreground_ratio': 'Foreground Ratio',
    'max_subject_area': 'Max Subject Area',
    'laplacian': 'Laplacian',
    'avg_brightness': 'Avg. Brightness',
    'size': 'Size',
    'entropy': 'Entropy',
    'avg_saturation': 'Avg. Saturation'
};

window.onload = function() {
    fetchSummary();
    // Removed calls to fetchDistributionStats as per previous instruction
    
    // Setup for Aggregate Heatmap Rule Statistics
    setupAggregateStatsListeners();
    fetchAndPopulateAggregateRulesDropdown();

    // NEW: Setup for Per-Image Rule Adherence Report
    setupPerImageReportListeners(); // Call new setup function
    fetchAndPopulatePerImageRulesDropdown(); // Populate dropdown on load for per-image report
};

// Function to set up event listeners for the aggregate stats section
function setupAggregateStatsListeners() {
    const selectElement = document.getElementById('aggregate-rule-select');
    const loadButton = document.getElementById('load-aggregate-stats-btn');
    const statsContent = document.getElementById('aggregate-stats-content');

    // Enable/disable load button based on dropdown selection
    selectElement.addEventListener('change', () => {
        loadButton.disabled = !selectElement.value;
        // Clear content if selection is default
        if (!selectElement.value) {
            statsContent.innerHTML = '<p>Please select a rule set and click "Load Statistics".</p>';
        }
    });

    // Event listener for the Load Statistics button
    loadButton.addEventListener('click', fetchAggregateHeatmapStats);
}

// NEW: Function to set up event listeners for the per-image report section
function setupPerImageReportListeners() {
    const selectElement = document.getElementById('per-image-rule-select');
    const generateButton = document.getElementById('generate-report-btn');
    const tableContainer = document.getElementById('per-image-report-table-container');

    // Enable/disable generate button based on dropdown selection
    selectElement.addEventListener('change', () => {
        generateButton.disabled = !selectElement.value;
        // Clear content if selection is default
        if (!selectElement.value) {
            tableContainer.innerHTML = '<p>Please select a rule set and click "Generate Report".</p>';
        }
    });

    // Event listener for the Generate Report button
    generateButton.addEventListener('click', fetchPerImageRuleReport);
}


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


// Function to fetch saved rule names and populate the dropdown for Aggregate Stats
async function fetchAndPopulateAggregateRulesDropdown() {
    const selectElement = document.getElementById('aggregate-rule-select');
    selectElement.innerHTML = '<option value="">-- Load Saved Rules --</option>'; // Clear existing options

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
        console.error("Error fetching saved rules for aggregate dashboard:", error);
        selectElement.innerHTML = '<option value="">Error loading rules</option>';
    }
}

// NEW: Function to fetch saved rule names and populate the dropdown for Per-Image Report
async function fetchAndPopulatePerImageRulesDropdown() {
    const selectElement = document.getElementById('per-image-rule-select');
    selectElement.innerHTML = '<option value="">-- Load Saved Rules --</option>'; // Clear existing options

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
        console.error("Error fetching saved rules for per-image report:", error);
        selectElement.innerHTML = '<option value="">Error loading rules</option>';
    }
}


// Function to fetch and display aggregate heatmap statistics
async function fetchAggregateHeatmapStats() {
    const selectElement = document.getElementById('aggregate-rule-select');
    const ruleName = selectElement.value;
    const statsContent = document.getElementById('aggregate-stats-content');
    const loadButton = document.getElementById('load-aggregate-stats-btn');

    if (!ruleName) {
        statsContent.innerHTML = '<p style="color: red;">Please select a rule set to load statistics.</p>';
        return;
    }

    statsContent.innerHTML = '<p>Loading aggregate statistics...</p>';
    loadButton.disabled = true; // Disable button while loading

    try {
        const response = await fetch(`/api/stats/aggregate_heatmap_rules/${ruleName}`);
        if (!response.ok) {
            const errorData = await response.json(); // Attempt to parse error detail
            throw new Error(errorData.detail || `Failed to fetch aggregate statistics. Status: ${response.status}`);
        }
        const data = await response.json();

        if (data.total_tiles_evaluated === 0) {
            statsContent.innerHTML = '<p>No image tiles found for the selected rule set.</p>';
            return;
        }

        // Build the statistics table
        let tableHtml = `
            <p><strong>Rule Set:</strong> ${ruleName}</p>
            <p><strong>Total Tiles Evaluated:</strong> ${data.total_tiles_evaluated.toLocaleString()}</p>
            <table class="stats-table">
                <thead>
                    <tr>
                        <th>Rule / Category</th>
                        <th>Matched Tiles</th>
                        <th>Percentage</th>
                    </tr>
                </thead>
                <tbody>
        `;

        // Add default (unmatched) tiles row first
        const defaultCount = data.rule_match_counts['default'] || 0;
        const defaultPercentage = (defaultCount / data.total_tiles_evaluated) * 100;
        tableHtml += `
            <tr>
                <td>Default (No Rule Matched)</td>
                <td>${defaultCount.toLocaleString()}</td>
                <td>${defaultPercentage.toFixed(2)}%</td>
            </tr>
        `;

        // Add each rule's stats
        data.rules_config.rules.forEach((rule, index) => {
            const ruleCount = data.rule_match_counts[String(index)] || 0;
            const rulePercentage = (ruleCount / data.total_tiles_evaluated) * 100;
            
            const ruleDescription = formatRuleConditionsForDashboard(rule.rule_group); 

            tableHtml += `
                <tr>
                    <td>${ruleDescription}</td>
                    <td>${ruleCount.toLocaleString()}</td>
                    <td>${rulePercentage.toFixed(2)}%</td>
                </tr>
            `;
        });

        tableHtml += `
                </tbody>
            </table>
        `;
        statsContent.innerHTML = tableHtml;

    } catch (error) {
        console.error("Error fetching aggregate heatmap stats:", error);
        statsContent.innerHTML = `<p style="color: red;">Failed to load statistics: ${error.message}. Please check console.</p>`;
    } finally {
        loadButton.disabled = false; // Re-enable button
    }
}


// NEW: Function to fetch and display per-image rule adherence report
async function fetchPerImageRuleReport() {
    const selectElement = document.getElementById('per-image-rule-select');
    const ruleName = selectElement.value;
    const tableContainer = document.getElementById('per-image-report-table-container');
    const generateButton = document.getElementById('generate-report-btn');

    if (!ruleName) {
        tableContainer.innerHTML = '<p style="color: red;">Please select a rule set to generate the report.</p>';
        return;
    }

    tableContainer.innerHTML = '<p>Generating per-image report...</p>';
    generateButton.disabled = true; // Disable button while loading

    try {
        const response = await fetch(`/api/stats/per_image_rule_report/${ruleName}`);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `Failed to fetch per-image report. Status: ${response.status}`);
        }
        const data = await response.json(); // This data contains report_data and rules_config

        if (!data.report_data || data.report_data.length === 0) {
            tableContainer.innerHTML = '<p>No image files found for the selected rule set.</p>';
            return;
        }

        // Build table headers dynamically based on rules_config
        let tableHtml = `
            <p><strong>Report based on Rule Set:</strong> ${ruleName}</p>
            <table class="stats-table">
                <thead>
                    <tr>
                        <th>JSON Filename</th>
                        <th>Total Tiles</th>
        `;
        
        // Add headers for each rule
        data.rules_config.rules.forEach((rule, index) => {
            const ruleDescription = formatRuleConditionsForDashboard(rule.rule_group);
            tableHtml += `
                <th>${ruleDescription} (Count)</th>
                <th>${ruleDescription} (%)</th>
            `;
        });

        // Add headers for default category
        tableHtml += `
                    <th>Default (Count)</th>
                    <th>Default (%)</th>
                </tr>
                </thead>
                <tbody>
        `;

        // Build table rows
        data.report_data.forEach(fileReport => {
            tableHtml += `
                <tr>
                    <td>${fileReport.json_filename}</td>
                    <td>${fileReport.total_tiles_evaluated_for_file.toLocaleString()}</td>
            `;

            // Display stats for each rule for this file
            data.rules_config.rules.forEach((rule, index) => {
                const ruleDetail = fileReport.rule_match_details.find(d => d.rule_index === String(index)) || {count: 0, percentage: 0};
                tableHtml += `
                    <td>${ruleDetail.count.toLocaleString()}</td>
                    <td>${ruleDetail.percentage.toFixed(2)}%</td>
                `;
            });

            // Display stats for default category for this file
            const defaultDetail = fileReport.rule_match_details.find(d => d.rule_index === 'default') || {count: 0, percentage: 0};
            tableHtml += `
                <td>${defaultDetail.count.toLocaleString()}</td>
                <td>${defaultDetail.percentage.toFixed(2)}%</td>
            `;
            tableHtml += `</tr>`;
        });

        tableHtml += `
                </tbody>
            </table>
        `;
        tableContainer.innerHTML = tableHtml;

    } catch (error) {
        console.error("Error fetching per-image report:", error);
        tableContainer.innerHTML = `<p style="color: red;">Failed to load report: ${error.message}. Please check console.</p>`;
    } finally {
        generateButton.disabled = false; // Re-enable button
    }
}


// Helper function to format rule conditions for dashboard display
function formatRuleConditionsForDashboard(ruleGroup) {
    const conditions = ruleGroup.conditions.map(cond => {
        const displayKey = KEY_DISPLAY_MAP[cond.key] || cond.key;
        return `${displayKey} ${cond.op} ${cond.value.toFixed(2)}`;
    });
    const logicalOpDisplay = ruleGroup.logical_op.toUpperCase();
    if (conditions.length > 1) {
        return `(${conditions.join(` ${logicalOpDisplay} `)})`;
    }
    return conditions.join('');
}