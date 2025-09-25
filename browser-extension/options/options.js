// Options page script for Sonarr Smart Indexer Extension

document.addEventListener('DOMContentLoaded', function() {
  // Migrate settings from localStorage if any
  migrateSettings();

  // Load current settings
  loadAllSettings();
  updateExtensionStatus();

  // Listen for storage changes
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'sync') {
      updateUIFromChanges(changes);
    }
  });

  // Event listeners
  document.getElementById('save-token').addEventListener('click', saveToken);
  document.getElementById('save-urls').addEventListener('click', saveUrls);
  document.getElementById('save-threshold').addEventListener('click', saveThreshold);
  document.getElementById('save-theme').addEventListener('click', saveTheme);
  document.getElementById('export-settings').addEventListener('click', exportSettings);
  document.getElementById('import-settings').addEventListener('click', importSettings);
  document.getElementById('test-connection').addEventListener('click', testConnection);
});

/**
 * Loads all settings from storage and displays them
 */
function loadAllSettings() {
  chrome.storage.sync.get(['apiToken', 'sonarrUrl', 'indexerUrl', 'notificationThreshold', 'theme'], (result) => {
    if (chrome.runtime.lastError) {
      console.error('Error loading settings:', chrome.runtime.lastError);
      return;
    }

    document.getElementById('api-token').value = result.apiToken || '';
    document.getElementById('sonarr-url').value = result.sonarrUrl || '';
    document.getElementById('indexer-url').value = result.indexerUrl || '';
    document.getElementById('notification-threshold').value = result.notificationThreshold || 10;
    document.getElementById('theme').value = result.theme || 'system';
  });
}

/**
 * Saves the API token to storage and authenticates with the background script
 */
function saveToken() {
  const tokenInput = document.getElementById('api-token');
  const token = tokenInput.value.trim();

  if (!token) {
    showStatus('token-status', 'Please enter a valid API token', 'error');
    return;
  }

  // Save to storage
  chrome.storage.sync.set({apiToken: token}, () => {
    if (chrome.runtime.lastError) {
      console.error('Error saving token:', chrome.runtime.lastError);
      showStatus('token-status', 'Error saving token to storage', 'error');
      return;
    }

    // Authenticate with background script
    chrome.runtime.sendMessage({action: 'authenticate', token: token}, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Authentication failed:', chrome.runtime.lastError);
        showStatus('token-status', 'Authentication failed', 'error');
        return;
      }

      if (response.success) {
        showStatus('token-status', 'Token saved and authenticated successfully', 'success');
        updateExtensionStatus();
      } else {
        showStatus('token-status', 'Authentication failed: ' + response.error, 'error');
      }
    });
  });
}

/**
 * Tests the connection to the mircrew-smart-indexer API
 */
function testConnection() {
  const testButton = document.getElementById('test-connection');
  const originalText = testButton.textContent;
  testButton.textContent = 'Testing...';
  testButton.disabled = true;

  chrome.runtime.sendMessage({action: 'getStatus'}, (response) => {
    testButton.textContent = originalText;
    testButton.disabled = false;

    if (chrome.runtime.lastError) {
      console.error('Connection test failed:', chrome.runtime.lastError);
      updateExtensionStatus('Error testing connection');
      return;
    }

    updateExtensionStatus(response.success ? response.status : 'Error: ' + response.error);
  });
}

/**
 * Updates the extension status display
 * @param {string} status - Optional status text override
 */
function updateExtensionStatus(status = null) {
  const statusDiv = document.getElementById('extension-status');

  if (status) {
    statusDiv.textContent = status;
    return;
  }

  statusDiv.textContent = 'Checking...';
  chrome.runtime.sendMessage({action: 'getStatus'}, (response) => {
    if (chrome.runtime.lastError) {
      statusDiv.textContent = 'Error checking status';
      return;
    }

    statusDiv.textContent = response.success ? `Status: ${response.status}` : 'Error: ' + response.error;
  });
}

/**
 * Shows a status message for operations
 * @param {string} statusId - ID of the status div
 * @param {string} message - Status message
 * @param {string} type - Message type ('success' or 'error')
 */
function showStatus(statusId, message, type) {
  const statusDiv = document.getElementById(statusId);
  statusDiv.textContent = message;
  statusDiv.className = `status-message status-${type}`;

  // Clear the message after 5 seconds
  setTimeout(() => {
    statusDiv.textContent = '';
    statusDiv.className = 'status-message';
  }, 5000);
}

/**
 * Saves server URLs to storage with validation
 */
function saveUrls() {
  const sonarrUrl = document.getElementById('sonarr-url').value.trim();
  const indexerUrl = document.getElementById('indexer-url').value.trim();

  if (!isValidUrl(sonarrUrl) || !isValidUrl(indexerUrl)) {
    showStatus('urls-status', 'Please enter valid URLs', 'error');
    return;
  }

  chrome.storage.sync.set({sonarrUrl: sonarrUrl, indexerUrl: indexerUrl}, () => {
    if (chrome.runtime.lastError) {
      showStatus('urls-status', 'Error saving URLs', 'error');
    } else {
      showStatus('urls-status', 'URLs saved successfully', 'success');
    }
  });
}

/**
 * Saves notification threshold to storage with validation
 */
function saveThreshold() {
  const threshold = parseInt(document.getElementById('notification-threshold').value);
  if (isNaN(threshold) || threshold <= 0) {
    showStatus('threshold-status', 'Please enter a positive number', 'error');
    return;
  }

  chrome.storage.sync.set({notificationThreshold: threshold}, () => {
    if (chrome.runtime.lastError) {
      showStatus('threshold-status', 'Error saving threshold', 'error');
    } else {
      showStatus('threshold-status', 'Threshold saved successfully', 'success');
    }
  });
}

/**
 * Saves theme preference to storage
 */
function saveTheme() {
  const theme = document.getElementById('theme').value;
  chrome.storage.sync.set({theme: theme}, () => {
    if (chrome.runtime.lastError) {
      showStatus('theme-status', 'Error saving theme', 'error');
    } else {
      showStatus('theme-status', 'Theme saved successfully', 'success');
      applyTheme(theme);
    }
  });
}

/**
 * Exports all settings to a JSON file
 */
function exportSettings() {
  chrome.storage.sync.get(null, (result) => {
    if (chrome.runtime.lastError) {
      showStatus('settings-status', 'Error exporting settings', 'error');
      return;
    }
    const dataStr = JSON.stringify(result, null, 2);
    const blob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sonarr-smart-indexer-settings.json';
    a.click();
    URL.revokeObjectURL(url);
    showStatus('settings-status', 'Settings exported', 'success');
  });
}

/**
 * Imports settings from JSON input
 */
function importSettings() {
  const json = prompt('Paste your settings JSON here:');
  if (!json) return;
  try {
    const settings = JSON.parse(json);
    chrome.storage.sync.set(settings, () => {
      if (chrome.runtime.lastError) {
        showStatus('settings-status', 'Error importing settings', 'error');
      } else {
        showStatus('settings-status', 'Settings imported successfully', 'success');
        loadAllSettings();
      }
    });
  } catch (e) {
    showStatus('settings-status', 'Invalid JSON', 'error');
  }
}

/**
 * Checks if a string is a valid URL
 * @param {string} string - The string to validate
 * @returns {boolean} True if valid URL
 */
function isValidUrl(string) {
  try {
    new URL(string);
    return true;
  } catch (_) {
    return false;
  }
}

/**
 * Migrates settings from localStorage to chrome.storage.sync
 */
function migrateSettings() {
  const oldSettings = {};
  const keys = ['apiToken', 'sonarrUrl', 'indexerUrl', 'notificationThreshold', 'theme', 'enabled', 'notifications'];

  keys.forEach(key => {
    const value = localStorage.getItem(key);
    if (value !== null) {
      try {
        oldSettings[key] = JSON.parse(value);
      } catch (e) {
        oldSettings[key] = value;
      }
    }
  });

  if (Object.keys(oldSettings).length > 0) {
    chrome.storage.sync.set(oldSettings, () => {
      if (!chrome.runtime.lastError) {
        keys.forEach(key => localStorage.removeItem(key));
        console.log('Settings migrated from localStorage to sync');
      }
    });
  }
}

/**
 * Updates UI elements when storage changes
 * @param {object} changes - The changes object from chrome.storage.onChanged
 */
function updateUIFromChanges(changes) {
  if ('apiToken' in changes) {
    document.getElementById('api-token').value = changes.apiToken.newValue || '';
  }
  if ('sonarrUrl' in changes) {
    document.getElementById('sonarr-url').value = changes.sonarrUrl.newValue || '';
  }
  if ('indexerUrl' in changes) {
    document.getElementById('indexer-url').value = changes.indexerUrl.newValue || '';
  }
  if ('notificationThreshold' in changes) {
    document.getElementById('notification-threshold').value = changes.notificationThreshold.newValue || 10;
  }
  if ('theme' in changes) {
    document.getElementById('theme').value = changes.theme.newValue || 'system';
    applyTheme(changes.theme.newValue);
  }
}

/**
 * Applies the selected theme
 * @param {string} theme - The theme to apply ('light', 'dark', 'system')
 */
function applyTheme(theme) {
  const body = document.body;
  if (theme === 'dark') {
    body.classList.add('dark');
  } else if (theme === 'light') {
    body.classList.remove('dark');
  } else if (theme === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (prefersDark) {
      body.classList.add('dark');
    } else {
      body.classList.remove('dark');
    }
  }
}