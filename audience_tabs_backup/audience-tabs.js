/**
 * Audience-Based Product Description Tabs
 * Handles tab switching and keyboard navigation
 */

(function() {
  'use strict';

  // Initialize audience tabs
  function initAudienceTabs() {
    const tabsContainer = document.querySelector('[data-audience-tabs]');
    if (!tabsContainer) return;

    const buttons = tabsContainer.querySelectorAll('.audience-tabs__button');
    const panels = tabsContainer.querySelectorAll('.audience-tabs__panel');

    // Handle tab click
    buttons.forEach(function(button) {
      button.addEventListener('click', function() {
        const targetTab = this.getAttribute('data-tab');

        // Update buttons
        buttons.forEach(function(btn) {
          btn.classList.remove('audience-tabs__button--active');
          btn.setAttribute('aria-selected', 'false');
        });
        this.classList.add('audience-tabs__button--active');
        this.setAttribute('aria-selected', 'true');

        // Update panels
        panels.forEach(function(panel) {
          if (panel.id === 'panel-' + targetTab) {
            panel.classList.add('audience-tabs__panel--active');
            panel.removeAttribute('hidden');
            panel.focus();
          } else {
            panel.classList.remove('audience-tabs__panel--active');
            panel.setAttribute('hidden', '');
          }
        });
      });

      // Keyboard navigation
      button.addEventListener('keydown', function(e) {
        const currentIndex = Array.from(buttons).indexOf(this);
        let targetIndex;

        if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
          e.preventDefault();
          targetIndex = currentIndex === 0 ? buttons.length - 1 : currentIndex - 1;
        } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
          e.preventDefault();
          targetIndex = currentIndex === buttons.length - 1 ? 0 : currentIndex + 1;
        } else if (e.key === 'Home') {
          e.preventDefault();
          targetIndex = 0;
        } else if (e.key === 'End') {
          e.preventDefault();
          targetIndex = buttons.length - 1;
        }

        if (targetIndex !== undefined) {
          buttons[targetIndex].click();
          buttons[targetIndex].focus();
        }
      });
    });
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAudienceTabs);
  } else {
    initAudienceTabs();
  }

  // Re-initialize if page content changes (for dynamic themes)
  if (window.MutationObserver) {
    const observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        if (mutation.addedNodes.length) {
          initAudienceTabs();
        }
      });
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }
})();
