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

    // Obtener parámetros de URL
    const urlParams = new URLSearchParams(window.location.search);

    let activeFilters = {
        estado: urlParams.get('estado') || '',
        search: urlParams.get('search_term') || '',
        opSearch: urlParams.get('op_codigo') || '',
        op: urlParams.get('op_id') || ''
    };

    // Total de órdenes
    const totalOrdenes = ordenCards.length;
    if (totalCountEl) {
        totalCountEl.textContent = totalOrdenes;
    }

    // Función para actualizar las URLs de las acciones con el filtro de estado actual y OP
    function updateActionURLs(estado, opId) {
        // Seleccionar todos los formularios que tengan acción, incluyendo los de los modales
        const actionForms = document.querySelectorAll('form[action]');
        
        // Obtener todos los parámetros actuales de la URL para preservarlos
        const currentParams = new URLSearchParams(window.location.search);
        const paramsToPreserve = ['filtro', 'rango_fecha', 'op_codigo', 'search_term'];
        
        actionForms.forEach(form => {
            if (!form.action) return; // Omitir si no hay URL de acción
            
            // Solo actualizar formularios relevantes a órdenes de compra para evitar efectos secundarios
            if (!form.action.includes('/compras/')) return;

            try {
                const actionUrl = new URL(form.action, window.location.origin);
                
                // Actualizar estado
                if (estado) {
                    actionUrl.searchParams.set('estado', estado);
                } else {
                    actionUrl.searchParams.delete('estado');
                }
                
                // Actualizar op_id
                if (opId) {
                    actionUrl.searchParams.set('op_id', opId);
                } else {
                    actionUrl.searchParams.delete('op_id');
                }
                
                // Preservar otros filtros
                paramsToPreserve.forEach(param => {
                    const val = currentParams.get(param);
                    if (val) {
                        actionUrl.searchParams.set(param, val);
                    } else {
                         actionUrl.searchParams.delete(param);
                    }
                });

                form.action = actionUrl.toString();
            } catch (e) {
                console.error("Error actualizando URL de acción:", e);
            }
        });
        
        // Actualizar URL del navegador (history)
        const currentUrl = new URL(window.location.href);
        
        if (estado) {
            currentUrl.searchParams.set('estado', estado);
        } else {
            currentUrl.searchParams.delete('estado');
        }

        if (opId) {
            currentUrl.searchParams.set('op_id', opId);
        } else {
            currentUrl.searchParams.delete('op_id');
        }
        
        // Nota: Los otros parámetros ya están en window.location.search, no necesitamos re-setearlos 
        // a menos que queramos sincronizar estado interno -> URL, pero aquí es más updateActionURLs.
        // La sincronización principal ocurre en los listeners de inputs.

        window.history.replaceState({}, '', currentUrl);
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

            // Filtro por búsqueda de OP (texto)
            if (activeFilters.opSearch) {
                const opCodigo = (card.dataset.opCodigo || '').toLowerCase();
                const opSearchTerm = activeFilters.opSearch.toLowerCase();
                if (!opCodigo.includes(opSearchTerm)) {
                    show = false;
                }
            }

            // Filtro por OP (ID, desde URL)
            // Nota: card.dataset.opId debe estar presente en el HTML
            if (activeFilters.op && card.dataset.opId != activeFilters.op) {
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
        const hasActiveClientFilters = activeFilters.estado || activeFilters.search || activeFilters.opSearch || activeFilters.op;
        if (btnClearAll) {
           btnClearAll.style.display = (hasActiveClientFilters || urlParams.has('filtro') || urlParams.has('rango_fecha')) ? 'block' : 'none';
        }
        
        // Actualizar URLs de formularios
        updateActionURLs(activeFilters.estado, activeFilters.op);
    }

    // Event listeners para botones de estado
    estadoBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            const newEstado = this.dataset.estado;
            const currentUrl = new URL(window.location.href);
            
            if (newEstado) {
                currentUrl.searchParams.set('estado', newEstado);
            } else {
                currentUrl.searchParams.delete('estado');
            }
            
            // Nota: Los otros parámetros (op_codigo, search_term, filtro, rango_fecha)
            // ya están en la URL actual, así que se preservan automáticamente al hacer 
            // new URL(window.location.href). No hace falta setearlos explícitamente de nuevo
            // salvo que queramos forzar algo desde activeFilters si estuviera desincronizado.

            // Redirigir al servidor para obtener datos frescos y evitar caché inconsistente
            window.location.href = currentUrl.toString();
        });
    });

    // Event listener para búsqueda
    if (searchInput) {
        // Inicializar valor desde URL si existe
        if (activeFilters.search) {
            searchInput.value = activeFilters.search;
        }

        let searchTimeout;
        searchInput.addEventListener('input', function () {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                activeFilters.search = this.value.trim();
                
                // Actualizar URL sin recargar antes de aplicar filtros
                const currentUrl = new URL(window.location.href);
                if (activeFilters.search) {
                    currentUrl.searchParams.set('search_term', activeFilters.search);
                } else {
                    currentUrl.searchParams.delete('search_term');
                }
                window.history.replaceState({}, '', currentUrl);

                applyClientFilters();

            }, 300);
        });
    }

    // Event listener para búsqueda de OP
    if (opSearchInput) {
        // Inicializar valor desde URL si existe
        if (activeFilters.opSearch) {
            opSearchInput.value = activeFilters.opSearch;
        }
        
        let opSearchTimeout;
        opSearchInput.addEventListener('input', function () {
            clearTimeout(opSearchTimeout);
            opSearchTimeout = setTimeout(() => {
                activeFilters.opSearch = this.value.trim();

                // Actualizar URL sin recargar antes de aplicar filtros
                const currentUrl = new URL(window.location.href);
                if (activeFilters.opSearch) {
                    currentUrl.searchParams.set('op_codigo', activeFilters.opSearch);
                } else {
                    currentUrl.searchParams.delete('op_codigo');
                }
                window.history.replaceState({}, '', currentUrl);
                
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
            
            // Los demás filtros (estado, op_id, op_codigo, search_term) se mantienen
            // porque estamos clonando la URL actual.

            window.location.href = currentUrl.toString();
        });
    });

    // Al cargar la página, marcar como activo el botón de filtro rápido
    const fechaFilter = urlParams.get('rango_fecha');
    const misOrdenesFilter = urlParams.get('filtro');

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
    if (activeFilters.estado) {
        const targetBtn = document.querySelector(`.btn-filter-estado[data-estado="${activeFilters.estado}"]`);
        if (targetBtn) {
            // Remover active de todos primero
            estadoBtns.forEach(b => b.classList.remove('active'));
            targetBtn.classList.add('active');
        }
    } else {
        // Si no hay filtro de estado, activar el botón "Todas" por defecto
        const allBtn = document.querySelector('.btn-filter-estado[data-estado=""]');
        if (allBtn) {
            // Remover active de todos primero
            estadoBtns.forEach(b => b.classList.remove('active'));
            allBtn.classList.add('active');
        }
    }
    
    // Inicializar URLs
    updateActionURLs(activeFilters.estado, activeFilters.op);

    // Aplicar filtros de cliente iniciales
    applyClientFilters();
});
