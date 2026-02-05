/**
 * Claude-Style UI JavaScript Utilities
 * Feature: 008-claude-ui-redesign
 *
 * Handles:
 * - Code copy buttons
 * - Theme switching with localStorage
 * - Sidebar collapse state
 * - Message animations
 */

(function() {
    'use strict';

    // ============================================
    // Constants
    // ============================================
    const STORAGE_KEYS = {
        THEME: 'mits_theme',
        SIDEBAR: 'mits_sidebar_collapsed',
        PREFERENCES: 'mits_preferences'
    };

    const COPY_TIMEOUT = 1500; // ms

    // ============================================
    // Theme Management
    // ============================================

    /**
     * Get current theme from localStorage
     * @returns {string} 'dark' or 'light'
     */
    function getTheme() {
        return localStorage.getItem(STORAGE_KEYS.THEME) || 'dark';
    }

    /**
     * Set theme and persist to localStorage
     * @param {string} theme - 'dark' or 'light'
     */
    function setTheme(theme) {
        const validThemes = ['dark', 'light'];
        if (!validThemes.includes(theme)) {
            console.warn(`Invalid theme: ${theme}. Using 'dark'.`);
            theme = 'dark';
        }

        localStorage.setItem(STORAGE_KEYS.THEME, theme);
        document.documentElement.setAttribute('data-theme', theme);

        // Update preferences object
        const prefs = getPreferences();
        prefs.theme = theme;
        savePreferences(prefs);

        // Dispatch event for Gradio to pick up
        document.dispatchEvent(new CustomEvent('mits-theme-changed', {
            detail: { theme }
        }));
    }

    /**
     * Toggle between dark and light themes
     * @returns {string} New theme
     */
    function toggleTheme() {
        const current = getTheme();
        const newTheme = current === 'dark' ? 'light' : 'dark';
        setTheme(newTheme);
        return newTheme;
    }

    /**
     * Apply saved theme on page load
     */
    function applyStoredTheme() {
        const theme = getTheme();
        document.documentElement.setAttribute('data-theme', theme);
    }

    // ============================================
    // Sidebar Management
    // ============================================

    /**
     * Get sidebar collapsed state from localStorage
     * @returns {boolean}
     */
    function getSidebarCollapsed() {
        return localStorage.getItem(STORAGE_KEYS.SIDEBAR) === 'true';
    }

    /**
     * Set sidebar collapsed state
     * @param {boolean} collapsed
     */
    function setSidebarCollapsed(collapsed) {
        localStorage.setItem(STORAGE_KEYS.SIDEBAR, collapsed.toString());

        // Update preferences object
        const prefs = getPreferences();
        prefs.sidebarCollapsed = collapsed;
        savePreferences(prefs);

        // Update DOM
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.toggle('collapsed', collapsed);
        }

        // Dispatch event
        document.dispatchEvent(new CustomEvent('mits-sidebar-changed', {
            detail: { collapsed }
        }));
    }

    /**
     * Toggle sidebar collapsed state
     * @returns {boolean} New collapsed state
     */
    function toggleSidebar() {
        const collapsed = !getSidebarCollapsed();
        setSidebarCollapsed(collapsed);
        return collapsed;
    }

    // ============================================
    // Preferences Management
    // ============================================

    /**
     * Get all preferences from localStorage
     * @returns {Object}
     */
    function getPreferences() {
        try {
            const stored = localStorage.getItem(STORAGE_KEYS.PREFERENCES);
            return stored ? JSON.parse(stored) : getDefaultPreferences();
        } catch (e) {
            console.warn('Failed to parse preferences:', e);
            return getDefaultPreferences();
        }
    }

    /**
     * Get default preferences
     * @returns {Object}
     */
    function getDefaultPreferences() {
        return {
            theme: 'dark',
            sidebarCollapsed: false,
            streamingEnabled: true,
            showThinking: true
        };
    }

    /**
     * Save preferences to localStorage
     * @param {Object} prefs
     */
    function savePreferences(prefs) {
        try {
            localStorage.setItem(STORAGE_KEYS.PREFERENCES, JSON.stringify(prefs));
        } catch (e) {
            console.warn('Failed to save preferences:', e);
        }
    }

    // ============================================
    // Code Copy Button
    // ============================================

    /**
     * Add copy buttons to all code blocks
     */
    function addCopyButtons() {
        const codeBlocks = document.querySelectorAll('.chatbot pre:not(.has-copy-btn)');

        codeBlocks.forEach(pre => {
            pre.classList.add('has-copy-btn');

            // Create wrapper if needed
            let wrapper = pre.parentElement;
            if (!wrapper.classList.contains('code-block-wrapper')) {
                wrapper = document.createElement('div');
                wrapper.className = 'code-block-wrapper';
                pre.parentNode.insertBefore(wrapper, pre);
                wrapper.appendChild(pre);
            }

            // Create copy button
            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-button';
            copyBtn.textContent = 'Копировать';
            copyBtn.setAttribute('aria-label', 'Копировать код');

            copyBtn.addEventListener('click', async () => {
                const code = pre.querySelector('code');
                const text = code ? code.textContent : pre.textContent;

                try {
                    await navigator.clipboard.writeText(text);

                    // Show confirmation
                    copyBtn.textContent = 'Скопировано!';
                    copyBtn.classList.add('copied');

                    setTimeout(() => {
                        copyBtn.textContent = 'Копировать';
                        copyBtn.classList.remove('copied');
                    }, COPY_TIMEOUT);

                } catch (err) {
                    console.error('Failed to copy:', err);
                    copyBtn.textContent = 'Ошибка';

                    setTimeout(() => {
                        copyBtn.textContent = 'Копировать';
                    }, COPY_TIMEOUT);
                }
            });

            wrapper.appendChild(copyBtn);
        });
    }

    // ============================================
    // Message Animation
    // ============================================

    /**
     * Observe and animate new messages
     */
    function setupMessageObserver() {
        const chatContainer = document.querySelector('.chatbot');
        if (!chatContainer) return;

        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // Animate new messages
                        if (node.classList && node.classList.contains('message')) {
                            node.style.animation = 'none';
                            node.offsetHeight; // Trigger reflow
                            node.style.animation = '';
                        }

                        // Add copy buttons to new code blocks
                        addCopyButtons();
                    }
                });
            });
        });

        observer.observe(chatContainer, {
            childList: true,
            subtree: true
        });
    }

    // ============================================
    // Initialization
    // ============================================

    /**
     * Initialize all UI enhancements
     */
    function init() {
        // Apply stored theme immediately
        applyStoredTheme();

        // Wait for DOM to be fully loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', onDOMReady);
        } else {
            onDOMReady();
        }
    }

    /**
     * Called when DOM is ready
     */
    function onDOMReady() {
        // Apply sidebar state
        const collapsed = getSidebarCollapsed();
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.toggle('collapsed', collapsed);
        }

        // Add copy buttons to existing code blocks
        addCopyButtons();

        // Setup mutation observer for new messages
        setupMessageObserver();

        console.log('MITS Claude UI initialized');
    }

    // ============================================
    // Expose API to global scope
    // ============================================

    window.MITS_UI = {
        // Theme
        getTheme,
        setTheme,
        toggleTheme,

        // Sidebar
        getSidebarCollapsed,
        setSidebarCollapsed,
        toggleSidebar,

        // Preferences
        getPreferences,
        savePreferences,

        // Utilities
        addCopyButtons,

        // Re-initialize (for Gradio reloads)
        reinit: onDOMReady
    };

    // Initialize
    init();

})();
