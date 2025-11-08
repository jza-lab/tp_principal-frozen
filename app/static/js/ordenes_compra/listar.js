document.addEventListener('DOMContentLoaded', function () {
    // Variables globales
    const searchInput = document.getElementById('searchInput');
    const estadoBtns = document.querySelectorAll('.btn-filter-estado');
    const quickActionBtns = document.querySelectorAll('.btn-quick-action');
    const ordenCards = document.querySelectorAll('.orden-card');
    const btnClearAll = document.getElementById('btnClearAll');
    const visibleCountEl = document.getElementById('visibleCount');
    const totalCountEl = document.getElementById('totalCount');
    const ordenesContainer = document.getElementById('ordenesContainer');
    const noResultsMessage = document.getElementById('noResultsMessage');

    let activeFilters = {
        estado: '',
        search: ''
    };

    // Total de órdenes
    const totalOrdenes = ordenCards.length;
    if (totalCountEl) {
        totalCountEl.textContent = totalOrdenes;
    }
    
    // Función de filtrado del lado del cliente (solo para búsqueda y estado)
    function applyClientFilters() {
        let visibleCount = 0;

        ordenCards.forEach(card => {
            let show = true;

            // Filtro por estado
            if (activeFilters.estado && card.dataset.estado !== activeFilters.estado) {
                show = false;
            }

            // Filtro por búsqueda de código
            if (activeFilters.search) {
                const codigo = card.dataset.codigo.toLowerCase();
                const searchTerm = activeFilters.search.toLowerCase();
                if (!codigo.includes(searchTerm)) {
                    show = false;
                }
            }

            // Mostrar u ocultar
            card.style.display = show ? '' : 'none';
            if (show) {
                visibleCount++;
            }
        });

        // Actualizar contador
        if (visibleCountEl) {
            visibleCountEl.textContent = visibleCount;
        }

        // Mostrar mensaje si no hay resultados
        const hasResults = visibleCount > 0;
        if (ordenesContainer) {
            ordenesContainer.style.display = hasResults ? '' : 'none';
        }
        if (noResultsMessage) {
            noResultsMessage.style.display = hasResults ? 'none' : 'flex';
        }

        // Mostrar/ocultar botón de limpiar filtros (solo para filtros de cliente)
        const hasActiveClientFilters = activeFilters.estado || activeFilters.search;
        if (btnClearAll) {
           // Se muestra si hay cualquier filtro activo, cliente o servidor
           const urlParams = new URLSearchParams(window.location.search);
           btnClearAll.style.display = (hasActiveClientFilters || urlParams.has('filtro') || urlParams.has('rango_fecha')) ? 'block' : 'none';
        }
    }

    // Event listeners para botones de estado (filtrado en cliente)
    estadoBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            estadoBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            activeFilters.estado = this.dataset.estado;
            applyClientFilters();
        });
    });

    // Event listener para búsqueda (filtrado en cliente)
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function () {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                activeFilters.search = this.value.trim();
                applyClientFilters();
            }, 300);
        });
    }

    // Event listeners para filtros rápidos (recarga de página)
    quickActionBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            const filter = this.dataset.quickFilter;
            const currentUrl = new URL(window.location.href);
            const isActive = this.classList.contains('active');

            let paramName, paramValue;
            if (filter === 'mis-ordenes') {
                paramName = 'filtro';
                paramValue = 'mis_ordenes';
            } else {
                paramName = 'rango_fecha';
                paramValue = filter;
            }

            // Limpiar filtros de URL para evitar conflictos
            currentUrl.searchParams.delete('filtro');
            currentUrl.searchParams.delete('rango_fecha');

            if (!isActive) {
                // Si no estaba activo, lo activamos y establecemos el parámetro
                currentUrl.searchParams.set(paramName, paramValue);
            }
            // Si estaba activo, al limpiarlo arriba ya es suficiente para desactivarlo.

            window.location.href = currentUrl.toString();
        });
    });

    // Al cargar la página, marcar como activo el botón de filtro rápido si el parámetro está en la URL
    const urlParams = new URLSearchParams(window.location.search);
    const fechaFilter = urlParams.get('rango_fecha');
    const misOrdenesFilter = urlParams.get('filtro');

    quickActionBtns.forEach(btn => {
        const quickFilter = btn.dataset.quickFilter;
        if ((quickFilter === fechaFilter) || (quickFilter === 'mis-ordenes' && misOrdenesFilter === 'mis_ordenes')) {
            btn.classList.add('active');
        }
    });

    // Limpiar todos los filtros (cliente y servidor)
    if (btnClearAll) {
        btnClearAll.addEventListener('click', function () {
            // Redirige a la URL base sin parámetros de consulta
            window.location.href = window.location.origin + window.location.pathname;
        });
    }

    // Aplicar filtros de cliente al cargar la página por si el usuario vuelve con el historial
    applyClientFilters();
});
