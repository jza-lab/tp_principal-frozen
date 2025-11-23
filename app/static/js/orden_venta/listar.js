document.addEventListener('DOMContentLoaded', function () {
    // Variables globales
    const searchInput = document.getElementById('searchInput');
    const estadoBtns = document.querySelectorAll('.btn-filter-estado');
    const quickActionBtns = document.querySelectorAll('.btn-quick-action');
    const pedidoCards = document.querySelectorAll('#pedidos-container .col-md-4');
    const btnClearAll = document.getElementById('btnClearAll');
    const visibleCountEl = document.getElementById('visibleCount');
    const totalCountEl = document.getElementById('totalCount');
    const pedidosContainer = document.getElementById('pedidos-container');
    const noResultsMessage = document.getElementById('noResultsMessage');
    const btnGestionarDespachos = document.getElementById('btn-gestionar-despachos');

    let activeFilters = {
        estado: '',
        search: ''
    };

    // --- Inicialización desde URL y Elementos activos ---
    function initFilters() {
        const urlParams = new URLSearchParams(window.location.search);
        const activeBtn = document.querySelector('.btn-filter-estado.active');
        
        // Prioridad: URL > Botón activo (que ya viene del servidor)
        if (urlParams.has('estado')) {
            activeFilters.estado = urlParams.get('estado');
        } else if (activeBtn) {
            activeFilters.estado = activeBtn.dataset.estado || '';
        }

        if (urlParams.has('search')) {
            activeFilters.search = urlParams.get('search');
        } else if (searchInput) {
            activeFilters.search = searchInput.value.trim();
        }
        
        updateFormsWithFilters();
    }

    function updateURL() {
        const url = new URL(window.location.href);
        
        if (activeFilters.estado) {
            url.searchParams.set('estado', activeFilters.estado);
        } else {
            url.searchParams.delete('estado');
        }

        if (activeFilters.search) {
            url.searchParams.set('search', activeFilters.search);
        } else {
            url.searchParams.delete('search');
        }

        // Usar replaceState para no llenar el historial con cada letra
        window.history.replaceState({}, '', url);
        
        updateFormsWithFilters();
    }

    function updateFormsWithFilters() {
        const filterString = window.location.search; // Esto incluye ?estado=...&search=...
        document.querySelectorAll('.filtros-activos-input').forEach(input => {
            input.value = filterString;
        });
    }

    const totalPedidos = pedidoCards.length;
    if (totalCountEl) {
        totalCountEl.textContent = totalPedidos;
    }
    
    function applyClientFilters() {
        let visibleCount = 0;

        pedidoCards.forEach(card => {
            let show = true;

            if (activeFilters.estado && card.dataset.estado !== activeFilters.estado) {
                show = false;
            }

            if (activeFilters.search) {
                const codigo = card.dataset.codigo.toLowerCase();
                const searchTerm = activeFilters.search.toLowerCase();
                if (!codigo.includes(searchTerm)) {
                    show = false;
                }
            }

            card.style.display = show ? '' : 'none';
            if (show) {
                visibleCount++;
            }
        });

        if (visibleCountEl) {
            visibleCountEl.textContent = visibleCount;
        }

        const hasResults = visibleCount > 0;
        if (pedidosContainer) {
            pedidosContainer.style.display = hasResults ? 'flex' : 'none';
        }
        if (noResultsMessage) {
            noResultsMessage.style.display = hasResults ? 'none' : 'flex';
        }

        const hasActiveClientFilters = activeFilters.estado || activeFilters.search;
        const urlParams = new URLSearchParams(window.location.search);
        if (btnClearAll) {
           btnClearAll.style.display = (hasActiveClientFilters || urlParams.has('rango_fecha')) ? 'block' : 'none';
        }
        
        // Lógica para mostrar/ocultar el botón de gestionar despachos
        if (btnGestionarDespachos) {
            btnGestionarDespachos.style.display = (activeFilters.estado === 'LISTO_PARA_ENTREGA') ? 'block' : 'none';
        }
    }

    estadoBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            estadoBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            activeFilters.estado = this.dataset.estado;
            applyClientFilters();
            updateURL(); // Actualizar URL al cambiar filtro
        });
    });

    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function () {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                activeFilters.search = this.value.trim();
                applyClientFilters();
                updateURL(); // Actualizar URL al buscar
            }, 300);
        });
    }

    quickActionBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            const filter = this.dataset.quickFilter;
            const currentUrl = new URL(window.location.href);
            const isActive = this.classList.contains('active');

            currentUrl.searchParams.delete('rango_fecha');

            if (!isActive) {
                currentUrl.searchParams.set('rango_fecha', filter);
            }

            window.location.href = currentUrl.toString();
        });
    });

    const urlParams = new URLSearchParams(window.location.search);
    const fechaFilter = urlParams.get('rango_fecha');

    quickActionBtns.forEach(btn => {
        if (btn.dataset.quickFilter === fechaFilter) {
            btn.classList.add('active');
        }
    });

    if (btnClearAll) {
        btnClearAll.addEventListener('click', function () {
            window.location.href = window.location.origin + window.location.pathname;
        });
    }

    initFilters(); // Inicializar filtros al cargar
    applyClientFilters();
});
