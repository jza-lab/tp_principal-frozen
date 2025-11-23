document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    const sortSelect = document.getElementById('sortSelect');
    const tableBody = document.getElementById('costosTableBody');
    const noResultsMessage = document.getElementById('noResultsMessage');
    const noRowsMessage = document.getElementById('noRowsMessage');

    // Get all initial rows. We convert the NodeList to an Array for easier sorting.
    let rows = Array.from(tableBody.querySelectorAll('tr.costo-row'));

    // --- Search Logic ---
    function filterRows() {
        const query = searchInput.value.toLowerCase().trim();
        let visibleCount = 0;

        rows.forEach(row => {
            const nombre = row.getAttribute('data-nombre').toLowerCase();
            const tipo = row.getAttribute('data-tipo').toLowerCase();
            
            // Check if query matches name or type
            if (nombre.includes(query) || tipo.includes(query)) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        // Toggle "No results" message
        if (visibleCount === 0 && rows.length > 0) {
            noResultsMessage.style.display = 'block';
        } else {
            noResultsMessage.style.display = 'none';
        }
    }

    searchInput.addEventListener('input', filterRows);

    // --- Sort Logic ---
    function sortRows() {
        const sortValue = sortSelect.value;
        if (!sortValue) return; // Do nothing if placeholder is selected

        const [criteria, order] = sortValue.split('_'); // e.g. ['nombre', 'asc']

        // Sort the array of rows
        rows.sort((a, b) => {
            const activoA = a.getAttribute('data-activo') === '1';
            const activoB = b.getAttribute('data-activo') === '1';

            // 1. Primary Rule: Inactive items always go to the bottom
            if (activoA && !activoB) return -1; // A is active, B is inactive -> A comes first
            if (!activoA && activoB) return 1;  // A is inactive, B is active -> B comes first
            
            // If both have same active status (both active or both inactive), apply secondary sort
            
            let valA, valB;

            if (criteria === 'nombre') {
                valA = a.getAttribute('data-nombre').toLowerCase();
                valB = b.getAttribute('data-nombre').toLowerCase();
                
                // String comparison
                if (valA < valB) return order === 'asc' ? -1 : 1;
                if (valA > valB) return order === 'asc' ? 1 : -1;
                return 0;

            } else if (criteria === 'monto') {
                valA = parseFloat(a.getAttribute('data-monto'));
                valB = parseFloat(b.getAttribute('data-monto'));

                // Number comparison
                return order === 'asc' ? valA - valB : valB - valA;
            }
            return 0;
        });

        // Re-append rows to table body in the new order
        // This moves them in the DOM without destroying event listeners
        rows.forEach(row => tableBody.appendChild(row));
    }

    sortSelect.addEventListener('change', sortRows);

    // Initial check: if there are rows, ensure they are sorted correctly by default if needed.
    // However, the user request implies they want to control it. 
    // But since the user said "ultimos siempre los inhabilitados", we should perhaps apply that rule immediately?
    // The server-side rendering usually puts them in insertion order. 
    // Let's run a default sort to ensure inactives are at the bottom right away, 
    // preserving the server's order for the actives unless a sort option is pre-selected.
    // For now, we will just listen to the user interaction as per the plan.
    // If the server didn't sort them with inactives last, this JS will only fix it when the user picks a sort option.
    // Let's force an initial sort if the user wants "ultimos siempre los inhabilitados" to be a hard rule.
    // But without a selected option, how do we sort the actives? 
    // Let's just leave it to user interaction to start with, or maybe default to 'nombre_asc' if desired.
    // The requirement says "quiero q salgan ordenados". This implies a default state.
    // I will trigger a default sort by Name ASC.
    
    if (rows.length > 0) {
        sortSelect.value = 'nombre_asc';
        sortRows();
    }
});
