// This prevents variable redeclaration when HTMX reloads the page
(function() {
    document.addEventListener('htmx:afterSwap', function(event) {
        // Only reset accordion state if the swap target is not modal-container, scenarios-container, or table-container
        const target = event.target;
        const isModalSwap = target && (target.id === 'modal-container' || target.closest('#modal-container'));
        const isScenariosSwap = target && target.classList && target.classList.contains('scenarios-container');
        const isTableSwap = target && target.classList && target.classList.contains('table-container');
        
        // Skip accordion reset for modal, scenarios container, and table container swaps
        if (isModalSwap || isScenariosSwap || isTableSwap) {
            return;
        }
        
        // Add a small delay to allow the DOM to update
        setTimeout(function() {
            // Ensure all accordions are closed by default
            document.querySelectorAll('.hs-accordion').forEach(function(accordion) {
                accordion.classList.remove('hs-accordion-active');

                const content = accordion.querySelector('.hs-accordion-content');
                if (content) {
                    content.style.height = '0px';
                }

                const toggle = accordion.querySelector('.hs-accordion-toggle');
                if (toggle) {
                    toggle.setAttribute('aria-expanded', 'false');
                    const downIcon = toggle.querySelector('.accordion-icon-down');
                    const upIcon = toggle.querySelector('.accordion-icon-up');
                    if (downIcon && upIcon) {
                        downIcon.classList.remove('hidden');
                        downIcon.classList.add('block');
                        upIcon.classList.remove('block');
                        upIcon.classList.add('hidden');
                    }
                }
            });
        }, 100);
    });
    
    document.addEventListener('htmx:afterSwap', function(event) {
        initializeDateFilters();
        initializeSortable();
    });
    
    document.addEventListener('DOMContentLoaded', function() {
        initializeDateFilters();
        initializeSortable();
    });
    
    function initializeDateFilters() {
        // Handle date filter radio button changes
        document.querySelectorAll('input[name="date-filter"]').forEach(function(radio) {
            radio.addEventListener('change', function() {
                if (this.checked) {
                    const selectedText = this.nextElementSibling.textContent;
                    const buttonText = document.getElementById('selected-filter-text');
                    if (buttonText) {
                        buttonText.textContent = selectedText;
                    }
                    const dropdown = document.getElementById('dropdownRadio');
                    if (dropdown) {
                        dropdown.classList.add('hidden');
                    }
                }
            });
        });
    }
    
    function initializeSortable() {
        // Initialize Sortable.js for scenario tables
        var sortables = document.querySelectorAll(".sortable");
        for (var i = 0; i < sortables.length; i++) {
            var sortable = sortables[i];
            var sortableInstance = new Sortable(sortable.querySelector('tbody') || sortable, {
                animation: 150,
                ghostClass: 'opacity-50',
                handle: '.drag-handle', // Only allow dragging by the handle
                
                // Make the `.htmx-indicator` unsortable
                filter: ".htmx-indicator",
                onMove: function (evt) {
                    return evt.related.className.indexOf('htmx-indicator') === -1;
                },
                
                // Disable sorting on the `end` event
                onEnd: function (evt) {
                    this.option("disabled", true);
                }
            });
            
            // Re-enable sorting on the `htmx:afterSwap` event
            sortable.addEventListener("htmx:afterSwap", function() {
                sortableInstance.option("disabled", false);
            });
        }
    }
    
})(); // Close the IIFE
