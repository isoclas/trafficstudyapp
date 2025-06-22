// This prevents variable redeclaration when HTMX reloads the page
(function() {
    // Add event listener for accordion animation
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
                // Make sure accordion is closed
                accordion.classList.remove('hs-accordion-active');
                
                // Update the content height to 0
                const content = accordion.querySelector('.hs-accordion-content');
                if (content) {
                    content.style.height = '0px';
                }
                
                // Update the toggle button
                const toggle = accordion.querySelector('.hs-accordion-toggle');
                if (toggle) {
                    toggle.setAttribute('aria-expanded', 'false');
                    // Ensure down arrow is shown, up arrow is hidden
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
})(); // Close the IIFE
