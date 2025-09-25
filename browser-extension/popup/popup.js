// Popup script for Sonarr Smart Indexer Extension

document.addEventListener('DOMContentLoaded', function() {
  const statusText = document.getElementById('status-text');
  const enabledToggle = document.getElementById('enabled-toggle');
  const optionsBtn = document.getElementById('options-btn');

  // Load current settings and status
  loadSettings();
  checkStatus();

  // Event listeners
  enabledToggle.addEventListener('change', toggleEnabled);
  const notificationRadios = document.querySelectorAll('input[name="notifications"]');
  notificationRadios.forEach(radio => {
    radio.addEventListener('change', saveNotifications);
  });
  optionsBtn.addEventListener('click', openOptions);

  // Listen for storage changes
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'sync') {
      if ('enabled' in changes) {
        document.getElementById('enabled-toggle').checked = changes.enabled.newValue !== false;
      }
      if ('notifications' in changes) {
        document.querySelector(`input[name="notifications"][value="${changes.notifications.newValue}"]`).checked = true;
      }
      if ('theme' in changes) {
        applyTheme(changes.theme.newValue);
      }
    }
  });
});

/**
 * Loads extension settings from storage
 */
function loadSettings() {
  chrome.storage.sync.get(['enabled', 'notifications', 'theme'], (result) => {
    if (chrome.runtime.lastError) {
      console.error('Error loading settings:', chrome.runtime.lastError);
      return;
    }

    const enabled = result.enabled !== false; // Default to true
    document.getElementById('enabled-toggle').checked = enabled;

    const notifications = result.notifications || 'both';
    document.querySelector(`input[name="notifications"][value="${notifications}"]`).checked = true;

    const theme = result.theme || 'system';
    applyTheme(theme);
  });
}

/**
 * Checks the current extension status via background script
 */
function checkStatus() {
  chrome.runtime.sendMessage({action: 'getStatus'}, (response) => {
    if (chrome.runtime.lastError) {
      console.error('Status check failed:', chrome.runtime.lastError);
      updateStatus('Error', 'error');
      return;
    }

    if (response.success) {
      updateStatus(response.status, response.status);
    } else {
      updateStatus('Error: ' + response.error, 'error');
    }
  });
}

/**
 * Updates the status display
 * @param {string} status - Status text
 * @param {string} cssClass - CSS class for styling
 */
function updateStatus(status, cssClass = '') {
  const statusText = document.getElementById('status-text');
  statusText.textContent = status;
  statusText.className = cssClass;
}

/**
 * Handles the enabled toggle change
 */
function toggleEnabled() {
  const enabled = document.getElementById('enabled-toggle').checked;

  chrome.storage.sync.set({enabled: enabled}, () => {
    if (chrome.runtime.lastError) {
      console.error('Error saving enabled setting:', chrome.runtime.lastError);
      // Revert the toggle if save failed
      document.getElementById('enabled-toggle').checked = !enabled;
    }
  });
}

/**
 * Saves notification preference to storage
 */
function saveNotifications() {
  const selected = document.querySelector('input[name="notifications"]:checked').value;

  chrome.storage.sync.set({notifications: selected}, () => {
    if (chrome.runtime.lastError) {
      console.error('Error saving notifications:', chrome.runtime.lastError);
    }
  });
}

/**
 * Opens the extension options page
 */
function openOptions() {
  chrome.runtime.openOptionsPage();
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