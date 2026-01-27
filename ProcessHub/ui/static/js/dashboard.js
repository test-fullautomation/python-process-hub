/**
 * Process Hub Dashboard JavaScript
 *
 * Copyright 2020-2026 Robert Bosch GmbH
 * Licensed under the Apache License, Version 2.0
 */

// ============================================================================
// Utility Functions
// ============================================================================

function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleTimeString();
}

function getStatusClass(status) {
    const statusMap = {
        'running': 'status-running',
        'stopped': 'status-stopped',
        'starting': 'status-starting',
        'stopping': 'status-stopping',
        'dead': 'status-dead',
        'failed': 'status-failed',
        'registered': 'status-registered'
    };
    return statusMap[status.toLowerCase()] || 'status-registered';
}

function getPhaseClass(phase) {
    const phaseMap = {
        'idle': 'phase-idle',
        'detecting': 'phase-detecting',
        'notifying': 'phase-notifying',
        'awaiting_ack': 'phase-awaiting',
        'restarting': 'phase-restarting',
        'done': 'phase-done',
        'failed': 'phase-failed'
    };
    return phaseMap[phase.toLowerCase()] || 'phase-idle';
}

// ============================================================================
// Tab Navigation Functions
// ============================================================================

let currentTab = 'dashboard';

function switchTab(tabName) {
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.tab === tabName) {
            item.classList.add('active');
        }
    });

    // Update views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    const targetView = document.getElementById('view-' + tabName);
    if (targetView) {
        targetView.classList.add('active');
    }

    currentTab = tabName;

    // Store in localStorage for persistence
    localStorage.setItem('processHubTab', tabName);
}

function setupTabNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const tabName = item.dataset.tab;
            if (tabName && !item.classList.contains('disabled')) {
                switchTab(tabName);
            }
        });
    });

    // Restore last tab from localStorage
    const savedTab = localStorage.getItem('processHubTab');
    if (savedTab && document.getElementById('view-' + savedTab)) {
        switchTab(savedTab);
    }
}

// ============================================================================
// Dashboard Update Functions
// ============================================================================

function updateDashboard(data) {
    // Update stats
    document.getElementById('connectionCount').textContent = data.connections.length;
    document.getElementById('processCount').textContent = data.processes.length;
    document.getElementById('runningCount').textContent =
        data.processes.filter(p => p.state === 'running').length;
    document.getElementById('restartPhase').textContent = data.restart.phase.toUpperCase();
    document.getElementById('lastUpdate').textContent = 'Updated: ' + new Date().toLocaleTimeString();

    // Update restart section
    const restartSection = document.getElementById('restartSection');
    const restartContent = document.getElementById('restartContent');

    if (data.restart.phase === 'idle') {
        restartSection.classList.add('idle');
        restartSection.classList.remove('restart-section');
        restartContent.innerHTML = '<p style="color: #888;">No restart in progress</p>';
    } else {
        restartSection.classList.remove('idle');
        restartSection.classList.add('restart-section');
        restartContent.innerHTML = `
            <p><span class="phase-badge ${getPhaseClass(data.restart.phase)}">${data.restart.phase}</span></p>
            ${data.restart.killed_processes.length > 0 ?
                '<p style="margin-top: 10px;"><strong>Killed processes:</strong> ' + data.restart.killed_processes.join(', ') + '</p>' : ''}
            ${data.restart.pending_panels.length > 0 ?
                '<p><strong>Pending panels:</strong> ' + data.restart.pending_panels.join(', ') + '</p>' : ''}
        `;
    }

    // Update connections table
    const connectionsContent = document.getElementById('connectionsContent');
    if (data.connections.length === 0) {
        connectionsContent.innerHTML = '<div class="empty-state">No connections</div>';
    } else {
        connectionsContent.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Panel ID</th>
                        <th>Session ID</th>
                        <th>Connected At</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.connections.map(conn => `
                        <tr>
                            <td>${conn.panel_id}</td>
                            <td>${conn.session_id}</td>
                            <td>${formatDate(conn.connected_at)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    // Update processes table
    const processesContent = document.getElementById('processesContent');
    if (data.processes.length === 0) {
        processesContent.innerHTML = '<div class="empty-state">No processes</div>';
    } else {
        processesContent.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Process</th>
                        <th>PID</th>
                        <th>Status</th>
                        <th>Owners</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.processes.map(proc => `
                        <tr>
                            <td>${proc.name}</td>
                            <td>${proc.pid || '-'}</td>
                            <td><span class="status-badge ${getStatusClass(proc.state)}">${proc.state}</span></td>
                            <td>${proc.requesters.join(', ') || '-'}</td>
                            <td class="actions-cell">
                                ${getProcessActions(proc.name, proc.state)}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }
}

function getProcessActions(name, state) {
    const isRunning = state === 'running';
    const isStopped = state === 'stopped' || state === 'dead' || state === 'failed';

    if (!adminEnabled) {
        return '<span style="color: #666; font-size: 11px;">Admin disabled</span>';
    }

    let buttons = '';

    if (isStopped) {
        buttons += `<button class="action-btn action-btn-start" onclick="adminStartByName('${name}')">Start</button>`;
    }

    if (isRunning) {
        buttons += `<button class="action-btn action-btn-stop" onclick="adminStopByName('${name}', false)">Stop</button>`;
        buttons += `<button class="action-btn action-btn-kill" onclick="adminStopByName('${name}', true)">Kill</button>`;
    }

    if (!isRunning && !isStopped) {
        // For other states like 'starting', 'stopping', show disabled buttons
        buttons += `<button class="action-btn action-btn-stop" disabled>...</button>`;
    }

    return buttons || '-';
}

function fetchData() {
    fetch('/api/state')
        .then(response => response.json())
        .then(data => updateDashboard(data))
        .catch(error => console.error('Error fetching data:', error));
}

// ============================================================================
// Console Log Functions
// ============================================================================

let lastLogCount = 0;
let currentLoggerFilter = '';
let currentLoggerInclude = '';
let currentLoggerExclude = '';
let currentLevelFilter = '';
let knownLoggers = new Set();
let filterDebounceTimer = null;

function formatLogTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { hour12: false }) + '.' +
           date.getMilliseconds().toString().padStart(3, '0');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateLogsDisplay(data) {
    const consoleLog = document.getElementById('consoleLog');
    const logCount = document.getElementById('logCount');
    const autoScroll = document.getElementById('autoScroll').checked;

    // Update logger dropdown with new loggers from API
    if (data.loggers && data.loggers.length > 0) {
        updateLoggerDropdown(data.loggers);
    }

    // Show filtered count vs total
    const hasFilters = currentLoggerFilter || currentLoggerInclude || currentLoggerExclude || currentLevelFilter;
    const filterInfo = hasFilters ? ' (filtered)' : '';
    logCount.textContent = data.total + ' entries' + filterInfo;

    if (data.logs.length === 0) {
        const emptyMsg = hasFilters
            ? 'No logs matching filter'
            : 'No logs yet';
        consoleLog.innerHTML = `<div class="empty-state">${emptyMsg}</div>`;
        return;
    }

    // Only update if there are new logs
    if (data.total !== lastLogCount) {
        lastLogCount = data.total;

        const logsHtml = data.logs.map(log => `
            <div class="log-entry">
                <span class="log-timestamp">${formatLogTime(log.timestamp)}</span>
                <span class="log-level log-level-${log.level}">${log.level}</span>
                <span class="log-logger">${escapeHtml(log.logger_name)}</span>
                <span class="log-message">${escapeHtml(log.message)}</span>
            </div>
        `).join('');

        consoleLog.innerHTML = logsHtml;

        // Auto-scroll to bottom
        if (autoScroll) {
            consoleLog.scrollTop = consoleLog.scrollHeight;
        }
    }
}

function updateLoggerDropdown(loggers) {
    const select = document.getElementById('loggerFilter');
    if (!select) return;

    // Check if we have new loggers
    let hasNewLoggers = false;
    for (const logger of loggers) {
        if (!knownLoggers.has(logger)) {
            knownLoggers.add(logger);
            hasNewLoggers = true;
        }
    }

    // Only rebuild dropdown if we have new loggers
    if (hasNewLoggers) {
        const currentValue = select.value;

        // Clear and rebuild options
        select.innerHTML = '<option value="">All Loggers</option>';

        // Sort loggers alphabetically
        const sortedLoggers = Array.from(knownLoggers).sort();

        for (const logger of sortedLoggers) {
            const option = document.createElement('option');
            option.value = logger;
            option.textContent = logger;
            select.appendChild(option);
        }

        // Restore previous selection
        select.value = currentValue;
    }
}

function fetchLogs() {
    let url = '/api/logs?limit=500';

    if (currentLoggerFilter) {
        url += '&logger_filter=' + encodeURIComponent(currentLoggerFilter);
    }
    if (currentLoggerInclude) {
        url += '&logger_prefix=' + encodeURIComponent(currentLoggerInclude);
    }
    if (currentLoggerExclude) {
        url += '&logger_exclude=' + encodeURIComponent(currentLoggerExclude);
    }
    if (currentLevelFilter) {
        url += '&level_filter=' + encodeURIComponent(currentLevelFilter);
    }

    fetch(url)
        .then(response => response.json())
        .then(data => updateLogsDisplay(data))
        .catch(error => console.error('Error fetching logs:', error));
}

function onLoggerFilterChange() {
    const select = document.getElementById('loggerFilter');
    currentLoggerFilter = select.value;
    lastLogCount = -1;  // Force refresh
    fetchLogs();
}

function onIncludeFilterChange() {
    // Debounce to avoid too many requests while typing
    clearTimeout(filterDebounceTimer);
    filterDebounceTimer = setTimeout(() => {
        const input = document.getElementById('loggerInclude');
        currentLoggerInclude = input.value.trim();
        lastLogCount = -1;  // Force refresh
        fetchLogs();
    }, 300);
}

function onExcludeFilterChange() {
    // Debounce to avoid too many requests while typing
    clearTimeout(filterDebounceTimer);
    filterDebounceTimer = setTimeout(() => {
        const input = document.getElementById('loggerExclude');
        currentLoggerExclude = input.value.trim();
        lastLogCount = -1;  // Force refresh
        fetchLogs();
    }, 300);
}

function onLevelFilterChange() {
    const select = document.getElementById('levelFilter');
    currentLevelFilter = select.value;
    lastLogCount = -1;  // Force refresh
    fetchLogs();
}

function resetLogFilters() {
    document.getElementById('loggerFilter').value = '';
    document.getElementById('loggerInclude').value = '';
    document.getElementById('loggerExclude').value = '';
    document.getElementById('levelFilter').value = '';
    currentLoggerFilter = '';
    currentLoggerInclude = '';
    currentLoggerExclude = '';
    currentLevelFilter = '';
    lastLogCount = -1;  // Force refresh
    fetchLogs();
}

function downloadLogs() {
    // Trigger download via API
    window.location.href = '/api/logs/download';
}

function clearLogs() {
    if (confirm('Are you sure you want to clear all logs?')) {
        fetch('/api/logs', { method: 'DELETE' })
            .then(response => response.json())
            .then(data => {
                lastLogCount = 0;
                knownLoggers.clear();
                // Reset logger dropdown
                const select = document.getElementById('loggerFilter');
                if (select) {
                    select.innerHTML = '<option value="">All Loggers</option>';
                    currentLoggerFilter = '';
                }
                fetchLogs();
            })
            .catch(error => console.error('Error clearing logs:', error));
    }
}

// ============================================================================
// Admin API Functions
// ============================================================================

let adminEnabled = false;
let resetEnabled = false;

function checkAdminStatus() {
    fetch('/api/admin/status')
        .then(response => response.json())
        .then(data => {
            adminEnabled = data.enabled;
            resetEnabled = data.reset_enabled || false;
            const statusEl = document.getElementById('adminStatus');
            const sectionEl = document.getElementById('adminSection');
            const navBadge = document.getElementById('adminBadge');
            const navItem = document.getElementById('navAdmin');

            if (data.enabled) {
                if (statusEl) {
                    statusEl.textContent = 'Enabled';
                    statusEl.classList.remove('disabled');
                }
                if (sectionEl) sectionEl.classList.remove('disabled');
                if (navBadge) {
                    navBadge.textContent = 'ON';
                    navBadge.classList.remove('disabled');
                }
                if (navItem) navItem.classList.remove('disabled');
            } else {
                if (statusEl) {
                    statusEl.textContent = 'Disabled';
                    statusEl.classList.add('disabled');
                }
                if (sectionEl) sectionEl.classList.add('disabled');
                if (navBadge) {
                    navBadge.textContent = 'OFF';
                    navBadge.classList.add('disabled');
                }
                if (navItem) navItem.classList.add('disabled');
            }
        })
        .catch(error => {
            console.error('Error checking admin status:', error);
            const statusEl = document.getElementById('adminStatus');
            if (statusEl) {
                statusEl.textContent = 'Error';
                statusEl.classList.add('disabled');
            }
        });
}

function showAdminResult(success, message) {
    const resultEl = document.getElementById('adminResult');
    resultEl.textContent = message;
    resultEl.className = 'admin-result ' + (success ? 'success' : 'error');

    // Auto-hide after 5 seconds
    setTimeout(() => {
        resultEl.className = 'admin-result';
    }, 5000);
}

function adminStartProcess() {
    const processName = document.getElementById('processName').value.trim();
    if (!processName) {
        showAdminResult(false, 'Please enter a process name');
        return;
    }

    if (!adminEnabled) {
        showAdminResult(false, 'Admin API is not enabled');
        return;
    }

    fetch(`/api/admin/processes/${encodeURIComponent(processName)}/start`, {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            showAdminResult(data.success, data.message);
            if (data.success) {
                document.getElementById('processName').value = '';
            }
        })
        .catch(error => {
            showAdminResult(false, 'Error: ' + error.message);
        });
}

function adminStopProcess(force = false) {
    const processName = document.getElementById('processName').value.trim();
    if (!processName) {
        showAdminResult(false, 'Please enter a process name');
        return;
    }

    if (!adminEnabled) {
        showAdminResult(false, 'Admin API is not enabled');
        return;
    }

    const url = `/api/admin/processes/${encodeURIComponent(processName)}/stop?force=${force}`;
    fetch(url, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            showAdminResult(data.success, data.message);
            if (data.success) {
                document.getElementById('processName').value = '';
            }
        })
        .catch(error => {
            showAdminResult(false, 'Error: ' + error.message);
        });
}

// Inline action button handlers
function adminStartByName(name) {
    if (!adminEnabled) return;

    fetch(`/api/admin/processes/${encodeURIComponent(name)}/start`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            showAdminResult(data.success, data.message);
            fetchData();  // Refresh process list
        })
        .catch(error => {
            showAdminResult(false, 'Error: ' + error.message);
        });
}

function adminStopByName(name, force) {
    if (!adminEnabled) return;

    const url = `/api/admin/processes/${encodeURIComponent(name)}/stop?force=${force}`;
    fetch(url, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            showAdminResult(data.success, data.message);
            fetchData();  // Refresh process list
        })
        .catch(error => {
            showAdminResult(false, 'Error: ' + error.message);
        });
}

function resetHub() {
    if (!resetEnabled) {
        showAdminResult(false, 'Reset hub is not enabled');
        return;
    }

    if (!confirm('Are you sure you want to reset the hub?\n\nThis will:\n- Remove all connections\n- Stop all processes\n\nAll connected clients will be disconnected.')) {
        return;
    }

    fetch('/api/admin/reset', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            showAdminResult(data.success, data.message);
            fetchData();  // Refresh data
        })
        .catch(error => {
            showAdminResult(false, 'Error: ' + error.message);
        });
}

// ============================================================================
// Process Autocomplete Functions
// ============================================================================

let availableProcesses = [];
let selectedAutocompleteIndex = -1;

function fetchAvailableProcesses() {
    fetch('/api/admin/available-processes')
        .then(response => response.json())
        .then(data => {
            availableProcesses = data.processes || [];
            updateProcessChips();
        })
        .catch(error => {
            console.error('Error fetching available processes:', error);
            availableProcesses = [];
            updateProcessChips();
        });
}

function updateProcessChips() {
    const container = document.getElementById('processChips');
    if (!container) return;

    if (availableProcesses.length === 0) {
        container.innerHTML = '<span class="empty-state">No processes configured</span>';
        return;
    }

    container.innerHTML = availableProcesses.map(name =>
        `<span class="process-chip" onclick="startProcessFromChip('${escapeHtml(name)}')">${escapeHtml(name)}</span>`
    ).join('');
}

function startProcessFromChip(name) {
    if (!adminEnabled) {
        showAdminResult(false, 'Admin API is not enabled');
        return;
    }

    fetch(`/api/admin/processes/${encodeURIComponent(name)}/start`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            showAdminResult(data.success, data.message);
            fetchData();  // Refresh process list
        })
        .catch(error => {
            showAdminResult(false, 'Error: ' + error.message);
        });
}

function highlightMatch(text, query) {
    if (!query) return text;
    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return text.replace(regex, '<span class="highlight">$1</span>');
}

function showAutocomplete(filtered, query) {
    const dropdown = document.getElementById('processAutocomplete');

    if (filtered.length === 0) {
        if (query.length > 0) {
            dropdown.innerHTML = '<div class="autocomplete-empty">No matching processes</div>';
            dropdown.classList.add('show');
        } else {
            dropdown.classList.remove('show');
        }
        return;
    }

    dropdown.innerHTML = filtered.map((name, index) => `
        <div class="autocomplete-item${index === selectedAutocompleteIndex ? ' selected' : ''}"
             data-value="${name}"
             onclick="selectAutocompleteItem('${name}')">
            ${highlightMatch(name, query)}
        </div>
    `).join('');

    dropdown.classList.add('show');
}

function hideAutocomplete() {
    const dropdown = document.getElementById('processAutocomplete');
    dropdown.classList.remove('show');
    selectedAutocompleteIndex = -1;
}

function selectAutocompleteItem(value) {
    const input = document.getElementById('processName');
    input.value = value;
    hideAutocomplete();
    input.focus();
}

function filterProcesses(query) {
    if (!query) return availableProcesses.slice(0, 10);  // Show first 10 when empty

    const lowerQuery = query.toLowerCase();
    return availableProcesses
        .filter(name => name.toLowerCase().includes(lowerQuery))
        .slice(0, 10);  // Limit to 10 results
}

function setupAutocomplete() {
    const input = document.getElementById('processName');
    const dropdown = document.getElementById('processAutocomplete');

    if (!input || !dropdown) return;

    // Input event - filter as user types
    input.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        selectedAutocompleteIndex = -1;
        const filtered = filterProcesses(query);
        showAutocomplete(filtered, query);
    });

    // Focus event - show suggestions
    input.addEventListener('focus', () => {
        const query = input.value.trim();
        const filtered = filterProcesses(query);
        if (filtered.length > 0 || query.length > 0) {
            showAutocomplete(filtered, query);
        }
    });

    // Keyboard navigation
    input.addEventListener('keydown', (e) => {
        const items = dropdown.querySelectorAll('.autocomplete-item');

        if (!dropdown.classList.contains('show') || items.length === 0) {
            if (e.key === 'Enter') {
                adminStartProcess();
            }
            return;
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                selectedAutocompleteIndex = Math.min(selectedAutocompleteIndex + 1, items.length - 1);
                updateAutocompleteSelection(items);
                break;

            case 'ArrowUp':
                e.preventDefault();
                selectedAutocompleteIndex = Math.max(selectedAutocompleteIndex - 1, -1);
                updateAutocompleteSelection(items);
                break;

            case 'Enter':
                e.preventDefault();
                if (selectedAutocompleteIndex >= 0 && items[selectedAutocompleteIndex]) {
                    const value = items[selectedAutocompleteIndex].dataset.value;
                    selectAutocompleteItem(value);
                } else {
                    hideAutocomplete();
                    adminStartProcess();
                }
                break;

            case 'Escape':
                hideAutocomplete();
                break;

            case 'Tab':
                hideAutocomplete();
                break;
        }
    });

    // Click outside to close
    document.addEventListener('click', (e) => {
        if (!input.contains(e.target) && !dropdown.contains(e.target)) {
            hideAutocomplete();
        }
    });
}

function updateAutocompleteSelection(items) {
    items.forEach((item, index) => {
        if (index === selectedAutocompleteIndex) {
            item.classList.add('selected');
            item.scrollIntoView({ block: 'nearest' });
        } else {
            item.classList.remove('selected');
        }
    });
}

// ============================================================================
// Process Configuration Functions
// ============================================================================

let configEnabled = false;
let editingConfig = null;  // Track which config is being edited

function checkConfigStatus() {
    fetch('/api/admin/config')
        .then(response => response.json())
        .then(data => {
            configEnabled = data.config_enabled;
            const statusEl = document.getElementById('configStatus');
            const sectionEl = document.getElementById('configSection');
            const navBadge = document.getElementById('configBadge');
            const navItem = document.getElementById('navConfig');

            if (data.config_enabled) {
                if (statusEl) {
                    statusEl.textContent = 'Enabled';
                    statusEl.classList.remove('disabled');
                }
                if (sectionEl) sectionEl.classList.remove('disabled');
                if (navBadge) {
                    navBadge.textContent = 'ON';
                    navBadge.classList.remove('disabled');
                }
                if (navItem) navItem.classList.remove('disabled');
                updateConfigTable(data.configs);
            } else {
                if (statusEl) {
                    statusEl.textContent = 'Disabled';
                    statusEl.classList.add('disabled');
                }
                if (sectionEl) sectionEl.classList.add('disabled');
                if (navBadge) {
                    navBadge.textContent = 'OFF';
                    navBadge.classList.add('disabled');
                }
                if (navItem) navItem.classList.add('disabled');
                const tableContent = document.getElementById('configTableContent');
                if (tableContent) {
                    tableContent.innerHTML = '<div class="empty-state">Config management not enabled</div>';
                }
            }
        })
        .catch(error => {
            console.error('Error checking config status:', error);
            const statusEl = document.getElementById('configStatus');
            if (statusEl) {
                statusEl.textContent = 'Error';
                statusEl.classList.add('disabled');
            }
        });
}

function fetchConfigs() {
    if (!configEnabled) return;

    fetch('/api/admin/config')
        .then(response => response.json())
        .then(data => {
            if (data.config_enabled) {
                updateConfigTable(data.configs);
            }
        })
        .catch(error => {
            console.error('Error fetching configs:', error);
        });
}

function updateConfigTable(configs) {
    const container = document.getElementById('configTableContent');
    const configNames = Object.keys(configs);

    if (configNames.length === 0) {
        container.innerHTML = '<div class="empty-state">No configurations</div>';
        return;
    }

    container.innerHTML = `
        <table class="config-table">
            <thead>
                <tr>
                    <th class="col-name">Name</th>
                    <th class="col-script">Script</th>
                    <th class="col-args">Arguments</th>
                    <th class="col-wait">Wait</th>
                    <th class="col-flags">Flags</th>
                    <th class="col-desc">Description</th>
                    <th class="col-actions">Actions</th>
                </tr>
            </thead>
            <tbody>
                ${configNames.map(name => {
                    const cfg = configs[name];
                    const args = cfg.args ? JSON.stringify(cfg.args) : '-';
                    const flags = getConfigFlags(cfg);
                    const description = cfg.description || '-';
                    return `
                        <tr>
                            <td class="col-name"><strong>${escapeHtml(name)}</strong></td>
                            <td class="col-script script-cell" title="${escapeHtml(cfg.script || '')}">${escapeHtml(cfg.script || '-')}</td>
                            <td class="col-args args-cell" title="${escapeHtml(args)}">${escapeHtml(args)}</td>
                            <td class="col-wait">${cfg.wait_time || 2.0}s</td>
                            <td class="col-flags">${flags}</td>
                            <td class="col-desc desc-cell" title="${escapeHtml(description)}">${escapeHtml(description)}</td>
                            <td class="col-actions config-actions">
                                <button class="btn btn-small btn-edit" onclick="editConfig('${escapeHtml(name)}')">Edit</button>
                                <button class="btn btn-small btn-delete" onclick="removeConfig('${escapeHtml(name)}')">Remove</button>
                            </td>
                        </tr>
                    `;
                }).join('')}
            </tbody>
        </table>
    `;
}

function getConfigFlags(cfg) {
    const flags = [];

    if (cfg.enable !== false) {
        flags.push('<span class="config-flag flag-enabled" title="Enabled">E</span>');
    } else {
        flags.push('<span class="config-flag flag-disabled" title="Disabled">D</span>');
    }

    if (cfg.mandatory === true) {
        flags.push('<span class="config-flag flag-mandatory" title="Mandatory">M</span>');
    }

    if (cfg.central_log === true) {
        flags.push('<span class="config-flag flag-centrallog" title="Central Log">L</span>');
    }

    return flags.length > 0 ? flags.join('') : '-';
}

function showConfigResult(success, message) {
    const resultEl = document.getElementById('configResult');
    resultEl.textContent = message;
    resultEl.className = 'config-result ' + (success ? 'success' : 'error');

    // Auto-hide after 5 seconds
    setTimeout(() => {
        resultEl.className = 'config-result';
    }, 5000);
}

function clearConfigForm() {
    document.getElementById('configName').value = '';
    document.getElementById('configScript').value = '';
    document.getElementById('configArgs').value = '';
    document.getElementById('configWaitTime').value = '2.0';
    document.getElementById('configEnv').value = '';
    document.getElementById('configDescription').value = '';
    document.getElementById('configWarning').value = '';
    document.getElementById('configEnable').checked = true;
    document.getElementById('configMandatory').checked = false;
    document.getElementById('configCentralLog').checked = false;

    // Reset edit mode
    cancelEdit();
}

function cancelEdit() {
    editingConfig = null;
    const form = document.getElementById('configForm');
    const nameInput = document.getElementById('configName');

    form.classList.remove('editing');
    nameInput.disabled = false;

    // Update button text back to "Add Configuration"
    const addBtn = form.querySelector('.btn-success');
    if (addBtn) {
        addBtn.textContent = 'Add Configuration';
        addBtn.onclick = addProcessConfig;
    }

    // Remove cancel button if exists
    const cancelBtn = form.querySelector('.btn-cancel');
    if (cancelBtn) {
        cancelBtn.remove();
    }
}

function addProcessConfig() {
    if (!configEnabled) {
        showConfigResult(false, 'Config management is not enabled');
        return;
    }

    const name = document.getElementById('configName').value.trim();
    const script = document.getElementById('configScript').value.trim();
    const argsStr = document.getElementById('configArgs').value.trim();
    const waitTime = parseFloat(document.getElementById('configWaitTime').value) || 2.0;
    const envStr = document.getElementById('configEnv').value.trim();
    const description = document.getElementById('configDescription').value.trim();
    const warningOnDeselect = document.getElementById('configWarning').value.trim();
    const enable = document.getElementById('configEnable').checked;
    const mandatory = document.getElementById('configMandatory').checked;
    const centralLog = document.getElementById('configCentralLog').checked;

    // Validation
    if (!name) {
        showConfigResult(false, 'Process name is required');
        return;
    }
    if (!script) {
        showConfigResult(false, 'Script path is required');
        return;
    }

    // Parse args
    let args = [];
    if (argsStr) {
        try {
            args = JSON.parse(argsStr);
            if (!Array.isArray(args)) {
                showConfigResult(false, 'Arguments must be a JSON array');
                return;
            }
        } catch (e) {
            showConfigResult(false, 'Invalid JSON in Arguments: ' + e.message);
            return;
        }
    }

    // Parse env
    let env = {};
    if (envStr) {
        try {
            env = JSON.parse(envStr);
            if (typeof env !== 'object' || Array.isArray(env)) {
                showConfigResult(false, 'Environment must be a JSON object');
                return;
            }
        } catch (e) {
            showConfigResult(false, 'Invalid JSON in Environment: ' + e.message);
            return;
        }
    }

    const payload = {
        name: name,
        config: {
            script: script,
            args: args,
            wait_time: waitTime,
            process_name: name,
            env: env,
            description: description,
            enable: enable,
            mandatory: mandatory,
            central_log: centralLog,
            warning_on_deselect: warningOnDeselect
        }
    };

    fetch('/api/admin/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(response => response.json())
        .then(data => {
            showConfigResult(data.success, data.message);
            if (data.success) {
                clearConfigForm();
                fetchConfigs();
                fetchAvailableProcesses();  // Refresh autocomplete list
            }
        })
        .catch(error => {
            showConfigResult(false, 'Error: ' + error.message);
        });
}

function removeConfig(name) {
    if (!configEnabled) {
        showConfigResult(false, 'Config management is not enabled');
        return;
    }

    if (!confirm(`Are you sure you want to remove configuration "${name}"?`)) {
        return;
    }

    fetch(`/api/admin/config/${encodeURIComponent(name)}`, {
        method: 'DELETE'
    })
        .then(response => response.json())
        .then(data => {
            showConfigResult(data.success, data.message);
            if (data.success) {
                fetchConfigs();
                fetchAvailableProcesses();  // Refresh autocomplete list
            }
        })
        .catch(error => {
            showConfigResult(false, 'Error: ' + error.message);
        });
}

function editConfig(name) {
    if (!configEnabled) {
        showConfigResult(false, 'Config management is not enabled');
        return;
    }

    // Fetch current configs to get the data
    fetch('/api/admin/config')
        .then(response => response.json())
        .then(data => {
            if (!data.config_enabled || !data.configs[name]) {
                showConfigResult(false, `Configuration "${name}" not found`);
                return;
            }

            const cfg = data.configs[name];
            editingConfig = name;

            // Populate form with existing values
            document.getElementById('configName').value = name;
            document.getElementById('configScript').value = cfg.script || '';
            document.getElementById('configWaitTime').value = cfg.wait_time || 2.0;
            document.getElementById('configArgs').value =
                cfg.args && cfg.args.length > 0 ? JSON.stringify(cfg.args, null, 2) : '';
            document.getElementById('configEnv').value =
                cfg.env && Object.keys(cfg.env).length > 0 ? JSON.stringify(cfg.env, null, 2) : '';
            document.getElementById('configDescription').value = cfg.description || '';
            document.getElementById('configWarning').value = cfg.warning_on_deselect || '';
            document.getElementById('configEnable').checked = cfg.enable !== false;
            document.getElementById('configMandatory').checked = cfg.mandatory === true;
            document.getElementById('configCentralLog').checked = cfg.central_log === true;

            // Set form to edit mode
            const form = document.getElementById('configForm');
            const nameInput = document.getElementById('configName');
            const addBtn = form.querySelector('.btn-success');

            form.classList.add('editing');
            nameInput.disabled = true;  // Can't change name during edit

            // Change button text to "Update Configuration"
            if (addBtn) {
                addBtn.textContent = 'Update Configuration';
                addBtn.onclick = updateProcessConfig;
            }

            // Add cancel button if not exists
            if (!form.querySelector('.btn-cancel')) {
                const cancelBtn = document.createElement('button');
                cancelBtn.className = 'btn btn-secondary btn-cancel';
                cancelBtn.textContent = 'Cancel';
                cancelBtn.type = 'button';
                cancelBtn.onclick = cancelEdit;
                addBtn.parentNode.insertBefore(cancelBtn, addBtn);
            }

            // Scroll to form
            form.scrollIntoView({ behavior: 'smooth', block: 'start' });

            showConfigResult(true, `Editing configuration: ${name}`);
        })
        .catch(error => {
            showConfigResult(false, 'Error: ' + error.message);
        });
}

function updateProcessConfig() {
    if (!configEnabled) {
        showConfigResult(false, 'Config management is not enabled');
        return;
    }

    if (!editingConfig) {
        showConfigResult(false, 'No configuration is being edited');
        return;
    }

    const name = editingConfig;
    const script = document.getElementById('configScript').value.trim();
    const argsStr = document.getElementById('configArgs').value.trim();
    const waitTime = parseFloat(document.getElementById('configWaitTime').value) || 2.0;
    const envStr = document.getElementById('configEnv').value.trim();
    const description = document.getElementById('configDescription').value.trim();
    const warningOnDeselect = document.getElementById('configWarning').value.trim();
    const enable = document.getElementById('configEnable').checked;
    const mandatory = document.getElementById('configMandatory').checked;
    const centralLog = document.getElementById('configCentralLog').checked;

    // Validation
    if (!script) {
        showConfigResult(false, 'Script path is required');
        return;
    }

    // Parse args
    let args = [];
    if (argsStr) {
        try {
            args = JSON.parse(argsStr);
            if (!Array.isArray(args)) {
                showConfigResult(false, 'Arguments must be a JSON array');
                return;
            }
        } catch (e) {
            showConfigResult(false, 'Invalid JSON in Arguments: ' + e.message);
            return;
        }
    }

    // Parse env
    let env = {};
    if (envStr) {
        try {
            env = JSON.parse(envStr);
            if (typeof env !== 'object' || Array.isArray(env)) {
                showConfigResult(false, 'Environment must be a JSON object');
                return;
            }
        } catch (e) {
            showConfigResult(false, 'Invalid JSON in Environment: ' + e.message);
            return;
        }
    }

    const payload = {
        config: {
            script: script,
            args: args,
            wait_time: waitTime,
            process_name: name,
            env: env,
            description: description,
            enable: enable,
            mandatory: mandatory,
            central_log: centralLog,
            warning_on_deselect: warningOnDeselect
        }
    };

    fetch(`/api/admin/config/${encodeURIComponent(name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(response => response.json())
        .then(data => {
            showConfigResult(data.success, data.message);
            if (data.success) {
                clearConfigForm();  // This also calls cancelEdit()
                fetchConfigs();
            }
        })
        .catch(error => {
            showConfigResult(false, 'Error: ' + error.message);
        });
}

// ============================================================================
// Initialization
// ============================================================================

// Setup tab navigation
setupTabNavigation();

// Initial fetch
fetchData();
fetchLogs();
fetchAvailableProcesses();

// Check admin status on load
checkAdminStatus();
checkConfigStatus();

// Setup autocomplete
setupAutocomplete();

// Refresh data
setInterval(fetchData, 1000);
setInterval(fetchLogs, 2000);  // Logs refresh every 2 seconds
setInterval(fetchAvailableProcesses, 10000);  // Refresh available processes every 10 seconds
setInterval(fetchConfigs, 10000);  // Refresh configs every 10 seconds
