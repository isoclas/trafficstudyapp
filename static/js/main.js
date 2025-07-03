// This prevents variable redeclaration when HTMX reloads the page
(function() {
    document.addEventListener('htmx:afterSwap', function(event) {
        // Only reset accordion state if the swap target is not modal-container or scenarios-container
        const target = event.target;
        const isModalSwap = target && (target.id === 'modal-container' || target.closest('#modal-container'));
        const isScenariosSwap = target && target.classList && target.classList.contains('scenarios-container');
        
        // Skip accordion reset for modal and scenarios container swaps
        if (isModalSwap || isScenariosSwap) {
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
    });
    
    document.addEventListener('DOMContentLoaded', function() {
        initializeDateFilters();
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
    
})(); // Close the IIFE
