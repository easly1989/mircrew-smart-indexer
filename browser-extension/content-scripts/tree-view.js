/**
 * TreeView Component for displaying hierarchical search results grouped by threads
 * Uses Shadow DOM for style encapsulation and ARIA attributes for accessibility
 * Integrates LikeButton components for thread liking functionality
 */

class TreeView {
  constructor(container) {
    this.container = container;
    this.data = [];
    this.expandedNodes = new Set();
    this.sortBy = 'thread_date'; // thread_date, like_count, episode_count
    this.sortOrder = 'desc'; // asc, desc
    this.notificationSystem = null;

    // Create shadow root for style encapsulation
    this.shadow = this.container.attachShadow({ mode: 'open' });

    // Initialize the component
    this.init();
  }

  /**
   * Initialize the tree view structure
   */
  init() {
    // Create main container
    this.wrapper = document.createElement('div');
    this.wrapper.className = 'tree-view-wrapper';
    this.wrapper.setAttribute('role', 'tree');
    this.wrapper.setAttribute('aria-label', 'Search results grouped by threads');

    // Create sorting controls
    this.sortControls = this.createSortControls();

    // Create tree container
    this.treeContainer = document.createElement('div');
    this.treeContainer.className = 'tree-container';

    this.wrapper.appendChild(this.sortControls);
    this.wrapper.appendChild(this.treeContainer);

    // Inject CSS
    const style = document.createElement('style');
    style.textContent = this.getCSS();
    this.shadow.appendChild(style);
    this.shadow.appendChild(this.wrapper);

    // Initialize message listeners for real-time updates
    this.initMessageListeners();

    // Initialize notification system
    this.initNotificationSystem();
  }

  /**
   * Initialize notification system
   */
  initNotificationSystem() {
    // Load notification system script dynamically
    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('content-scripts/notifications.js');
    script.onload = () => {
      // Create notification system instance
      this.notificationSystem = new NotificationSystem(this.container);

      // Listen for focus thread events from notifications
      document.addEventListener('focusThread', (event) => {
        this.focusThread(event.detail.threadId);
      });
    };
    document.head.appendChild(script);
  }

  /**
   * Initialize message listeners for real-time updates
   */
  initMessageListeners() {
    // Listen for thread updates from background script
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === 'threadUpdate') {
        this.updateThreadReleases(request.threadId, request.updates);
        sendResponse({ success: true });
      }
    });

    // Subscribe to threads when they become visible
    this.subscribeToVisibleThreads();
  }

  /**
   * Subscribe to updates for threads currently visible in the tree
   */
  subscribeToVisibleThreads() {
    // Subscribe to all threads in current data
    this.data.forEach(thread => {
      this.subscribeToThread(thread.thread_id);
    });

    // Also subscribe when new data is set
    const originalSetData = this.setData.bind(this);
    this.setData = (data) => {
      originalSetData(data);
      // Subscribe to new threads
      data.forEach(thread => {
        this.subscribeToThread(thread.thread_id);
      });
    };
  }

  /**
   * Subscribe to real-time updates for a specific thread
   * @param {string} threadId - Thread ID to subscribe to
   */
  subscribeToThread(threadId) {
    chrome.runtime.sendMessage({
      action: 'subscribeThread',
      threadId: threadId
    }).catch(error => {
      console.debug('Failed to subscribe to thread:', threadId, error);
    });
  }

  /**
   * Create sorting controls UI
   * @returns {HTMLElement} Sort controls container
   */
  createSortControls() {
    const controls = document.createElement('div');
    controls.className = 'sort-controls';

    controls.innerHTML = `
      <label for="sort-select">Sort by:</label>
      <select id="sort-select" aria-label="Sort search results">
        <option value="thread_date">Thread Date</option>
        <option value="like_count">Like Count</option>
        <option value="episode_count">Episode Count</option>
      </select>
      <button id="sort-order-btn" aria-label="Toggle sort order">
        <span class="sort-icon">↓</span>
      </button>
    `;

    // Add event listeners
    const select = controls.querySelector('#sort-select');
    const orderBtn = controls.querySelector('#sort-order-btn');

    select.addEventListener('change', (e) => {
      this.sortBy = e.target.value;
      this.render();
    });

    orderBtn.addEventListener('click', () => {
      this.sortOrder = this.sortOrder === 'desc' ? 'asc' : 'desc';
      orderBtn.querySelector('.sort-icon').textContent = this.sortOrder === 'desc' ? '↓' : '↑';
      this.render();
    });

    return controls;
  }

  /**
   * Set the data and trigger re-render
   * @param {Array} data - Array of thread objects with releases
   */
  setData(data) {
    this.data = this.processData(data);
    this.render();
  }

  /**
   * Process and group raw data by threads
   * @param {Array} rawData - Raw search results
   * @returns {Array} Processed thread data
   */
  processData(rawData) {
    // Group releases by thread_id
    const threadMap = new Map();

    rawData.forEach(item => {
      const threadId = item.thread_id || item.threadId || 'unknown';

      if (!threadMap.has(threadId)) {
        threadMap.set(threadId, {
          thread_id: threadId,
          title: item.thread_title || item.threadTitle || 'Unknown Thread',
          author: item.thread_author || item.threadAuthor || 'Unknown',
          post_date: item.thread_date || item.threadDate || new Date().toISOString(),
          like_count: item.like_count || item.likeCount || 0,
          user_liked: item.user_liked || item.userLiked || false,
          releases: []
        });
      }

      threadMap.get(threadId).releases.push({
        title: item.title,
        size: item.size,
        seeders: item.seeders,
        magnet: item.magnet,
        link: item.link,
        episode: item.episode,
        season: item.season
      });
    });

    return Array.from(threadMap.values());
  }

  /**
   * Sort the thread data based on current sort settings
   * @param {Array} data - Thread data to sort
   * @returns {Array} Sorted data
   */
  sortData(data) {
    return data.sort((a, b) => {
      let aVal, bVal;

      switch (this.sortBy) {
        case 'thread_date':
          aVal = new Date(a.post_date);
          bVal = new Date(b.post_date);
          break;
        case 'like_count':
          aVal = a.like_count;
          bVal = b.like_count;
          break;
        case 'episode_count':
          aVal = a.releases.length;
          bVal = b.releases.length;
          break;
        default:
          aVal = a.post_date;
          bVal = b.post_date;
      }

      if (this.sortOrder === 'desc') {
        return bVal > aVal ? 1 : bVal < aVal ? -1 : 0;
      } else {
        return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
      }
    });
  }

  /**
   * Render the tree view
   */
  render() {
    const sortedData = this.sortData(this.data);
    this.treeContainer.innerHTML = '';

    if (sortedData.length === 0) {
      this.treeContainer.innerHTML = '<div class="no-results">No results found</div>';
      return;
    }

    sortedData.forEach(thread => {
      const threadNode = this.createThreadNode(thread);
      this.treeContainer.appendChild(threadNode);
    });
  }

  /**
   * Create a thread node element
   * @param {object} thread - Thread data
   * @returns {HTMLElement} Thread node element
   */
  createThreadNode(thread) {
    const node = document.createElement('div');
    node.className = 'thread-node';
    node.setAttribute('role', 'treeitem');
    node.setAttribute('aria-expanded', this.expandedNodes.has(thread.thread_id));
    node.setAttribute('data-thread-id', thread.thread_id);

    const isExpanded = this.expandedNodes.has(thread.thread_id);

    // Create thread header structure
    const header = document.createElement('div');
    header.className = 'thread-header';
    header.setAttribute('tabindex', '0');

    header.innerHTML = `
      <button class="expand-btn" aria-label="${isExpanded ? 'Collapse' : 'Expand'} thread">
        <span class="expand-icon">${isExpanded ? '▼' : '▶'}</span>
      </button>
      <div class="thread-info">
        <div class="thread-title">${this.escapeHtml(thread.title)}</div>
        <div class="thread-meta">
          <span class="author">by ${this.escapeHtml(thread.author)}</span>
          <span class="date">${this.formatDate(thread.post_date)}</span>
          <span class="like-count">♥ ${thread.like_count}</span>
          <span class="episode-count">${thread.releases.length} episodes</span>
          ${thread.user_liked ? '<span class="liked-indicator" title="You liked this">★</span>' : ''}
          <span class="like-button-container"></span>
        </div>
      </div>
    `;

    // Create like button and add it to the container
    const likeButtonContainer = header.querySelector('.like-button-container');
    if (typeof LikeButton !== 'undefined') {
      const likeButton = new LikeButton(thread.thread_id, {
        isLiked: thread.user_liked || false,
        likeCount: thread.like_count || 0
      });

      // Listen for like events to update the UI
      likeButton.getElement().addEventListener('likebutton:liked', (event) => {
        this.handleLikeUpdate(thread.thread_id, event.detail.likeCount, true);
      });

      likeButtonContainer.appendChild(likeButton.getElement());
    }

    // Create children container
    const children = document.createElement('div');
    children.className = 'thread-children';
    children.style.display = isExpanded ? 'block' : 'none';
    children.innerHTML = thread.releases.map(release => this.createReleaseNode(release)).join('');

    // Assemble the node
    node.appendChild(header);
    node.appendChild(children);

    // Add event listeners
    const expandBtn = header.querySelector('.expand-btn');

    const toggleExpand = () => {
      const expanded = this.expandedNodes.has(thread.thread_id);
      if (expanded) {
        this.expandedNodes.delete(thread.thread_id);
      } else {
        this.expandedNodes.add(thread.thread_id);
      }
      node.setAttribute('aria-expanded', !expanded);
      expandBtn.setAttribute('aria-label', expanded ? 'Expand thread' : 'Collapse thread');
      expandBtn.querySelector('.expand-icon').textContent = expanded ? '▶' : '▼';
      children.style.display = expanded ? 'none' : 'block';
    };

    header.addEventListener('click', (e) => {
      // Don't toggle if clicking on like button
      if (e.target.closest('.like-button')) return;
      toggleExpand();
    });

    header.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleExpand();
      }
    });

    return node;
  }

  /**
   * Create a release node element
   * @param {object} release - Release data
   * @returns {string} Release node HTML
   */
  createReleaseNode(release) {
    return `
      <div class="release-node" role="treeitem">
        <div class="release-info">
          <div class="release-title">${this.escapeHtml(release.title)}</div>
          <div class="release-meta">
            <span class="size">${release.size || 'Unknown'}</span>
            <span class="seeders">${release.seeders || 0} seeders</span>
          </div>
        </div>
        <button class="download-btn" onclick="window.open('${this.escapeHtml(release.magnet || release.link)}', '_blank')" aria-label="Download ${this.escapeHtml(release.title)}">
          Download
        </button>
      </div>
    `;
  }

  /**
   * Get the CSS styles for the component
   * @returns {string} CSS styles
   */
  getCSS() {
    return `
      .tree-view-wrapper {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 14px;
        background: #fff;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        max-height: 600px;
        overflow-y: auto;
      }

      .sort-controls {
        display: flex;
        align-items: center;
        padding: 8px 12px;
        border-bottom: 1px solid #dee2e6;
        background: #f8f9fa;
        gap: 8px;
      }

      .sort-controls select {
        padding: 4px 8px;
        border: 1px solid #ced4da;
        border-radius: 3px;
      }

      #sort-order-btn {
        padding: 4px 8px;
        background: #007bff;
        color: white;
        border: none;
        border-radius: 3px;
        cursor: pointer;
      }

      .tree-container {
        padding: 8px;
      }

      .thread-node {
        margin-bottom: 4px;
      }

      .thread-header {
        display: flex;
        align-items: center;
        padding: 8px;
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.2s;
      }

      .thread-header:hover, .thread-header:focus {
        background: #e9ecef;
        outline: 2px solid #007bff;
        outline-offset: -2px;
      }

      .expand-btn {
        background: none;
        border: none;
        cursor: pointer;
        padding: 4px;
        margin-right: 8px;
        color: #6c757d;
      }

      .thread-info {
        flex: 1;
      }

      .thread-title {
        font-weight: bold;
        margin-bottom: 4px;
        color: #212529;
      }

      .thread-meta {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 12px;
        color: #6c757d;
        flex-wrap: wrap;
      }

      .like-button-container {
        margin-left: auto;
        display: flex;
        align-items: center;
      }

      .liked-indicator {
        color: #ffc107;
      }

      .thread-children {
        margin-left: 32px;
        border-left: 2px solid #dee2e6;
        padding-left: 8px;
        margin-top: 4px;
      }

      .release-node {
        display: flex;
        align-items: center;
        padding: 6px 8px;
        margin-bottom: 2px;
        background: #fff;
        border: 1px solid #e9ecef;
        border-radius: 3px;
      }

      .release-info {
        flex: 1;
      }

      .release-title {
        font-size: 13px;
        margin-bottom: 2px;
        color: #495057;
      }

      .release-meta {
        display: flex;
        gap: 12px;
        font-size: 11px;
        color: #6c757d;
      }

      .download-btn {
        padding: 4px 8px;
        background: #28a745;
        color: white;
        border: none;
        border-radius: 3px;
        cursor: pointer;
        font-size: 12px;
      }

      .download-btn:hover {
        background: #218838;
      }

      .no-results {
        padding: 20px;
        text-align: center;
        color: #6c757d;
      }

      .new-releases-indicator {
        color: #28a745;
        font-weight: bold;
        margin-left: 8px;
        animation: pulse 2s infinite;
      }

      @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
      }

      .new-release {
        background: linear-gradient(90deg, #d4edda 0%, #fff 100%);
        border-left: 4px solid #28a745;
        animation: slideIn 0.5s ease-out;
      }

      @keyframes slideIn {
        from {
          opacity: 0;
          transform: translateX(-20px);
        }
        to {
          opacity: 1;
          transform: translateX(0);
        }
      }

      .thread-header.updated {
        animation: highlight 1s ease-out;
      }

      @keyframes highlight {
        0% { background-color: #e3f2fd; }
        100% { background-color: #f8f9fa; }
      }

      .thread-node.focused {
        animation: focusedPulse 3s ease-out;
        box-shadow: 0 0 0 2px #007bff;
      }

      @keyframes focusedPulse {
        0% { box-shadow: 0 0 0 2px #007bff; }
        50% { box-shadow: 0 0 0 4px rgba(0, 123, 255, 0.3); }
        100% { box-shadow: 0 0 0 2px transparent; }
      }
    `;
  }

  /**
   * Escape HTML to prevent XSS
   * @param {string} text - Text to escape
   * @returns {string} Escaped text
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Handle like updates from LikeButton components
   * @param {string} threadId - Thread ID that was liked
   * @param {number} newLikeCount - Updated like count
   * @param {boolean} userLiked - Whether user liked this thread
   */
  handleLikeUpdate(threadId, newLikeCount, userLiked) {
    // Update the thread data
    const thread = this.data.find(t => t.thread_id === threadId);
    if (thread) {
      thread.like_count = newLikeCount;
      thread.user_liked = userLiked;

      // Update the UI if this thread is currently rendered
      const threadNode = this.treeContainer.querySelector(`[data-thread-id="${threadId}"]`);
      if (threadNode) {
        const likeCountEl = threadNode.querySelector('.like-count');
        const likedIndicator = threadNode.querySelector('.liked-indicator');

        if (likeCountEl) {
          likeCountEl.textContent = `♥ ${newLikeCount}`;
        }

        if (userLiked && !likedIndicator) {
          // Add liked indicator if not present
          const metaEl = threadNode.querySelector('.thread-meta');
          if (metaEl) {
            const indicator = document.createElement('span');
            indicator.className = 'liked-indicator';
            indicator.title = 'You liked this';
            indicator.textContent = '★';
            metaEl.appendChild(indicator);
          }
        } else if (!userLiked && likedIndicator) {
          // Remove liked indicator if present
          likedIndicator.remove();
        }
      }
    }
  }

  /**
   * Update thread releases with real-time data
   * @param {string} threadId - Thread ID to update
   * @param {object} updates - Update data from WebSocket
   */
  updateThreadReleases(threadId, updates) {
    const threadIndex = this.data.findIndex(t => t.thread_id === threadId);
    if (threadIndex === -1) {
      console.log('Thread not found in current data:', threadId);
      return;
    }

    const thread = this.data[threadIndex];
    let hasNewReleases = false;

    // Update thread metadata if provided
    if (updates.likeCount !== undefined) {
      thread.like_count = updates.likeCount;
    }
    if (updates.userLiked !== undefined) {
      thread.user_liked = updates.userLiked;
    }
    if (updates.title) {
      thread.title = updates.title;
    }

    // Add new releases if provided
    if (updates.newReleases && Array.isArray(updates.newReleases)) {
      hasNewReleases = updates.newReleases.length > 0;

      updates.newReleases.forEach(newRelease => {
        // Check if release already exists (by title or magnet)
        const exists = thread.releases.some(existing =>
          existing.title === newRelease.title ||
          existing.magnet === newRelease.magnet ||
          existing.link === newRelease.link
        );

        if (!exists) {
          thread.releases.push({
            title: newRelease.title,
            size: newRelease.size,
            seeders: newRelease.seeders,
            magnet: newRelease.magnet,
            link: newRelease.link,
            episode: newRelease.episode,
            season: newRelease.season,
            isNew: true // Mark as new for visual indication
          });
        }
      });
    }

    // Update the UI with smooth transitions
    this.updateThreadUI(threadId, hasNewReleases);

    // Resort if needed (new releases might change episode count)
    if (hasNewReleases && this.sortBy === 'episode_count') {
      this.render();
    }
  }

  /**
   * Update thread UI with visual feedback
   * @param {string} threadId - Thread ID to update
   * @param {boolean} hasNewReleases - Whether new releases were added
   */
  updateThreadUI(threadId, hasNewReleases = false) {
    const threadNode = this.treeContainer.querySelector(`[data-thread-id="${threadId}"]`);
    if (!threadNode) {
      console.log('Thread node not found in UI:', threadId);
      return;
    }

    const thread = this.data.find(t => t.thread_id === threadId);
    if (!thread) return;

    // Update like count
    const likeCountEl = threadNode.querySelector('.like-count');
    if (likeCountEl) {
      likeCountEl.textContent = `♥ ${thread.like_count}`;
    }

    // Update liked indicator
    const likedIndicator = threadNode.querySelector('.liked-indicator');
    if (thread.user_liked && !likedIndicator) {
      const metaEl = threadNode.querySelector('.thread-meta');
      if (metaEl) {
        const indicator = document.createElement('span');
        indicator.className = 'liked-indicator';
        indicator.title = 'You liked this';
        indicator.textContent = '★';
        metaEl.appendChild(indicator);
      }
    } else if (!thread.user_liked && likedIndicator) {
      likedIndicator.remove();
    }

    // Update episode count
    const episodeCountEl = threadNode.querySelector('.episode-count');
    if (episodeCountEl) {
      episodeCountEl.textContent = `${thread.releases.length} episodes`;
    }

    // Update title if changed
    const titleEl = threadNode.querySelector('.thread-title');
    if (titleEl && titleEl.textContent !== thread.title) {
      titleEl.textContent = this.escapeHtml(thread.title);
    }

    // Add visual indicator for new releases
    if (hasNewReleases) {
      this.addNewReleaseIndicator(threadNode, threadId);
      this.updateReleaseNodes(threadNode, thread);
    }

    // Add update animation
    this.animateUpdate(threadNode);
  }

  /**
   * Add visual indicator for new releases
   * @param {HTMLElement} threadNode - Thread node element
   * @param {string} threadId - Thread ID
   */
  addNewReleaseIndicator(threadNode, threadId) {
    // Remove existing indicator
    const existingIndicator = threadNode.querySelector('.new-releases-indicator');
    if (existingIndicator) {
      existingIndicator.remove();
    }

    // Add new indicator
    const header = threadNode.querySelector('.thread-header');
    if (header) {
      const indicator = document.createElement('span');
      indicator.className = 'new-releases-indicator';
      indicator.title = 'New releases available';
      indicator.textContent = '🆕';
      header.appendChild(indicator);

      // Auto-remove after 30 seconds
      setTimeout(() => {
        if (indicator.parentNode) {
          indicator.remove();
        }
      }, 30000);
    }
  }

  /**
   * Update release nodes with new releases
   * @param {HTMLElement} threadNode - Thread node element
   * @param {object} thread - Thread data
   */
  updateReleaseNodes(threadNode, thread) {
    const childrenContainer = threadNode.querySelector('.thread-children');
    if (!childrenContainer) return;

    // Clear existing content and rebuild
    const newReleases = thread.releases.filter(release => release.isNew);
    const existingReleases = thread.releases.filter(release => !release.isNew);

    // Create HTML for all releases, highlighting new ones
    const allReleasesHtml = [
      ...existingReleases.map(release => this.createReleaseNode(release)),
      ...newReleases.map(release => {
        // Temporarily modify the release for highlighting
        const highlighted = { ...release, isNew: false };
        let html = this.createReleaseNode(highlighted);
        // Add highlight class
        html = html.replace('release-node', 'release-node new-release');
        return html;
      })
    ].join('');

    childrenContainer.innerHTML = allReleasesHtml;

    // Remove new release highlighting after animation
    setTimeout(() => {
      const newReleaseNodes = childrenContainer.querySelectorAll('.new-release');
      newReleaseNodes.forEach(node => {
        node.classList.remove('new-release');
      });

      // Clear the isNew flag from data
      thread.releases.forEach(release => {
        delete release.isNew;
      });
    }, 3000);
  }

  /**
   * Add smooth animation for updates
   * @param {HTMLElement} element - Element to animate
   */
  animateUpdate(element) {
    element.style.transition = 'background-color 0.3s ease';
    element.style.backgroundColor = '#e3f2fd'; // Light blue highlight

    setTimeout(() => {
      element.style.backgroundColor = '';
      setTimeout(() => {
        element.style.transition = '';
      }, 300);
    }, 1000);
  }

  /**
   * Focus on a specific thread (scroll to and highlight)
   * @param {string} threadId - Thread ID to focus on
   */
  focusThread(threadId) {
    const threadNode = this.treeContainer.querySelector(`[data-thread-id="${threadId}"]`);
    if (threadNode) {
      // Scroll into view
      threadNode.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });

      // Highlight the thread
      threadNode.classList.add('focused');
      setTimeout(() => {
        threadNode.classList.remove('focused');
      }, 3000);

      // Expand the thread if collapsed
      const isExpanded = this.expandedNodes.has(threadId);
      if (!isExpanded) {
        this.expandedNodes.add(threadId);
        const node = threadNode;
        const expandBtn = node.querySelector('.expand-btn');
        const expandIcon = expandBtn.querySelector('.expand-icon');
        const children = node.querySelector('.thread-children');

        node.setAttribute('aria-expanded', true);
        expandBtn.setAttribute('aria-label', 'Collapse thread');
        expandIcon.textContent = '▼';
        children.style.display = 'block';
      }
    }
  }

  /**
   * Format date for display
   * @param {string} dateStr - ISO date string
   * @returns {string} Formatted date
   */
  formatDate(dateStr) {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString();
    } catch {
      return 'Unknown';
    }
  }

  /**
   * Expand all thread nodes
   */
  expandAll() {
    this.data.forEach(thread => {
      this.expandedNodes.add(thread.thread_id);
    });
    this.render();
  }

  /**
   * Collapse all thread nodes
   */
  collapseAll() {
    this.expandedNodes.clear();
    this.render();
  }

  /**
   * Get current expanded state
   * @returns {Set} Set of expanded thread IDs
   */
  getExpandedState() {
    return new Set(this.expandedNodes);
  }

  /**
   * Set expanded state
   * @param {Set} state - Set of thread IDs to expand
   */
  setExpandedState(state) {
    this.expandedNodes = new Set(state);
    this.render();
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TreeView;
}