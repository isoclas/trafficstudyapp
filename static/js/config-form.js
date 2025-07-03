// This function needs to remain in JavaScript as it's handling dynamic UI behavior
function toggleTripDistCount() {
    const tripDistCheckbox = document.getElementById('include_trip_dist');
    const tripDistCountContainer = document.getElementById('trip_dist_count_container');

    // Check if both elements exist before proceeding
    if (!tripDistCheckbox || !tripDistCountContainer) {
        return; // Exit the function if elements don't exist
    }

    if (tripDistCheckbox.checked) {
        tripDistCountContainer.style.display = 'block';
    } else {
        tripDistCountContainer.style.display = 'none';
    }
}

function toggleTripAssignCount() {
    const tripAssignCheckbox = document.getElementById('include_trip_assign');
    const tripAssignCountContainer = document.getElementById('trip_assign_count_container');

    // Check if both elements exist before proceeding
    if (!tripAssignCheckbox || !tripAssignCountContainer) {
        return; // Exit the function if elements don't exist
    }

    if (tripAssignCheckbox.checked) {
        tripAssignCountContainer.style.display = 'block';
    } else {
        tripAssignCountContainer.style.display = 'none';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    toggleTripDistCount();
    toggleTripAssignCount();
});

// Also initialize after HTMX swaps
document.addEventListener('htmx:afterSwap', function(event) {
    // Small delay to ensure DOM is updated
    setTimeout(function() {
        toggleTripDistCount();
        toggleTripAssignCount();
    }, 10);
});

// Also initialize after HTMX loads content
document.addEventListener('htmx:load', function(event) {
    toggleTripDistCount();
    toggleTripAssignCount();
});
