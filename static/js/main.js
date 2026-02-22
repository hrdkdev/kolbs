/**
 * Kolb's Learning Cycle - Main JavaScript
 * Minimal vanilla JS for autosave, accordions, keyboard shortcuts
 */

(function() {
    'use strict';

    // Configuration
    const AUTOSAVE_DELAY = 1500; // ms
    let autosaveTimer = null;
    let lastSavedData = null;

    // ==========================================
    // Utility functions
    // ==========================================

    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    function showSaveStatus(status, message) {
        const indicator = document.getElementById('save-indicator');
        const statusEl = document.getElementById('save-status');
        if (!indicator || !statusEl) return;

        indicator.className = 'save-indicator ' + status;
        statusEl.textContent = message;

        if (status === 'saved') {
            setTimeout(() => {
                statusEl.textContent = 'Saved ' + new Date().toLocaleTimeString();
            }, 1000);
        }
    }

    // ==========================================
    // Autosave functionality
    // ==========================================

    function getFormData() {
        const form = document.getElementById('entry-form');
        if (!form) return null;

        const formData = new FormData(form);
        const data = {};
        
        formData.forEach((value, key) => {
            if (key === 'tags') {
                data.tags = value.split(',').map(t => t.trim()).filter(t => t);
            } else if (key === 'no_experiment_needed') {
                data.no_experiment_needed = true;
            } else if (key !== 'action' && key !== 'next_step') {
                data[key] = value;
            }
        });

        // Handle unchecked checkboxes
        if (!formData.has('no_experiment_needed')) {
            data.no_experiment_needed = false;
        }

        // Collect reflection prompt responses
        const reflectionPrompts = {};
        document.querySelectorAll('#step-2 .prompt-textarea[data-prompt-name]').forEach(textarea => {
            const promptName = textarea.getAttribute('data-prompt-name');
            if (promptName && textarea.value.trim()) {
                reflectionPrompts[promptName] = textarea.value;
            }
        });
        data.reflection_prompts = reflectionPrompts;

        // Collect abstraction prompt responses
        const abstractionPrompts = {};
        document.querySelectorAll('#step-3 .prompt-textarea[data-prompt-name]').forEach(textarea => {
            const promptName = textarea.getAttribute('data-prompt-name');
            if (promptName && textarea.value.trim()) {
                abstractionPrompts[promptName] = textarea.value;
            }
        });
        data.abstraction_prompts = abstractionPrompts;

        return data;
    }

    function hasDataChanged(newData) {
        if (!lastSavedData) return true;
        return JSON.stringify(newData) !== JSON.stringify(lastSavedData);
    }

    async function autosave() {
        // Check if we're on an entry page and autosave is enabled
        if (typeof entryId === 'undefined' || entryId === null) return;
        if (typeof autosaveEnabled !== 'undefined' && !autosaveEnabled) return;
        if (typeof isNew !== 'undefined' && isNew) return;

        const data = getFormData();
        if (!data || !hasDataChanged(data)) return;

        showSaveStatus('saving', 'Saving...');

        try {
            const response = await fetch(`/api/entry/${entryId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                lastSavedData = data;
                showSaveStatus('saved', 'Saved');
                
                // Update completion indicator if present
                if (result.entry && result.entry.completion !== undefined) {
                    updateCompletionDisplay(result.entry.completion);
                }
            } else {
                showSaveStatus('error', 'Save failed');
                console.error('Autosave failed:', result.error);
            }
        } catch (error) {
            showSaveStatus('error', 'Save failed');
            console.error('Autosave error:', error);
        }
    }

    function updateCompletionDisplay(completion) {
        const chip = document.querySelector('.chip-draft, .chip-complete');
        if (chip && chip.classList.contains('chip-draft')) {
            chip.textContent = `Draft - ${completion}%`;
        }
    }

    function scheduleAutosave() {
        if (autosaveTimer) {
            clearTimeout(autosaveTimer);
        }
        autosaveTimer = setTimeout(autosave, AUTOSAVE_DELAY);
    }

    function initAutosave() {
        const form = document.getElementById('entry-form');
        if (!form) return;

        // Store initial data
        lastSavedData = getFormData();

        // Listen for changes on all form fields
        form.querySelectorAll('input, textarea, select').forEach(el => {
            el.addEventListener('input', scheduleAutosave);
            el.addEventListener('change', scheduleAutosave);
        });

        // Auto-expand prompt blocks that have content
        document.querySelectorAll('.prompt-textarea[data-prompt-name]').forEach(textarea => {
            if (textarea.value.trim()) {
                const promptBlock = textarea.closest('.prompt-block');
                if (promptBlock) {
                    promptBlock.classList.add('open');
                    const checkbox = promptBlock.querySelector('.prompt-check');
                    if (checkbox) checkbox.checked = true;
                }
            }
        });
    }

    // ==========================================
    // Accordion functionality
    // ==========================================

    window.toggleAccordion = function(id) {
        const item = document.getElementById(id);
        if (!item) return;

        const wasOpen = item.classList.contains('open');
        
        // Close all accordions in the same container
        const container = item.closest('.accordion');
        if (container) {
            container.querySelectorAll('.accordion-item').forEach(acc => {
                acc.classList.remove('open');
            });
        }

        // Open the clicked one (unless it was already open)
        if (!wasOpen) {
            item.classList.add('open');
        }
    };

    // ==========================================
    // Prompt block functionality
    // ==========================================

    window.togglePrompt = function(block) {
        block.classList.toggle('open');
        const checkbox = block.querySelector('.prompt-check');
        if (checkbox) {
            checkbox.checked = block.classList.contains('open');
        }
    };

    // ==========================================
    // Distraction-free mode
    // ==========================================

    window.toggleDistractionFree = function() {
        document.body.classList.toggle('distraction-free');
        
        // Store preference in sessionStorage
        const isEnabled = document.body.classList.contains('distraction-free');
        sessionStorage.setItem('distractionFree', isEnabled);
    };

    function restoreDistractionFreeMode() {
        if (sessionStorage.getItem('distractionFree') === 'true') {
            document.body.classList.add('distraction-free');
        }
    }

    // ==========================================
    // Keyboard shortcuts
    // ==========================================

    function initKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            // Ctrl/Cmd + S: Save
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                const form = document.getElementById('entry-form');
                if (form) {
                    // Trigger immediate autosave
                    autosave();
                }
            }

            // Ctrl/Cmd + Enter: Next step (wizard mode)
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                const nextBtn = document.querySelector('button[name="next_step"]');
                if (nextBtn) {
                    e.preventDefault();
                    nextBtn.click();
                }
            }

            // / : Focus search (when not in input)
            if (e.key === '/' && !isInputFocused()) {
                const searchInput = document.getElementById('search-input');
                if (searchInput) {
                    e.preventDefault();
                    searchInput.focus();
                }
            }

            // Escape: Exit focus mode / close modals
            if (e.key === 'Escape') {
                // Close modals
                const modal = document.getElementById('exp-modal');
                if (modal && !modal.classList.contains('hidden')) {
                    closeExpModal();
                    return;
                }

                // Exit distraction-free mode
                if (document.body.classList.contains('distraction-free')) {
                    document.body.classList.remove('distraction-free');
                    sessionStorage.removeItem('distractionFree');
                }
            }
        });
    }

    function isInputFocused() {
        const active = document.activeElement;
        return active && (
            active.tagName === 'INPUT' ||
            active.tagName === 'TEXTAREA' ||
            active.tagName === 'SELECT' ||
            active.isContentEditable
        );
    }

    // ==========================================
    // Flash messages auto-dismiss
    // ==========================================

    function initFlashMessages() {
        const messages = document.querySelectorAll('.flash-message');
        messages.forEach((msg, index) => {
            setTimeout(() => {
                msg.style.animation = 'slideIn 0.3s ease reverse';
                setTimeout(() => msg.remove(), 300);
            }, 5000 + (index * 500));
        });
    }

    // ==========================================
    // Form validation helpers
    // ==========================================

    function initFormValidation() {
        // Experiment specificity warning
        const expTextarea = document.getElementById('new_exp_text');
        const expWarning = document.getElementById('exp-warning');
        
        if (expTextarea && expWarning) {
            expTextarea.addEventListener('input', debounce(function() {
                const text = this.value.toLowerCase();
                const vaguePhrases = ['try harder', 'do better', 'be more', 'work on', 'improve', 'focus more'];
                const isVague = vaguePhrases.some(p => text.includes(p)) && text.split(' ').length < 8;
                
                if (isVague) {
                    expWarning.textContent = 'Consider being more specific. What exactly will you do?';
                    expWarning.className = 'form-hint text-warning';
                } else {
                    expWarning.textContent = '';
                    expWarning.className = 'form-hint';
                }
            }, 500));
        }
    }

    // ==========================================
    // Search highlighting (optional enhancement)
    // ==========================================

    function highlightSearchTerms() {
        const params = new URLSearchParams(window.location.search);
        const searchTerm = params.get('search');
        
        if (!searchTerm || searchTerm.length < 2) return;

        const regex = new RegExp(`(${escapeRegex(searchTerm)})`, 'gi');
        
        document.querySelectorAll('.entry-item-text, .experiment-item-text').forEach(el => {
            const text = el.innerHTML;
            el.innerHTML = text.replace(regex, '<mark>$1</mark>');
        });
    }

    function escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // ==========================================
    // Initialize everything
    // ==========================================

    function init() {
        restoreDistractionFreeMode();
        initKeyboardShortcuts();
        initFlashMessages();
        initAutosave();
        initFormValidation();
        highlightSearchTerms();
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
