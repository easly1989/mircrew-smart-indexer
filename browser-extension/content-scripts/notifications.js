/**
 * Notification System for Real-time Thread Updates
 * Handles in-UI notifications, badges, and mark-as-read functionality
 */

class NotificationSystem {
  /**
   * Create notification system instance
   * @param {HTMLElement} container - Container element for notifications
   */
  constructor(container) {
    this.container = container;
    this.notifications = new Map(); // threadId -> notification data
    this.unreadCount = 0;
    this.maxNotifications = 10;

    this.init();
  }

  /**
   * Initialize the notification system
   */
  init() {
    // Create notification UI
    this.createNotificationUI();

    // Load existing unread updates
    this.loadUnreadUpdates();

    // Listen for thread updates
    this.initMessageListeners();
  }

  /**
   * Create notification UI elements
   */
  createNotificationUI() {
    // Create notification panel
    this.panel = document.createElement('div');
    this.panel.className = 'notification-panel';
    this.panel.setAttribute('role', 'region');
    this.panel.setAttribute('aria-label', 'Thread update notifications');

    // Create notification badge for unread count
    this.badge = document.createElement('div');
    this.badge.className = 'notification-badge hidden';
    this.badge.setAttribute('aria-label', 'Unread notifications');

    // Create panel header
    const header = document.createElement('div');
    header.className = 'notification-header';

    const title = document.createElement('h3');
    title.textContent = 'Thread Updates';
    title.className = 'notification-title';

    const clearAllBtn = document.createElement('button');
    clearAllBtn.className = 'clear-all-btn';
    clearAllBtn.textContent = 'Mark All Read';
    clearAllBtn.addEventListener('click', () => this.markAllAsRead());

    header.appendChild(title);
    header.appendChild(clearAllBtn);

    // Create notification list
    this.list = document.createElement('div');
    this.list.className = 'notification-list';

    // Assemble panel
    this.panel.appendChild(header);
    this.panel.appendChild(this.list);

    // Add to container
    this.container.appendChild(this.badge);
    this.container.appendChild(this.panel);

    // Add CSS
    this.injectCSS();
  }

  /**
   * Inject CSS styles for notifications
   */
  injectCSS() {
    const style = document.createElement('style');
    style.textContent = `
      .notification-panel {
        position: fixed;
        top: 20px;
        right: 20px;
        width: 350px;
        max-height: 500px;
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        display: none;
        flex-direction: column;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 14px;
      }

      .notification-panel.visible {
        display: flex;
      }

      .notification-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        border-bottom: 1px solid #dee2e6;
        background: #f8f9fa;
        border-radius: 8px 8px 0 0;
      }

      .notification-title {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: #212529;
      }

      .clear-all-btn {
        background: #007bff;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
        transition: background-color 0.2s;
      }

      .clear-all-btn:hover {
        background: #0056b3;
      }

      .notification-list {
        flex: 1;
        overflow-y: auto;
        max-height: 400px;
      }

      .notification-item {
        padding: 12px 16px;
        border-bottom: 1px solid #f1f3f4;
        cursor: pointer;
        transition: background-color 0.2s;
        position: relative;
      }

      .notification-item:hover {
        background: #f8f9fa;
      }

      .notification-item.unread {
        background: #e3f2fd;
        border-left: 3px solid #2196f3;
      }

      .notification-content {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
      }

      .notification-text {
        flex: 1;
        margin-right: 12px;
      }

      .notification-title {
        font-weight: 500;
        color: #212529;
        margin-bottom: 4px;
        font-size: 14px;
      }

      .notification-message {
        color: #6c757d;
        font-size: 12px;
        line-height: 1.4;
      }

      .notification-time {
        color: #9e9e9e;
        font-size: 11px;
        margin-top: 4px;
      }

      .notification-actions {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
      }

      .mark-read-btn {
        background: none;
        border: none;
        color: #6c757d;
        cursor: pointer;
        padding: 4px;
        border-radius: 3px;
        font-size: 12px;
        transition: all 0.2s;
      }

      .mark-read-btn:hover {
        background: #e9ecef;
        color: #212529;
      }

      .notification-badge {
        position: fixed;
        top: 15px;
        right: 15px;
        background: #dc3545;
        color: white;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        font-weight: bold;
        z-index: 10001;
        cursor: pointer;
        transition: all 0.2s;
      }

      .notification-badge.hidden {
        display: none;
      }

      .notification-badge:hover {
        transform: scale(1.1);
      }

      .notification-badge.pulse {
        animation: pulse 2s infinite;
      }

      @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
      }

      .empty-notifications {
        padding: 40px 20px;
        text-align: center;
        color: #6c757d;
        font-style: italic;
      }
    `;
    document.head.appendChild(style);
  }

  /**
   * Initialize message listeners
   */
  initMessageListeners() {
    // Listen for thread updates from background script
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === 'threadUpdate') {
        this.handleThreadUpdate(request.threadId, request.updates);
        sendResponse({ success: true });
      }
    });

    // Handle badge click to show/hide panel
    this.badge.addEventListener('click', () => {
      this.togglePanel();
    });

    // Close panel when clicking outside
    document.addEventListener('click', (e) => {
      if (!this.panel.contains(e.target) && !this.badge.contains(e.target)) {
        this.hidePanel();
      }
    });
  }

  /**
   * Load existing unread updates from storage
   */
  async loadUnreadUpdates() {
    try {
      const response = await chrome.runtime.sendMessage({ action: 'getUnreadUpdates' });
      if (response.success && response.updates) {
        Object.entries(response.updates).forEach(([threadId, data]) => {
          this.addNotification(threadId, data.updates, data.timestamp, false);
        });
      }
    } catch (error) {
      console.error('Failed to load unread updates:', error);
    }
  }

  /**
   * Handle thread update from WebSocket
   * @param {string} threadId - Thread ID
   * @param {object} updates - Update data
   */
  handleThreadUpdate(threadId, updates) {
    const timestamp = Date.now();
    this.addNotification(threadId, updates, timestamp, true);
  }

  /**
   * Add a notification to the system
   * @param {string} threadId - Thread ID
   * @param {object} updates - Update data
   * @param {number} timestamp - Timestamp
   * @param {boolean} isNew - Whether this is a new notification
   */
  addNotification(threadId, updates, timestamp, isNew = true) {
    // Remove old notifications if at limit
    if (this.notifications.size >= this.maxNotifications) {
      const oldestKey = this.notifications.keys().next().value;
      this.removeNotification(oldestKey);
    }

    // Create notification data
    const notification = {
      threadId,
      updates,
      timestamp,
      isNew,
      unread: true
    };

    this.notifications.set(threadId, notification);
    this.renderNotification(notification);

    if (isNew) {
      this.unreadCount++;
      this.updateBadge();

      // Auto-show panel for new notifications
      this.showPanel();
    }
  }

  /**
   * Render a notification item
   * @param {object} notification - Notification data
   */
  renderNotification(notification) {
    // Remove existing notification for this thread
    const existing = this.list.querySelector(`[data-thread-id="${notification.threadId}"]`);
    if (existing) {
      existing.remove();
    }

    // Create notification element
    const item = document.createElement('div');
    item.className = `notification-item ${notification.unread ? 'unread' : ''}`;
    item.setAttribute('data-thread-id', notification.threadId);

    // Create content
    const content = document.createElement('div');
    content.className = 'notification-content';

    const text = document.createElement('div');
    text.className = 'notification-text';

    const title = document.createElement('div');
    title.className = 'notification-title';
    title.textContent = notification.updates.title || `Thread ${notification.threadId}`;

    const message = document.createElement('div');
    message.className = 'notification-message';

    // Build message based on update type
    const messages = [];
    if (notification.updates.newReleases && notification.updates.newReleases.length > 0) {
      messages.push(`${notification.updates.newReleases.length} new release(s)`);
    }
    if (notification.updates.likeCount !== undefined) {
      messages.push(`Likes: ${notification.updates.likeCount}`);
    }
    message.textContent = messages.join(', ') || 'Updated';

    const time = document.createElement('div');
    time.className = 'notification-time';
    time.textContent = this.formatTime(notification.timestamp);

    text.appendChild(title);
    text.appendChild(message);
    text.appendChild(time);

    // Create actions
    const actions = document.createElement('div');
    actions.className = 'notification-actions';

    const markReadBtn = document.createElement('button');
    markReadBtn.className = 'mark-read-btn';
    markReadBtn.textContent = '✓';
    markReadBtn.title = 'Mark as read';
    markReadBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.markAsRead(notification.threadId);
    });

    actions.appendChild(markReadBtn);

    content.appendChild(text);
    content.appendChild(actions);

    item.appendChild(content);

    // Add click handler to focus thread
    item.addEventListener('click', () => {
      this.focusThread(notification.threadId);
    });

    // Add to list (newest first)
    if (this.list.firstChild) {
      this.list.insertBefore(item, this.list.firstChild);
    } else {
      this.list.appendChild(item);
    }
  }

  /**
   * Mark a notification as read
   * @param {string} threadId - Thread ID
   */
  async markAsRead(threadId) {
    const notification = this.notifications.get(threadId);
    if (notification && notification.unread) {
      notification.unread = false;
      this.unreadCount = Math.max(0, this.unreadCount - 1);

      // Update UI
      const item = this.list.querySelector(`[data-thread-id="${threadId}"]`);
      if (item) {
        item.classList.remove('unread');
      }

      this.updateBadge();

      // Notify background script
      try {
        await chrome.runtime.sendMessage({
          action: 'markThreadAsRead',
          threadId: threadId
        });
      } catch (error) {
        console.error('Failed to mark thread as read:', error);
      }
    }
  }

  /**
   * Mark all notifications as read
   */
  async markAllAsRead() {
    const unreadThreadIds = Array.from(this.notifications.values())
      .filter(n => n.unread)
      .map(n => n.threadId);

    for (const threadId of unreadThreadIds) {
      await this.markAsRead(threadId);
    }
  }

  /**
   * Remove a notification
   * @param {string} threadId - Thread ID
   */
  removeNotification(threadId) {
    const notification = this.notifications.get(threadId);
    if (notification && notification.unread) {
      this.unreadCount = Math.max(0, this.unreadCount - 1);
    }

    this.notifications.delete(threadId);

    const item = this.list.querySelector(`[data-thread-id="${threadId}"]`);
    if (item) {
      item.remove();
    }

    this.updateBadge();

    // Show empty state if no notifications
    if (this.notifications.size === 0) {
      this.showEmptyState();
    }
  }

  /**
   * Show empty state when no notifications
   */
  showEmptyState() {
    const empty = document.createElement('div');
    empty.className = 'empty-notifications';
    empty.textContent = 'No thread updates';
    this.list.appendChild(empty);
  }

  /**
   * Focus on a specific thread (scroll to it)
   * @param {string} threadId - Thread ID
   */
  focusThread(threadId) {
    // Dispatch custom event for tree view to handle
    const event = new CustomEvent('focusThread', {
      detail: { threadId }
    });
    document.dispatchEvent(event);

    // Mark as read when focused
    this.markAsRead(threadId);
  }

  /**
   * Update notification badge
   */
  updateBadge() {
    if (this.unreadCount > 0) {
      this.badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
      this.badge.classList.remove('hidden');
      this.badge.classList.add('pulse');
    } else {
      this.badge.classList.add('hidden');
      this.badge.classList.remove('pulse');
    }
  }

  /**
   * Toggle notification panel visibility
   */
  togglePanel() {
    if (this.panel.classList.contains('visible')) {
      this.hidePanel();
    } else {
      this.showPanel();
    }
  }

  /**
   * Show notification panel
   */
  showPanel() {
    this.panel.classList.add('visible');

    // Mark visible notifications as read after 2 seconds
    setTimeout(() => {
      if (this.panel.classList.contains('visible')) {
        // Mark top visible notifications as read
        const visibleItems = Array.from(this.list.querySelectorAll('.notification-item.unread')).slice(0, 3);
        visibleItems.forEach(item => {
          const threadId = item.getAttribute('data-thread-id');
          this.markAsRead(threadId);
        });
      }
    }, 2000);
  }

  /**
   * Hide notification panel
   */
  hidePanel() {
    this.panel.classList.remove('visible');
  }

  /**
   * Format timestamp for display
   * @param {number} timestamp - Unix timestamp
   * @returns {string} Formatted time
   */
  formatTime(timestamp) {
    const now = Date.now();
    const diff = now - timestamp;

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return `${Math.floor(diff / 86400000)}d ago`;
  }

  /**
   * Get current notification status
   * @returns {object} Status information
   */
  getStatus() {
    return {
      totalNotifications: this.notifications.size,
      unreadCount: this.unreadCount,
      notifications: Array.from(this.notifications.values())
    };
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = NotificationSystem;
}