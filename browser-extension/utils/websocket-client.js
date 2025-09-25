/**
 * WebSocket Client for Real-time Thread Updates
 * Handles connection to mircrew-smart-indexer WebSocket endpoint
 * Implements reconnection logic, message queuing, and error handling
 */

class WebSocketClient extends EventTarget {
  /**
   * Create WebSocket client instance
   * @param {string} url - WebSocket endpoint URL
   * @param {object} options - Configuration options
   */
  constructor(url, options = {}) {
    super();

    this.url = url;
    this.options = {
      reconnectInterval: 1000, // Start with 1 second
      maxReconnectInterval: 30000, // Max 30 seconds
      maxReconnectAttempts: 10,
      heartbeatInterval: 30000, // 30 seconds
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

  /**
   * Connect to WebSocket server
   * @param {string} token - Optional authentication token
   */
  connect(token = null) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    try {
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      // Note: WebSocket doesn't support custom headers in constructor
      // Authentication should be handled via query parameters or initial message
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

  /**
   * Disconnect from WebSocket server
   */
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

  /**
   * Subscribe to thread updates
   * @param {string} threadId - Thread ID to subscribe to
   */
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

  /**
   * Unsubscribe from thread updates
   * @param {string} threadId - Thread ID to unsubscribe from
   */
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

  /**
   * Send message to server
   * @param {object} message - Message to send
   */
  sendMessage(message) {
    if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
      } catch (error) {
        console.error('Failed to send WebSocket message:', error);
        // Queue message for retry
        this.queueMessage(message);
      }
    } else {
      // Queue message if not connected
      this.queueMessage(message);
    }
  }

  /**
   * Queue message for later sending
   * @param {object} message - Message to queue
   */
  queueMessage(message) {
    if (this.messageQueue.length < this.options.messageQueueMaxSize) {
      this.messageQueue.push(message);
    } else {
      console.warn('Message queue full, dropping message:', message);
    }
  }

  /**
   * Process queued messages
   */
  processMessageQueue() {
    while (this.messageQueue.length > 0 && this.isConnected) {
      const message = this.messageQueue.shift();
      this.sendMessage(message);
    }
  }

  /**
   * Handle WebSocket open event
   */
  handleOpen() {
    console.log('WebSocket connected');
    this.isConnected = true;
    this.isReconnecting = false;
    this.reconnectAttempts = 0;

    // Reset reconnect interval
    this.options.reconnectInterval = 1000;

    // Start heartbeat
    this.startHeartbeat();

    // Subscribe to all current subscriptions
    this.subscriptions.forEach(threadId => {
      this.sendMessage({
        type: 'subscribe',
        threadId: threadId
      });
    });

    // Process queued messages
    this.processMessageQueue();

    this.dispatchEvent(new CustomEvent('connected'));
  }

  /**
   * Handle WebSocket message event
   * @param {MessageEvent} event - WebSocket message event
   */
  handleMessage(event) {
    try {
      const message = JSON.parse(event.data);

      // Handle different message types
      switch (message.type) {
        case 'thread_update':
          this.handleThreadUpdate(message);
          break;
        case 'heartbeat':
          // Reset heartbeat timeout
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

  /**
   * Handle thread update message
   * @param {object} message - Thread update message
   */
  handleThreadUpdate(message) {
    const { threadId, updates } = message;

    // Throttle updates to prevent UI overload
    this.throttleUpdate(threadId, () => {
      this.dispatchEvent(new CustomEvent('threadUpdate', {
        detail: { threadId, updates }
      }));
    });
  }

  /**
   * Throttle updates for a specific thread
   * @param {string} threadId - Thread ID
   * @param {function} callback - Update callback
   */
  throttleUpdate(threadId, callback) {
    const key = `thread_${threadId}`;

    if (this.throttleTimeouts.has(key)) {
      clearTimeout(this.throttleTimeouts.get(key));
    }

    // Throttle to 500ms intervals
    const timeout = setTimeout(() => {
      this.throttleTimeouts.delete(key);
      callback();
    }, 500);

    this.throttleTimeouts.set(key, timeout);
  }

  /**
   * Handle WebSocket close event
   * @param {CloseEvent} event - WebSocket close event
   */
  handleClose(event) {
    console.log('WebSocket closed:', event.code, event.reason);
    this.isConnected = false;
    this.clearTimeouts();

    // Attempt reconnection unless it was a clean close
    if (event.code !== 1000 && !this.isReconnecting) {
      this.attemptReconnect();
    } else {
      this.dispatchEvent(new CustomEvent('disconnected'));
    }
  }

  /**
   * Handle WebSocket error event
   * @param {Event} error - WebSocket error event
   */
  handleError(error) {
    console.error('WebSocket error:', error);

    if (!this.isReconnecting) {
      this.dispatchEvent(new CustomEvent('error', { detail: error }));
    }
  }

  /**
   * Attempt to reconnect to WebSocket server
   */
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
      this.connect();
    }, delay);

    this.dispatchEvent(new CustomEvent('reconnecting', {
      detail: { attempt: this.reconnectAttempts, delay }
    }));
  }

  /**
   * Start heartbeat timer
   */
  startHeartbeat() {
    this.heartbeatTimeout = setInterval(() => {
      if (this.isConnected) {
        this.sendMessage({ type: 'heartbeat' });
      }
    }, this.options.heartbeatInterval);
  }

  /**
   * Reset heartbeat timeout
   */
  resetHeartbeat() {
    // Heartbeat response received, clear any pending timeout
    // In a more sophisticated implementation, we could track heartbeat responses
  }

  /**
   * Clear all timeouts
   */
  clearTimeouts() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.heartbeatTimeout) {
      clearInterval(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }

    // Clear all throttle timeouts
    this.throttleTimeouts.forEach(timeout => clearTimeout(timeout));
    this.throttleTimeouts.clear();
  }

  /**
   * Get connection status
   * @returns {object} Connection status
   */
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

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = WebSocketClient;
}