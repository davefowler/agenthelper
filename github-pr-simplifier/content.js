// GitHub PR Simplifier - Content Script
// Simplifies PR pages by showing CI status + merge button prominently,
// with comments in a tabbed interface

(function() {
  'use strict';

  // Only run on PR conversation pages
  if (!window.location.pathname.match(/\/pull\/\d+$/)) {
    // We're on a sub-page like /files or /commits, don't modify
    if (!window.location.pathname.match(/\/pull\/\d+\/?$/)) {
      return;
    }
  }

  let isSimplified = false;
  let originalState = null;

  function init() {
    // Wait for the page to fully load
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => setTimeout(simplifyPR, 500));
    } else {
      setTimeout(simplifyPR, 500);
    }

    // Re-run on navigation (GitHub uses pjax/turbo)
    document.addEventListener('turbo:load', () => setTimeout(simplifyPR, 500));
    document.addEventListener('pjax:end', () => setTimeout(simplifyPR, 500));
  }

  function simplifyPR() {
    // Check if we're on a PR page
    if (!window.location.pathname.match(/\/pull\/\d+\/?$/)) {
      return;
    }

    // Don't re-run if already simplified
    if (document.querySelector('.pr-simplifier-container')) {
      return;
    }

    const discussion = document.querySelector('.js-discussion');
    if (!discussion) {
      // Try again shortly if the page isn't ready
      setTimeout(simplifyPR, 500);
      return;
    }

    createSimplifiedView(discussion);
  }

  function createSimplifiedView(discussion) {
    // Find key elements
    const mergeBox = document.querySelector('.merge-pr, .js-merge-pr, [data-target="merge-box.loader"]')?.closest('.merge-message, .branch-action-item, .js-merge-box-button-container')?.closest('.BorderGrid-row, .merge-message');
    const statusChecks = document.querySelector('.merge-status-list, .branch-action-item, [data-target*="status"]')?.closest('.BorderGrid-row, .merge-message');

    // Get the PR header info
    const prHeader = document.querySelector('.gh-header-meta, .js-issue-header');

    // Find all timeline comments
    const timelineItems = discussion.querySelectorAll('.js-timeline-item, .timeline-comment-group, .TimelineItem');

    // Collect comments with metadata
    const comments = [];
    timelineItems.forEach((item, index) => {
      const author = item.querySelector('.author, [data-hovercard-type="user"]')?.textContent?.trim();
      const timestamp = item.querySelector('relative-time, time-ago');
      const timeText = timestamp?.getAttribute('datetime') || timestamp?.textContent || '';
      const commentBody = item.querySelector('.comment-body, .markdown-body');
      const isReview = item.classList.contains('js-timeline-item') && item.querySelector('.review-comment');
      const isBotComment = author?.includes('[bot]') || author?.includes('bot');

      if (commentBody || item.querySelector('.TimelineItem-body')) {
        comments.push({
          element: item.cloneNode(true),
          author: author || 'Unknown',
          timestamp: timeText,
          date: timestamp ? new Date(timeText) : new Date(0),
          index: index,
          isBot: isBotComment,
          isReview: isReview
        });
      }
    });

    // Sort comments by date, newest first
    comments.sort((a, b) => b.date - a.date);

    // Create the simplified container
    const container = document.createElement('div');
    container.className = 'pr-simplifier-container';

    // Create toggle button to switch between views
    const toggleBtn = document.createElement('button');
    toggleBtn.className = 'pr-simplifier-toggle btn btn-sm';
    toggleBtn.innerHTML = 'Show Original View';
    toggleBtn.onclick = toggleView;

    // Create the header section with CI status and merge
    const headerSection = document.createElement('div');
    headerSection.className = 'pr-simplifier-header';

    // Extract and clone the merge/CI section
    const mergeSection = document.querySelector('.js-merge-group, .merge-message, #partial-pull-merging');
    const branchActions = document.querySelector('.branch-action-item, .js-branch-action-container, .merge-pr');
    const checksContainer = document.querySelector('.merge-status-list, .js-merge-status-list');

    if (mergeSection) {
      const mergeClone = mergeSection.cloneNode(true);
      headerSection.appendChild(mergeClone);
    } else if (branchActions) {
      const branchClone = branchActions.cloneNode(true);
      headerSection.appendChild(branchClone);
    }

    // Also try to get the specific merge box
    const specificMergeBox = document.querySelector('.js-merge-box, .merge-message');
    if (specificMergeBox && !headerSection.querySelector('.js-merge-box, .merge-message')) {
      headerSection.appendChild(specificMergeBox.cloneNode(true));
    }

    // Create tabs container
    const tabsContainer = document.createElement('div');
    tabsContainer.className = 'pr-simplifier-tabs';

    // Create tab navigation
    const tabNav = document.createElement('div');
    tabNav.className = 'pr-simplifier-tab-nav';

    // Create tab content area
    const tabContent = document.createElement('div');
    tabContent.className = 'pr-simplifier-tab-content';

    // Build tabs for each comment (newest first, stacked)
    comments.forEach((comment, idx) => {
      // Create tab button
      const tabBtn = document.createElement('button');
      tabBtn.className = 'pr-simplifier-tab-btn' + (idx === 0 ? ' active' : '');
      tabBtn.dataset.tabIndex = idx;

      const authorSpan = document.createElement('span');
      authorSpan.className = 'tab-author' + (comment.isBot ? ' is-bot' : '');
      authorSpan.textContent = comment.author;

      const timeSpan = document.createElement('span');
      timeSpan.className = 'tab-time';
      timeSpan.textContent = formatTimeAgo(comment.date);

      tabBtn.appendChild(authorSpan);
      tabBtn.appendChild(timeSpan);
      tabBtn.onclick = () => switchTab(idx);

      tabNav.appendChild(tabBtn);

      // Create tab content panel
      const tabPanel = document.createElement('div');
      tabPanel.className = 'pr-simplifier-tab-panel' + (idx === 0 ? ' active' : '');
      tabPanel.dataset.tabIndex = idx;
      tabPanel.appendChild(comment.element);

      tabContent.appendChild(tabPanel);
    });

    // If no comments, show a message
    if (comments.length === 0) {
      const noComments = document.createElement('div');
      noComments.className = 'pr-simplifier-no-comments';
      noComments.textContent = 'No comments yet';
      tabContent.appendChild(noComments);
    }

    tabsContainer.appendChild(tabNav);
    tabsContainer.appendChild(tabContent);

    // Assemble the container
    container.appendChild(toggleBtn);
    container.appendChild(headerSection);
    container.appendChild(tabsContainer);

    // Save original state and hide original content
    originalState = {
      discussionDisplay: discussion.style.display
    };
    discussion.style.display = 'none';
    discussion.dataset.prSimplifierHidden = 'true';

    // Insert our simplified view
    discussion.parentNode.insertBefore(container, discussion);

    isSimplified = true;
  }

  function switchTab(index) {
    // Update tab buttons
    document.querySelectorAll('.pr-simplifier-tab-btn').forEach(btn => {
      btn.classList.toggle('active', parseInt(btn.dataset.tabIndex) === index);
    });

    // Update tab panels
    document.querySelectorAll('.pr-simplifier-tab-panel').forEach(panel => {
      panel.classList.toggle('active', parseInt(panel.dataset.tabIndex) === index);
    });
  }

  function toggleView() {
    const container = document.querySelector('.pr-simplifier-container');
    const discussion = document.querySelector('.js-discussion');
    const toggleBtn = document.querySelector('.pr-simplifier-toggle');

    if (isSimplified) {
      // Show original
      container.querySelector('.pr-simplifier-header').style.display = 'none';
      container.querySelector('.pr-simplifier-tabs').style.display = 'none';
      discussion.style.display = '';
      toggleBtn.textContent = 'Show Simplified View';
      isSimplified = false;
    } else {
      // Show simplified
      container.querySelector('.pr-simplifier-header').style.display = '';
      container.querySelector('.pr-simplifier-tabs').style.display = '';
      discussion.style.display = 'none';
      toggleBtn.textContent = 'Show Original View';
      isSimplified = true;
    }
  }

  function formatTimeAgo(date) {
    if (!date || date.getTime() === 0) return '';

    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  // Initialize
  init();
})();
