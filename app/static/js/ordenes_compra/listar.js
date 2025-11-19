document.addEventListener('DOMContentLoaded', function () {
    // Variables globales
    const searchInput = document.getElementById('searchInput');
    const opSearchInput = document.getElementById('opSearchInput');
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
        search: '',
        opSearch: ''
    };

    // Total de órdenes
    const totalOrdenes = ordenCards.length;
    if (totalCountEl) {
        totalCountEl.textContent = totalOrdenes;
    }

    // Función para actualizar las URLs de las acciones con el filtro de estado actual
    function updateActionURLs(estado) {
        const actionForms = document.querySelectorAll('.orden-card form');
        actionForms.forEach(form => {
            if (!form.action) return; // Omitir si no hay URL de acción
            const actionUrl = new URL(form.action, window.location.origin);
            if (estado) {
                actionUrl.searchParams.set('estado', estado);
            } else {
                actionUrl.searchParams.delete('estado');
            }
            form.action = actionUrl.toString();
        });
    }
    
    // Función de filtrado del lado del cliente
    function applyClientFilters() {
        let visibleCount = 0;

        ordenCards.forEach(card => {
            let show = true;

            // Filtro por estado
            if (activeFilters.estado && card.dataset.estado !== activeFilters.estado) {
                show = false;
            }

            // Filtro por búsqueda de OC
            if (activeFilters.search) {
                const codigo = card.dataset.codigo.toLowerCase();
                const searchTerm = activeFilters.search.toLowerCase();
                if (!codigo.includes(searchTerm)) {
                    show = false;
                }
            }

            // Filtro por búsqueda de OP
            if (activeFilters.opSearch) {
                const opCodigo = card.dataset.opCodigo.toLowerCase();
                const opSearchTerm = activeFilters.opSearch.toLowerCase();
                if (!opCodigo.includes(opSearchTerm)) {
                    show = false;
                }
            }

            // Filtro por OP
            if (activeFilters.op && card.dataset.opId !== activeFilters.op) {
                show = false;
            }

            // Mostrar u ocultar tarjeta
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
        if (noResultsMessage) {
            const hasResults = visibleCount > 0;
            if (ordenesContainer) {
                ordenesContainer.style.display = hasResults ? '' : 'none';
            }
            noResultsMessage.style.display = hasResults ? 'none' : 'flex';
        }

        // Control del botón Limpiar Filtros
        const urlParams = new URLSearchParams(window.location.search);
        const hasActiveClientFilters = activeFilters.estado || activeFilters.search;
        if (btnClearAll) {
           btnClearAll.style.display = (hasActiveClientFilters || urlParams.has('filtro') || urlParams.has('rango_fecha') || urlParams.has('estado')) ? 'block' : 'none';
        }
    }

    // Event listeners para botones de estado
    estadoBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            estadoBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            activeFilters.estado = this.dataset.estado;

            // Actualizar URLs de acción y aplicar filtros
            updateActionURLs(activeFilters.estado);
            applyClientFilters();
        });
    });

    // Event listener para búsqueda
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

    // Event listener para búsqueda de OP
    if (opSearchInput) {
        let opSearchTimeout;
        opSearchInput.addEventListener('input', function () {
            clearTimeout(opSearchTimeout);
            opSearchTimeout = setTimeout(() => {
                activeFilters.opSearch = this.value.trim();
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
            
            // Limpiar otros filtros rápidos para evitar conflictos
            currentUrl.searchParams.delete('filtro');
            currentUrl.searchParams.delete('rango_fecha');

            if (!isActive) {
                currentUrl.searchParams.set(paramName, paramValue);
            }

            window.location.href = currentUrl.toString();
        });
    });

    // Al cargar la página, marcar como activo el botón de filtro rápido
    const urlParamsOnLoad = new URLSearchParams(window.location.search);
    const fechaFilter = urlParamsOnLoad.get('rango_fecha');
    const misOrdenesFilter = urlParamsOnLoad.get('filtro');

    quickActionBtns.forEach(btn => {
        const quickFilter = btn.dataset.quickFilter;
        if ((quickFilter === fechaFilter) || (quickFilter === 'mis-ordenes' && misOrdenesFilter === 'mis_ordenes')) {
            btn.classList.add('active');
        }
    });

    // Limpiar todos los filtros
    if (btnClearAll) {
        btnClearAll.addEventListener('click', function () {
            window.location.href = window.location.origin + window.location.pathname;
        });
    }

    // Al cargar, aplicar filtro de estado si está en la URL
    const estadoFilterFromUrl = urlParamsOnLoad.get('estado');
    if (estadoFilterFromUrl) {
        const targetBtn = document.querySelector(`.btn-filter-estado[data-estado="${estadoFilterFromUrl}"]`);
        if (targetBtn) {
            targetBtn.click();
        }
    } else {
        // Si no hay filtro de estado, activar el botón "Todas" por defecto
        const allBtn = document.querySelector('.btn-filter-estado[data-estado=""]');
        if (allBtn) {
            allBtn.click();
        }
        // Asegurarse de que las URLs de acción estén limpias si no hay filtro inicial
        updateActionURLs('');
    }

    // Event listener for OP filter
    if (opFilter) {
        opFilter.addEventListener('change', function () {
            activeFilters.op = this.value;
            applyClientFilters();
        });
    }

    // Al cargar, aplicar filtro de OP si está en la URL
    const opFilterFromUrl = urlParamsOnLoad.get('op_id');
    if (opFilterFromUrl && opFilter) {
        opFilter.value = opFilterFromUrl;
        activeFilters.op = opFilterFromUrl;
    }

    // Aplicar filtros de cliente iniciales
    applyClientFilters();
});
