const EmpleadosPanel = (function() {
    // --- ELEMENTOS DEL DOM (privados) ---
    let searchInput;
    let clearSearchBtn;
    let allUsersContainer;
    let userCards;
    let noSearchResults;
    let filterButtons;
    
    let currentFilter = 'all';

    // --- FUNCIONES (privadas) ---

    // Lógica de habilitar/inhabilitar usuario (movida desde habilitarUsuario.js)
    function showConfirmationModal(title, body, onConfirm, confirmButtonClass = 'primary') {
        const confirmationModal = new bootstrap.Modal(document.getElementById('confirmationModal'));
        document.getElementById('confirmationModalLabel').textContent = title;
        document.getElementById('confirmationModalText').innerHTML = body;

        const confirmBtn = document.getElementById('confirmActionBtn');
        confirmBtn.className = `btn btn-${confirmButtonClass}`; // Reset and apply class
        confirmBtn.textContent = title.split(' ')[1]; // "Habilitación" -> "Habilitar"

        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

        newConfirmBtn.addEventListener('click', () => {
            onConfirm();
            confirmationModal.hide();
        }, { once: true });

        confirmationModal.show();
    }

    function handleUserAction(url, successMessage, errorMessage, actionVerb) {
        fetch(url, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(response => response.json().then(data => ({ ok: response.ok, data })))
        .then(({ ok, data }) => {
            if (ok && data.success) {
                // Podríamos mostrar un flash message en lugar de recargar
                window.location.reload();
            } else {
                showConfirmationModal('Error', data.error || errorMessage, () => {}, 'danger');
            }
        })
        .catch(error => {
            console.error(`Error en la ${actionVerb}:`, error);
            showConfirmationModal('Error', `Ocurrió un error de red al intentar ${actionVerb.toLowerCase()} el usuario.`, () => {}, 'danger');
        });
    }

    function updateUserCounts() {
        const all = userCards.length;
        let active = 0;
        let inactive = 0;
        
        userCards.forEach(card => {
            if (card.dataset.status === 'active') active++;
            else inactive++;
        });
        
        document.getElementById('count-all').textContent = all;
        document.getElementById('count-active').textContent = active;
        document.getElementById('count-inactive').textContent = inactive;
    }

    function filterAndSearch() {
        const searchTerm = searchInput.value.toLowerCase().trim();
        let visibleCount = 0;

        userCards.forEach(card => {
            const legajo = card.dataset.legajo.toLowerCase();
            const nombre = card.dataset.nombre.toLowerCase();
            const status = card.dataset.status;

            const matchesSearch = legajo.includes(searchTerm) || nombre.includes(searchTerm);
            const matchesFilter = currentFilter === 'all' || status === currentFilter;

            if (matchesSearch && matchesFilter) {
                card.style.display = '';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        noSearchResults.style.display = (visibleCount === 0 && searchTerm) ? 'flex' : 'none';
        allUsersContainer.style.display = (visibleCount === 0 && searchTerm) ? 'none' : 'flex';
        clearSearchBtn.style.display = searchTerm ? 'flex' : 'none';
    }

    function bindEvents() {
        searchInput.addEventListener('input', filterAndSearch);
        
        clearSearchBtn.addEventListener('click', function() {
            searchInput.value = '';
            filterAndSearch();
            searchInput.focus();
        });

        filterButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                filterButtons.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                currentFilter = this.dataset.filter;
                filterAndSearch();
            });
        });

        // Event delegation para los botones de acción de las tarjetas
        allUsersContainer.addEventListener('click', function(e) {
            const form = e.target.closest('form');
            if (form) {
                e.preventDefault();
                const action = form.action;
                const userId = action.match(/\/(\d+)\//)[1];
                
                if (action.includes('habilitar')) {
                    showConfirmationModal('Confirmar Habilitación', '¿Estás seguro de que quieres habilitar este usuario?', () => {
                        form.submit(); // O usar handleUserAction
                    }, 'success');
                } else if (action.includes('eliminar')) {
                     showConfirmationModal('Confirmar Inhabilitación', '¿Estás seguro de que quieres inhabilitar este usuario?', () => {
                        form.submit();
                    }, 'danger');
                }
            }
        });
    }

    // --- MÉTODO PÚBLICO ---
    function init() {
        // Cachear elementos del DOM
        searchInput = document.getElementById('user-search-input');
        clearSearchBtn = document.getElementById('clear-search');
        allUsersContainer = document.getElementById('all-users-container');
        userCards = allUsersContainer.querySelectorAll('.user-card-wrapper');
        noSearchResults = document.getElementById('no-search-results');
        filterButtons = document.querySelectorAll('.filter-btn');

        if (!allUsersContainer) return; // No hacer nada si el panel no está presente

        // Inicializar
        updateUserCounts();
        bindEvents();
        console.log("Panel de Empleados inicializado.");
    }

    return {
        init: init
    };
})();