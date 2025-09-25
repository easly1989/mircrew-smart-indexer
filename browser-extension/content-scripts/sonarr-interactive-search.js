// Content script for enhancing Sonarr's Interactive Search with smart indexing
// Detects the Interactive Search interface and injects UI components

let injected = false;
let treeView = null;

/**
 * Checks if the current page contains Sonarr's Interactive Search interface
 * @returns {boolean} True if Interactive Search elements are detected
 */
function detectInteractiveSearch() {
  // Look for common Sonarr Interactive Search elements
  // This may need adjustment based on actual Sonarr DOM structure
  const indicators = [
    '.interactive-search',
    '[data-testid="interactive-search"]',
    'form[action*="search"] input[type="text"]',
    '.search-results table'
  ];

  return indicators.some(selector => document.querySelector(selector));
}

/**
 * Injects the smart indexer UI components into the page
 */
function injectUI() {
  if (injected || !detectInteractiveSearch()) {
    return;
  }

  try {
    // Load TreeView script
    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('content-scripts/tree-view.js');
    script.onload = () => {
      console.log('TreeView script loaded');
    };
    document.head.appendChild(script);

    // Create main UI container
    const container = document.createElement('div');
    container.id = 'sonarr-smart-indexer-ui';
    container.style.cssText = `
      position: fixed;
      top: 10px;
      right: 10px;
      width: 400px;
      height: 600px;
      background: #f8f9fa;
      border: 1px solid #dee2e6;
      border-radius: 4px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      z-index: 10000;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      display: flex;
      flex-direction: column;
    `;

    container.innerHTML = `
      <div style="
        padding: 8px 12px;
        border-bottom: 1px solid #dee2e6;
        background: #e9ecef;
        font-weight: bold;
        border-radius: 4px 4px 0 0;
      ">Smart Indexer Tree View</div>
      <div id="tree-view-container" style="
        flex: 1;
        overflow: hidden;
      "></div>
      <div style="
        padding: 8px 12px;
        border-top: 1px solid #dee2e6;
        background: #f8f9fa;
        font-size: 12px;
      ">
        <button id="smart-search-btn" style="
          background: #007bff;
          color: white;
          border: none;
          padding: 6px 12px;
          border-radius: 3px;
          cursor: pointer;
          margin-right: 8px;
        ">Smart Search</button>
        <button id="expand-all-btn" style="
          background: #28a745;
          color: white;
          border: none;
          padding: 6px 12px;
          border-radius: 3px;
          cursor: pointer;
          margin-right: 8px;
        ">Expand All</button>
        <button id="collapse-all-btn" style="
          background: #6c757d;
          color: white;
          border: none;
          padding: 6px 12px;
          border-radius: 3px;
          cursor: pointer;
        ">Collapse All</button>
        <div id="smart-status" style="margin-top: 8px; color: #6c757d;"></div>
      </div>
    `;

    document.body.appendChild(container);

    // Initialize TreeView after script loads
    script.onload = () => {
      const treeContainer = document.getElementById('tree-view-container');
      treeView = new TreeView(treeContainer);
      console.log('TreeView initialized');
    };

    // Add event listeners
    const searchBtn = document.getElementById('smart-search-btn');
    const expandAllBtn = document.getElementById('expand-all-btn');
    const collapseAllBtn = document.getElementById('collapse-all-btn');
    const statusDiv = document.getElementById('smart-status');

    searchBtn.addEventListener('click', handleSmartSearch);
    expandAllBtn.addEventListener('click', () => treeView && treeView.expandAll());
    collapseAllBtn.addEventListener('click', () => treeView && treeView.collapseAll());

    updateStatus();

    // Set up observer for Sonarr's result updates
    setupResultObserver();

    injected = true;
    console.log('Smart Indexer UI injected successfully');
  } catch (error) {
    console.error('Failed to inject Smart Indexer UI:', error);
  }
}

/**
 * Sets up a MutationObserver to watch for Sonarr's search result updates
 */
function setupResultObserver() {
  const resultsTable = document.querySelector('.search-results tbody, .results tbody, table tbody');

  if (!resultsTable) {
    console.warn('Could not find Sonarr results table to observe');
    return;
  }

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
        // New results added to Sonarr's table
        const newResults = Array.from(mutation.addedNodes)
          .filter(node => node.tagName === 'TR' && !node.hasAttribute('data-smart-indexer'))
          .map(row => extractResultFromRow(row));

        if (newResults.length > 0 && treeView) {
          // Optionally add new Sonarr results to tree view
          console.log(`Detected ${newResults.length} new Sonarr results`);
          // For now, just log. Could enhance to add to tree view if needed
        }
      }
    });
  });

  observer.observe(resultsTable, {
    childList: true,
    subtree: false
  });

  console.log('Result observer set up');
}

/**
 * Extract result data from a Sonarr result table row
 * @param {HTMLElement} row - Table row element
 * @returns {object} Extracted result data
 */
function extractResultFromRow(row) {
  const cells = row.querySelectorAll('td');
  if (cells.length < 4) return null;

  return {
    title: cells[0]?.textContent?.trim() || '',
    size: cells[1]?.textContent?.trim() || '',
    seeders: cells[2]?.textContent?.trim() || '',
    link: cells[3]?.querySelector('a, button')?.href || ''
  };
}

/**
 * Handles the smart search button click
 */
async function handleSmartSearch() {
  try {
    // Get current search query from Sonarr's search input
    const queryInput = document.querySelector('input[name="query"], input[placeholder*="search" i]');
    const query = queryInput ? queryInput.value.trim() : '';

    if (!query) {
      alert('Please enter a search query first');
      return;
    }

    // Check extension status
    chrome.runtime.sendMessage({action: 'getStatus'}, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Status check failed:', chrome.runtime.lastError);
        updateStatus('Error checking status');
        return;
      }

      if (!response.success || response.status !== 'authenticated') {
        alert('Please authenticate in the extension options first');
        return;
      }

      // Perform smart search
      updateStatus('Searching...');
      chrome.runtime.sendMessage({action: 'search', data: {query}}, (searchResponse) => {
        if (chrome.runtime.lastError) {
          console.error('Search failed:', chrome.runtime.lastError);
          updateStatus('Search failed');
          return;
        }

        if (searchResponse.success) {
          displayResults(searchResponse.data);
          updateStatus('Search completed');
        } else {
          updateStatus('Search failed: ' + searchResponse.error);
        }
      });
    });
  } catch (error) {
    console.error('Smart search error:', error);
    updateStatus('Error occurred');
  }
}

/**
 * Displays search results in the tree view
 * @param {Array} results - Search results from the API
 */
function displayResults(results) {
  try {
    if (!treeView) {
      console.warn('TreeView not initialized yet');
      return;
    }

    if (Array.isArray(results)) {
      // Set data in tree view
      treeView.setData(results);
      updateStatus(`Found ${results.length} results in ${getUniqueThreads(results)} threads`);
      console.log(`Displayed ${results.length} smart search results in tree view`);
    } else {
      console.warn('Invalid results format');
      updateStatus('Invalid results format');
    }
  } catch (error) {
    console.error('Error displaying results:', error);
    updateStatus('Error displaying results');
  }
}

/**
 * Count unique threads in results
 * @param {Array} results - Search results
 * @returns {number} Number of unique threads
 */
function getUniqueThreads(results) {
  const threadIds = new Set();
  results.forEach(result => {
    const threadId = result.thread_id || result.threadId || 'unknown';
    threadIds.add(threadId);
  });
  return threadIds.size;
}

/**
 * Updates the status display in the UI
 * @param {string} status - Status message to display
 */
function updateStatus(status = '') {
  const statusDiv = document.getElementById('smart-status');
  if (statusDiv) {
    statusDiv.textContent = status;
  }
}

// Set up DOM observer to detect when Interactive Search loads
const observer = new MutationObserver((mutations) => {
  mutations.forEach(() => {
    injectUI();
  });
});

// Start observing after DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
    injectUI();
  });
} else {
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
  injectUI();
}