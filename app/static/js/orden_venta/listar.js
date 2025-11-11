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
        });
    });

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

    applyClientFilters();
});
