/**
 * LikeButton Component for thread liking functionality
 * Handles visual states, API integration, and state persistence
 * Uses Shadow DOM for style encapsulation and custom events for state changes
 */
class LikeButton {
  constructor(threadId, initialState = {}) {
    this.threadId = threadId;
    this.state = {
      isLiked: initialState.isLiked || false,
      likeCount: initialState.likeCount || 0,
      status: 'idle', // idle, liking, liked, error
      retryCount: 0
    };

    // Create shadow root for style encapsulation
    this.shadow = document.createElement('div').attachShadow({ mode: 'open' });

    // Bind methods
    this.handleClick = this.handleClick.bind(this);
    this.handleRetry = this.handleRetry.bind(this);

    // Initialize component
    this.init();
  }

  /**
   * Initialize the button component
   */
  init() {
    this.createButton();
    this.loadState();
    this.attachEvents();
  }

  /**
   * Create the button element with appropriate initial state
   */
  createButton() {
    const button = document.createElement('button');
    button.className = 'like-button';
    button.setAttribute('aria-label', this.getAriaLabel());
    button.innerHTML = this.getButtonContent();

    // Inject CSS
    const style = document.createElement('style');
    style.textContent = this.getCSS();
    this.shadow.appendChild(style);
    this.shadow.appendChild(button);

    this.button = button;
  }

  /**
   * Get the CSS styles for the component
   * @returns {string} CSS styles
   */
  getCSS() {
    return `
      .like-button {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        background: #fff;
        color: #495057;
        font-size: 13px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        cursor: pointer;
        transition: all 0.2s ease;
        position: relative;
        min-height: 32px;
      }

      .like-button:hover:not(:disabled) {
        background: #f8f9fa;
        border-color: #adb5bd;
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      }

      .like-button:active:not(:disabled) {
        transform: translateY(0);
      }

      .like-button:disabled {
        cursor: not-allowed;
        opacity: 0.6;
      }

      .like-button.liked {
        background: #d4edda;
        border-color: #c3e6cb;
        color: #155724;
      }

      .like-button.error {
        background: #f8d7da;
        border-color: #f5c6cb;
        color: #721c24;
      }

      .like-button.processing {
        background: #fff3cd;
        border-color: #ffeaa7;
        color: #856404;
        cursor: wait;
      }

      .spinner {
        width: 14px;
        height: 14px;
        border: 2px solid #f3f3f3;
        border-top: 2px solid #856404;
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }

      .icon {
        font-size: 16px;
        line-height: 1;
      }

      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }

      .tooltip {
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(0,0,0,0.8);
        color: white;
        padding: 4px 8px;
        border-radius: 3px;
        font-size: 12px;
        white-space: nowrap;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s;
        margin-bottom: 4px;
      }

      .like-button:hover .tooltip {
        opacity: 1;
      }
    `;
  }

  /**
   * Get the button content based on current state
   * @returns {string} HTML content for the button
   */
  getButtonContent() {
    const { status, isLiked, likeCount } = this.state;

    switch (status) {
      case 'liking':
        return `
          <div class="spinner"></div>
          <span>Liking...</span>
        `;

      case 'liked':
        return `
          <span class="icon">✅</span>
          <span>Liked</span>
        `;

      case 'error':
        return `
          <span class="icon">❌</span>
          <span>Retry</span>
          <div class="tooltip">Failed to like thread. Click to retry.</div>
        `;

      default: // idle
        return `
          <span class="icon">👍</span>
          <span>Like Thread</span>
          ${likeCount > 0 ? `<span class="like-count">(${likeCount})</span>` : ''}
        `;
    }
  }

  /**
   * Get appropriate ARIA label for accessibility
   * @returns {string} ARIA label text
   */
  getAriaLabel() {
    const { status, isLiked, likeCount } = this.state;

    switch (status) {
      case 'liking':
        return 'Liking thread...';
      case 'liked':
        return 'Thread liked';
      case 'error':
        return 'Failed to like thread, click to retry';
      default:
        return isLiked ? `Unlike thread (${likeCount} likes)` : `Like thread (${likeCount} likes)`;
    }
  }

  /**
   * Update button appearance based on current state
   */
  updateButton() {
    this.button.className = `like-button ${this.state.status}`;
    this.button.innerHTML = this.getButtonContent();
    this.button.setAttribute('aria-label', this.getAriaLabel());
    this.button.disabled = this.state.status === 'liking';
  }

  /**
   * Attach event listeners to the button
   */
  attachEvents() {
    this.button.addEventListener('click', this.handleClick);
  }

  /**
   * Handle button click events
   * @param {Event} event - Click event
   */
  async handleClick(event) {
    event.preventDefault();
    event.stopPropagation();

    if (this.state.status === 'liking') return;

    if (this.state.status === 'error') {
      await this.handleRetry();
    } else {
      await this.performLike();
    }
  }

  /**
   * Perform the like action with retry logic
   */
  async performLike() {
    this.setState({ status: 'liking' });

    try {
      const response = await this.sendLikeRequest();

      if (response.success) {
        this.setState({
          status: 'liked',
          isLiked: true,
          likeCount: response.total_likes || this.state.likeCount + 1,
          retryCount: 0
        });

        // Save state to extension storage
        await this.saveState();

        // Dispatch custom event for parent components
        this.dispatchEvent('liked', {
          threadId: this.threadId,
          likeCount: this.state.likeCount
        });

        // Track analytics
        this.trackAnalytics('like', { threadId: this.threadId });

        // Trigger thread refresh after successful like
        this.triggerThreadRefresh();

        // Auto-reset to idle state after 2 seconds
        setTimeout(() => {
          if (this.state.status === 'liked') {
            this.setState({ status: 'idle' });
          }
        }, 2000);
      } else {
        throw new Error(response.error || 'Like request failed');
      }
    } catch (error) {
      console.error('Like button error:', error);
      this.setState({
        status: 'error',
        retryCount: this.state.retryCount + 1
      });

      // Reset to idle after 5 seconds if user doesn't retry
      setTimeout(() => {
        if (this.state.status === 'error') {
          this.setState({ status: 'idle' });
        }
      }, 5000);
    }
  }

  /**
   * Handle retry action with exponential backoff
   */
  async handleRetry() {
    const delay = Math.min(1000 * Math.pow(2, this.state.retryCount), 10000); // Max 10 seconds

    setTimeout(async () => {
      await this.performLike();
    }, delay);
  }

  /**
   * Send like request to background script
   * @returns {Promise<object>} Response from API
   */
  async sendLikeRequest() {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({
        action: 'likeThread',
        threadId: this.threadId
      }, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response);
        }
      });
    });
  }

  /**
   * Trigger thread refresh after successful like
   */
  async triggerThreadRefresh() {
    try {
      await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({
          action: 'refreshThread',
          threadId: this.threadId
        }, (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else if (response.success) {
            resolve(response);
          } else {
            reject(new Error(response.error || 'Refresh failed'));
          }
        });
      });

      // Dispatch event to notify parent components about refresh
      this.dispatchEvent('refreshed', {
        threadId: this.threadId
      });
    } catch (error) {
      console.warn('Thread refresh failed:', error);
      // Don't fail the like operation if refresh fails
    }
  }

  /**
   * Update component state and re-render
   * @param {object} newState - Partial state update
   */
  setState(newState) {
    this.state = { ...this.state, ...newState };
    this.updateButton();
  }

  /**
   * Load state from extension storage
   */
  async loadState() {
    try {
      const result = await new Promise((resolve) => {
        chrome.storage.local.get([`thread_${this.threadId}`], resolve);
      });

      const storedState = result[`thread_${this.threadId}`];
      if (storedState) {
        this.setState(storedState);
      }
    } catch (error) {
      console.error('Failed to load like state:', error);
    }
  }

  /**
   * Save state to extension storage
   */
  async saveState() {
    try {
      const stateToSave = {
        isLiked: this.state.isLiked,
        likeCount: this.state.likeCount,
        status: this.state.status === 'liked' ? 'idle' : this.state.status
      };

      await new Promise((resolve) => {
        chrome.storage.local.set({ [`thread_${this.threadId}`]: stateToSave }, resolve);
      });
    } catch (error) {
      console.error('Failed to save like state:', error);
    }
  }

  /**
   * Update like count from external source
   * @param {number} newCount - New like count
   * @param {boolean} userLiked - Whether user liked this thread
   */
  updateLikeCount(newCount, userLiked = null) {
    this.setState({
      likeCount: newCount,
      isLiked: userLiked !== null ? userLiked : this.state.isLiked
    });
  }

  /**
   * Dispatch custom event to parent components
   * @param {string} eventType - Event type
   * @param {object} detail - Event detail data
   */
  dispatchEvent(eventType, detail) {
    const event = new CustomEvent(`likebutton:${eventType}`, {
      bubbles: true,
      detail: { threadId: this.threadId, ...detail }
    });
    this.shadow.host.dispatchEvent(event);
  }

  /**
   * Get the root element for DOM insertion
   * @returns {HTMLElement} Shadow host element
   */
  getElement() {
    return this.shadow.host;
  }

  /**
   * Track analytics events for like actions
   * @param {string} action - Action type ('like', 'unlike', 'retry', etc.)
   * @param {object} data - Additional data for the event
   */
  trackAnalytics(action, data = {}) {
    try {
      // Send analytics event to background script
      if (typeof chrome !== 'undefined' && chrome.runtime) {
        chrome.runtime.sendMessage({
          action: 'trackAnalytics',
          event: 'like_action',
          data: {
            action,
            threadId: this.threadId,
            retryCount: this.state.retryCount,
            timestamp: Date.now(),
            ...data
          }
        }).catch(err => console.warn('Analytics tracking failed:', err));
      }

      // Also dispatch custom event for external analytics
      this.dispatchEvent('analytics', {
        action,
        data: { ...data, threadId: this.threadId }
      });
    } catch (error) {
      console.warn('Analytics error:', error);
    }
  }

  /**
   * Clean up event listeners and resources
   */
  destroy() {
    if (this.button) {
      this.button.removeEventListener('click', this.handleClick);
    }
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = LikeButton;
}