// Background service worker for Sonarr Smart Indexer Extension
// Handles message passing between content scripts and API communication

const API_BASE = 'http://localhost:9898/api/v1';
const WS_BASE = 'ws://localhost:9898/api/v1/updates';

// WebSocket client instance for real-time updates
let wsClient = null;
let messageQueue = [];
let updateThrottleTimeouts = new Map();
let subscribedThreads = new Set();

/**
 * WebSocket Client for Real-time Thread Updates (inline definition for service worker)
 */
class WebSocketClient extends EventTarget {
  constructor(url, options = {}) {
    super();

    this.url = url;
    this.options = {
      reconnectInterval: 1000,
      maxReconnectInterval: 30000,
      maxReconnectAttempts: 10,
      heartbeatInterval: 30000,
      messageQueueMaxSize: 100,
      ...options
    };

    this.ws = null;
    this.reconnectAttempts = 0;
    this.reconnectTimeout = null;
    this.heartbeatTimeout = null;
    this.messageQueue = [];
    this.isConnected = false;
    this.isReconnecting = false;
    this.subscriptions = new Set();
    this.throttleTimeouts = new Map();
  }

  connect(token = null) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const authParam = token ? `?token=${encodeURIComponent(token)}` : '';
      this.ws = new WebSocket(`${this.url}${authParam}`);

      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
      this.ws.onerror = this.handleError.bind(this);

      this.dispatchEvent(new CustomEvent('connecting'));
    } catch (error) {
      console.error('WebSocket connection error:', error);
      this.handleError(error);
    }
  }

  disconnect() {
    this.clearTimeouts();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.messageQueue = [];
    this.subscriptions.clear();
    this.throttleTimeouts.clear();

    this.dispatchEvent(new CustomEvent('disconnected'));
  }

  subscribe(threadId) {
    if (!this.subscriptions.has(threadId)) {
      this.subscriptions.add(threadId);

      if (this.isConnected) {
        this.sendMessage({
          type: 'subscribe',
          threadId: threadId
        });
      }
    }
  }

  unsubscribe(threadId) {
    if (this.subscriptions.has(threadId)) {
      this.subscriptions.delete(threadId);

      if (this.isConnected) {
        this.sendMessage({
          type: 'unsubscribe',
          threadId: threadId
        });
      }
    }
  }

  sendMessage(message) {
    if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
      } catch (error) {
        console.error('Failed to send WebSocket message:', error);
        this.queueMessage(message);
      }
    } else {
      this.queueMessage(message);
    }
  }

  queueMessage(message) {
    if (this.messageQueue.length < this.options.messageQueueMaxSize) {
      this.messageQueue.push(message);
    } else {
      console.warn('Message queue full, dropping message:', message);
    }
  }

  processMessageQueue() {
    while (this.messageQueue.length > 0 && this.isConnected) {
      const message = this.messageQueue.shift();
      this.sendMessage(message);
    }
  }

  handleOpen() {
    console.log('WebSocket connected');
    this.isConnected = true;
    this.isReconnecting = false;
    this.reconnectAttempts = 0;
    this.options.reconnectInterval = 1000;

    this.startHeartbeat();
    this.subscriptions.forEach(threadId => {
      this.sendMessage({
        type: 'subscribe',
        threadId: threadId
      });
    });
    this.processMessageQueue();
    this.dispatchEvent(new CustomEvent('connected'));
  }

  handleMessage(event) {
    try {
      const message = JSON.parse(event.data);
      switch (message.type) {
        case 'thread_update':
          this.handleThreadUpdate(message);
          break;
        case 'heartbeat':
          this.resetHeartbeat();
          break;
        case 'error':
          console.error('WebSocket server error:', message.error);
          this.dispatchEvent(new CustomEvent('error', { detail: message.error }));
          break;
        default:
          console.log('Unknown message type:', message.type);
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  handleThreadUpdate(message) {
    const { threadId, updates } = message;
    this.throttleUpdate(threadId, () => {
      this.dispatchEvent(new CustomEvent('threadUpdate', {
        detail: { threadId, updates }
      }));
    });
  }

  throttleUpdate(threadId, callback) {
    const key = `thread_${threadId}`;
    if (this.throttleTimeouts.has(key)) {
      clearTimeout(this.throttleTimeouts.get(key));
    }
    const timeout = setTimeout(() => {
      this.throttleTimeouts.delete(key);
      callback();
    }, 500);
    this.throttleTimeouts.set(key, timeout);
  }

  handleClose(event) {
    console.log('WebSocket closed:', event.code, event.reason);
    this.isConnected = false;
    this.clearTimeouts();

    if (event.code !== 1000 && !this.isReconnecting) {
      this.attemptReconnect();
    } else {
      this.dispatchEvent(new CustomEvent('disconnected'));
    }
  }

  handleError(error) {
    console.error('WebSocket error:', error);
    if (!this.isReconnecting) {
      this.dispatchEvent(new CustomEvent('error', { detail: error }));
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.dispatchEvent(new CustomEvent('maxReconnectAttemptsReached'));
      return;
    }

    this.isReconnecting = true;
    this.reconnectAttempts++;
    const delay = Math.min(
      this.options.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1),
      this.options.maxReconnectInterval
    );

    console.log(`Attempting reconnection ${this.reconnectAttempts}/${this.options.maxReconnectAttempts} in ${delay}ms`);

    this.reconnectTimeout = setTimeout(() => {
      // Reconnect with same token
      this.connect();
    }, delay);

    this.dispatchEvent(new CustomEvent('reconnecting', {
      detail: { attempt: this.reconnectAttempts, delay }
    }));
  }

  startHeartbeat() {
    this.heartbeatTimeout = setInterval(() => {
      if (this.isConnected) {
        this.sendMessage({ type: 'heartbeat' });
      }
    }, this.options.heartbeatInterval);
  }

  resetHeartbeat() {
    // Heartbeat response received
  }

  clearTimeouts() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.heartbeatTimeout) {
      clearInterval(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
    this.throttleTimeouts.forEach(timeout => clearTimeout(timeout));
    this.throttleTimeouts.clear();
  }

  getStatus() {
    return {
      isConnected: this.isConnected,
      isReconnecting: this.isReconnecting,
      reconnectAttempts: this.reconnectAttempts,
      subscriptions: Array.from(this.subscriptions),
      queueSize: this.messageQueue.length
    };
  }
}

/**
 * Retrieves the API authentication token from storage
 * @returns {Promise<string|null>} The stored API token or null if not found
 */
async function getApiToken() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(['apiToken'], (result) => {
      resolve(result.apiToken || null);
    });
  });
}

/**
 * Stores the API authentication token in storage
 * @param {string} token - The API token to store
 * @returns {Promise<void>}
 */
async function setApiToken(token) {
  return new Promise((resolve) => {
    chrome.storage.sync.set({apiToken: token}, resolve);
  });
}

/**
 * Retrieves the CSRF token from storage or fetches a new one
 * @returns {Promise<string|null>} The CSRF token or null if failed
 */
async function getCsrfToken() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['csrfToken', 'csrfExpiry'], (result) => {
      const now = Date.now();
      // Check if token exists and hasn't expired (1 hour TTL)
      if (result.csrfToken && result.csrfExpiry && now < result.csrfExpiry) {
        resolve(result.csrfToken);
      } else {
        // Fetch new token
        fetchCsrfToken().then(resolve).catch(() => resolve(null));
      }
    });
  });
}

/**
 * Fetches a new CSRF token from the API
 * @returns {Promise<string|null>} The new CSRF token
 */
async function fetchCsrfToken() {
  try {
    const response = await fetch(`${API_BASE}/csrf-token`);
    if (!response.ok) {
      throw new Error(`CSRF token fetch failed: ${response.status}`);
    }
    const data = await response.json();
    const token = data.token;
    const expiry = Date.now() + (60 * 60 * 1000); // 1 hour from now

    // Store token in local storage
    await new Promise((resolve) => {
      chrome.storage.local.set({
        csrfToken: token,
        csrfExpiry: expiry
      }, resolve);
    });

    return token;
  } catch (error) {
    console.error('Failed to fetch CSRF token:', error);
    return null;
  }
}

/**
 * Makes an authenticated API call to the mircrew-smart-indexer
 * @param {string} endpoint - API endpoint (e.g., '/search')
 * @param {object} options - Fetch options (method, body, etc.)
 * @returns {Promise<object>} API response data
 * @throws {Error} If the API call fails
 */
async function callApi(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const token = await getApiToken();

  const defaultHeaders = {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  };

  // Merge default headers with any custom headers from options
  const headers = { ...defaultHeaders, ...(options.headers || {}) };

  try {
    const response = await fetch(url, {
      ...options,
      headers
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      return await response.json();
    }

    return await response.text();
  } catch (error) {
    console.error(`API call to ${endpoint} failed:`, error);
    throw error;
  }
}

/**
 * Shows a notification to the user
 * @param {string} title - Notification title
 * @param {string} message - Notification message
 */
function showNotification(title, message) {
  chrome.notifications.create('', {
    type: 'basic',
    iconUrl: 'icons/icon48.png',
    title: title,
    message: message
  });
}

/**
 * Initialize WebSocket connection for real-time updates
 */
async function initializeWebSocket() {
  if (wsClient) {
    return; // Already initialized
  }

  const token = await getApiToken();
  if (!token) {
    console.log('No API token available, WebSocket not initialized');
    return;
  }

  wsClient = new WebSocketClient(WS_BASE, {
    reconnectInterval: 1000,
    maxReconnectInterval: 30000,
    maxReconnectAttempts: 10,
    heartbeatInterval: 30000
  });

  // Set up event listeners
  wsClient.addEventListener('connected', () => {
    console.log('WebSocket connected, subscribing to threads');
    // Resubscribe to all threads
    subscribedThreads.forEach(threadId => {
      wsClient.subscribe(threadId);
    });
  });

  wsClient.addEventListener('disconnected', () => {
    console.log('WebSocket disconnected');
  });

  wsClient.addEventListener('threadUpdate', (event) => {
    const { threadId, updates } = event.detail;
    handleThreadUpdate(threadId, updates);
  });

  wsClient.addEventListener('error', (event) => {
    console.error('WebSocket error:', event.detail);
  });

  wsClient.addEventListener('maxReconnectAttemptsReached', () => {
    console.error('Max WebSocket reconnection attempts reached, falling back to polling');
    // Could implement polling fallback here
  });

  // Connect with authentication
  wsClient.connect(token);
}

/**
 * Subscribe to updates for a specific thread
 * @param {string} threadId - Thread ID to subscribe to
 */
function subscribeToThread(threadId) {
  if (!subscribedThreads.has(threadId)) {
    subscribedThreads.add(threadId);

    if (wsClient && wsClient.isConnected) {
      wsClient.subscribe(threadId);
    } else {
      // Initialize WebSocket if not already done
      initializeWebSocket();
    }
  }
}

/**
 * Unsubscribe from updates for a specific thread
 * @param {string} threadId - Thread ID to unsubscribe from
 */
function unsubscribeFromThread(threadId) {
  if (subscribedThreads.has(threadId)) {
    subscribedThreads.delete(threadId);

    if (wsClient && wsClient.isConnected) {
      wsClient.unsubscribe(threadId);
    }
  }
}

/**
 * Handle incoming thread update from WebSocket
 * @param {string} threadId - Thread ID that was updated
 * @param {object} updates - Update data
 */
function handleThreadUpdate(threadId, updates) {
  console.log('Received thread update:', threadId, updates);

  // Throttle updates to prevent overwhelming the UI
  throttleUpdate(threadId, () => {
    // Notify all content scripts about the update
    chrome.tabs.query({}, (tabs) => {
      tabs.forEach(tab => {
        if (tab.url && tab.url.includes('localhost:8989')) {
          chrome.tabs.sendMessage(tab.id, {
            action: 'threadUpdate',
            threadId: threadId,
            updates: updates
          }).catch(error => {
            // Tab might not have content script or be ready
            console.debug('Failed to send update to tab:', tab.id, error);
          });
        }
      });
    });

    // Show browser notification for new releases
    if (updates.newReleases && updates.newReleases.length > 0) {
      showNotification(
        'New Releases Available',
        `Thread "${updates.title || threadId}" has ${updates.newReleases.length} new release(s)`
      );
    }

    // Store update timestamp for "mark as read" functionality
    const updateKey = `thread_update_${threadId}`;
    chrome.storage.local.set({
      [updateKey]: {
        timestamp: Date.now(),
        updates: updates
      }
    });
  });
}

/**
 * Throttle updates to prevent UI overload
 * @param {string} threadId - Thread ID
 * @param {function} callback - Update callback
 */
function throttleUpdate(threadId, callback) {
  const key = `update_${threadId}`;

  if (updateThrottleTimeouts.has(key)) {
    clearTimeout(updateThrottleTimeouts.get(key));
  }

  // Throttle to 1 second intervals per thread
  const timeout = setTimeout(() => {
    updateThrottleTimeouts.delete(key);
    callback();
  }, 1000);

  updateThrottleTimeouts.set(key, timeout);
}

/**
 * Queue message for processing
 * @param {object} message - Message to queue
 */
function queueMessage(message) {
  if (messageQueue.length < 100) { // Max queue size
    messageQueue.push(message);
  } else {
    console.warn('Message queue full, dropping message');
  }
}

/**
 * Process queued messages
 */
function processMessageQueue() {
  while (messageQueue.length > 0) {
    const message = messageQueue.shift();
    // Process message based on type
    switch (message.type) {
      case 'subscribe':
        subscribeToThread(message.threadId);
        break;
      case 'unsubscribe':
        unsubscribeFromThread(message.threadId);
        break;
      default:
        console.log('Unknown queued message type:', message.type);
    }
  }
}

// Message listener for communication with content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  (async () => {
    try {
      switch (request.action) {
        case 'authenticate':
           // Set the API token
           await setApiToken(request.token);
           // Initialize WebSocket connection after authentication
           initializeWebSocket();
           sendResponse({ success: true });
           break;

        case 'search':
          // Perform search via API
          const searchResults = await callApi('/search', {
            method: 'POST',
            body: JSON.stringify(request.data)
          });
          sendResponse({ success: true, data: searchResults });
          break;

        case 'getStatus':
          // Check API connectivity and auth status
          const token = await getApiToken();
          let apiStatus = 'disconnected';
          try {
            await callApi('/status');
            apiStatus = token ? 'authenticated' : 'connected';
          } catch (error) {
            apiStatus = 'error';
          }
          sendResponse({ success: true, status: apiStatus });
          break;

        case 'likeThread':
          // Like/unlike a thread
          try {
            const csrfToken = await getCsrfToken();
            if (!csrfToken) {
              throw new Error('Failed to obtain CSRF token');
            }

            const likeResult = await callApi(`/thread/${request.threadId}/like`, {
              method: 'POST',
              headers: {
                'X-CSRF-Token': csrfToken
              },
              body: JSON.stringify({
                action: request.action || 'like' // Default to 'like' if not specified
              })
            });

            sendResponse({ success: true, ...likeResult });
          } catch (error) {
            console.error('Like thread error:', error);
            sendResponse({ success: false, error: error.message });
          }
          break;

        case 'refreshThread':
          // Refresh thread data after like
          try {
            const csrfToken = await getCsrfToken();
            if (!csrfToken) {
              throw new Error('Failed to obtain CSRF token');
            }

            const refreshResult = await callApi(`/search/refresh/${request.threadId}`, {
              method: 'POST',
              headers: {
                'X-CSRF-Token': csrfToken
              }
            });

            sendResponse({ success: true, ...refreshResult });
          } catch (error) {
            console.error('Refresh thread error:', error);
            sendResponse({ success: false, error: error.message });
          }
          break;

        case 'trackAnalytics':
           // Track analytics events
           try {
             console.log('Analytics event:', request.event, request.data);
             // Here you could send to external analytics service
             // For now, just log and store locally for debugging
             chrome.storage.local.get(['analytics'], (result) => {
               const analytics = result.analytics || [];
               analytics.push({
                 event: request.event,
                 data: request.data,
                 timestamp: Date.now()
               });

               // Keep only last 100 events
               if (analytics.length > 100) {
                 analytics.splice(0, analytics.length - 100);
               }

               chrome.storage.local.set({ analytics });
             });

             sendResponse({ success: true });
           } catch (error) {
             console.error('Analytics tracking error:', error);
             sendResponse({ success: false, error: error.message });
           }
           break;

        case 'subscribeThread':
           // Subscribe to real-time updates for a thread
           try {
             subscribeToThread(request.threadId);
             sendResponse({ success: true });
           } catch (error) {
             console.error('Thread subscription error:', error);
             sendResponse({ success: false, error: error.message });
           }
           break;

        case 'unsubscribeThread':
           // Unsubscribe from real-time updates for a thread
           try {
             unsubscribeFromThread(request.threadId);
             sendResponse({ success: true });
           } catch (error) {
             console.error('Thread unsubscription error:', error);
             sendResponse({ success: false, error: error.message });
           }
           break;

        case 'getWebSocketStatus':
           // Get WebSocket connection status
           try {
             const status = wsClient ? wsClient.getStatus() : { isConnected: false };
             sendResponse({ success: true, status: status });
           } catch (error) {
             console.error('WebSocket status error:', error);
             sendResponse({ success: false, error: error.message });
           }
           break;

        case 'markThreadAsRead':
           // Mark thread updates as read
           try {
             const updateKey = `thread_update_${request.threadId}`;
             chrome.storage.local.remove([updateKey], () => {
               sendResponse({ success: true });
             });
           } catch (error) {
             console.error('Mark as read error:', error);
             sendResponse({ success: false, error: error.message });
           }
           break;

        case 'getUnreadUpdates':
           // Get list of threads with unread updates
           try {
             chrome.storage.local.get(null, (result) => {
               const unreadUpdates = {};
               Object.keys(result).forEach(key => {
                 if (key.startsWith('thread_update_')) {
                   const threadId = key.replace('thread_update_', '');
                   unreadUpdates[threadId] = result[key];
                 }
               });
               sendResponse({ success: true, updates: unreadUpdates });
             });
           } catch (error) {
             console.error('Get unread updates error:', error);
             sendResponse({ success: false, error: error.message });
           }
           break;

        default:
          sendResponse({ success: false, error: 'Unknown action' });
      }
    } catch (error) {
      console.error('Message handling error:', error);
      showNotification('Extension Error', error.message);
      sendResponse({ success: false, error: error.message });
    }
  })();

  // Return true to indicate asynchronous response
  return true;
});

// Handle extension installation
chrome.runtime.onInstalled.addListener(async () => {
  console.log('Sonarr Smart Indexer Extension installed');

  // Check if we have an existing token and initialize WebSocket
  const token = await getApiToken();
  if (token) {
    initializeWebSocket();
  }
});