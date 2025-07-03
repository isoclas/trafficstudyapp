function toggleTripDistCount() {
    const tripDistCheckbox = document.getElementById('include_trip_dist');
    const tripDistCountContainer = document.getElementById('trip_dist_count_container');

    if (!tripDistCheckbox || !tripDistCountContainer) {
        return;
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

    if (!tripAssignCheckbox || !tripAssignCountContainer) {
        return;
    }

    if (tripAssignCheckbox.checked) {
        tripAssignCountContainer.style.display = 'block';
    } else {
        tripAssignCountContainer.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    toggleTripDistCount();
    toggleTripAssignCount();
});

document.addEventListener('htmx:afterSwap', function(event) {
    setTimeout(function() {
        toggleTripDistCount();
        toggleTripAssignCount();
    }, 10);
});

document.addEventListener('htmx:load', function(event) {
    toggleTripDistCount();
    toggleTripAssignCount();
});
