document.addEventListener('DOMContentLoaded', function () {
    // State
    let activeFilters = {
        busqueda: '',
        categorias: [],
        proveedores: [],
        stock_status: ''
    };
    let suggestionsDebounceTimer;
    let filterDebounceTimer;
    let fetchInsumosController = new AbortController();

    // DOM Elements
    const searchInput = document.getElementById('busqueda-filtro');
    const suggestionsContainer = document.getElementById('suggestions-container');
    const categoryCheckboxes = document.querySelectorAll('.category-checkbox');
    const proveedorCheckboxes = document.querySelectorAll('.proveedor-checkbox');
    const stockBajoBtn = document.getElementById('stock-bajo-btn');
    const limpiarFiltrosBtn = document.getElementById('limpiar-filtros-btn');
    const activeFiltersContainer = document.getElementById('active-filters-container');
    const insumosGrid = document.getElementById('insumos-grid');
    const insumosCount = document.getElementById('insumos-count');
    const noResultsMessage = document.getElementById('no-results-message');
    const cardTemplate = document.getElementById('insumo-card-template');

    // --- Event Listeners ---
    searchInput.addEventListener('input', () => {
        const query = searchInput.value;
        activeFilters.busqueda = query;

        // Suggestions logic
        clearTimeout(suggestionsDebounceTimer);
        if (query.length > 1) {
            suggestionsDebounceTimer = setTimeout(() => {
                fetchSuggestions(query);
            }, 250); // Shorter delay for suggestions
        } else {
            suggestionsContainer.innerHTML = '';
        }

        // Main filter logic
        clearTimeout(filterDebounceTimer);
        filterDebounceTimer = setTimeout(() => {
            fetchInsumos();
        }, 500); // Slightly longer delay for main filtering
    });

    suggestionsContainer.addEventListener('click', (e) => {
        if (e.target.classList.contains('suggestion-item')) {
            searchInput.value = e.target.textContent;
            activeFilters.busqueda = searchInput.value;
            suggestionsContainer.innerHTML = '';
            fetchInsumos();
        }
    });

    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target)) {
            suggestionsContainer.innerHTML = '';
        }
    });


    categoryCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            const category = checkbox.value;
            if (checkbox.checked) {
                if (!activeFilters.categorias.includes(category)) {
                    activeFilters.categorias.push(category);
                }
            } else {
                activeFilters.categorias = activeFilters.categorias.filter(c => c !== category);
            }
            fetchInsumos();
        });
    });

    proveedorCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            const proveedorId = checkbox.value;
            if (checkbox.checked) {
                if (!activeFilters.proveedores.includes(proveedorId)) {
                    activeFilters.proveedores.push(proveedorId);
                }
            } else {
                activeFilters.proveedores = activeFilters.proveedores.filter(id => id !== proveedorId);
            }
            fetchInsumos();
        });
    });

    stockBajoBtn.addEventListener('click', () => {
        if (activeFilters.stock_status === 'bajo') {
            activeFilters.stock_status = '';
            stockBajoBtn.classList.remove('active');
        } else {
            activeFilters.stock_status = 'bajo';
            stockBajoBtn.classList.add('active');
        }
        fetchInsumos();
    });

    limpiarFiltrosBtn.addEventListener('click', () => {
        // Reset state
        activeFilters = { busqueda: '', categorias: [], proveedores: [], stock_status: '' };

        // Reset UI
        searchInput.value = '';
        categoryCheckboxes.forEach(cb => cb.checked = false);
        proveedorCheckboxes.forEach(cb => cb.checked = false);
        stockBajoBtn.classList.remove('active');

        fetchInsumos();
    });

    activeFiltersContainer.addEventListener('click', (e) => {
        if (e.target.classList.contains('remove-filter-btn')) {
            const type = e.target.dataset.filterType;
            const value = e.target.dataset.filterValue;

            if (type === 'busqueda') {
                activeFilters.busqueda = '';
                searchInput.value = '';
            } else if (type === 'stock_status') {
                activeFilters.stock_status = '';
                stockBajoBtn.classList.remove('active');
            } else if (type === 'categoria') {
                activeFilters.categorias = activeFilters.categorias.filter(c => c !== value);
                const checkbox = document.querySelector(`.category-checkbox[value="${value}"]`);
                if (checkbox) checkbox.checked = false;
            } else if (type === 'proveedor') {
                activeFilters.proveedores = activeFilters.proveedores.filter(id => id !== value);
                const checkbox = document.querySelector(`.proveedor-checkbox[value="${value}"]`);
                if (checkbox) checkbox.checked = false;
            }
            fetchInsumos();
        }
    });

    // --- Core Functions ---
    function fetchSuggestions(query) {
        const url = `/api/insumos/suggestions?q=${encodeURIComponent(query)}`;
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.data.length > 0) {
                    suggestionsContainer.innerHTML = '';
                    data.data.forEach(name => {
                        const item = document.createElement('a');
                        item.href = '#';
                        item.className = 'list-group-item list-group-item-action suggestion-item';
                        item.textContent = name;
                        suggestionsContainer.appendChild(item);
                    });
                } else {
                    suggestionsContainer.innerHTML = '';
                }
            })
            .catch(error => {
                console.error('Error fetching suggestions:', error);
                suggestionsContainer.innerHTML = '';
            });
    }

    function fetchInsumos() {
        // Abort any ongoing fetch request
        fetchInsumosController.abort();
        fetchInsumosController = new AbortController();
        const signal = fetchInsumosController.signal;

        const params = new URLSearchParams();
        if (activeFilters.busqueda) {
            params.append('busqueda', activeFilters.busqueda);
        }
        if (activeFilters.stock_status) {
            params.append('stock_status', activeFilters.stock_status);
        }
        activeFilters.categorias.forEach(cat => {
            params.append('categoria', cat);
        });
        activeFilters.proveedores.forEach(id => {
            params.append('id_proveedor', id);
        });

        const url = `/api/insumos/filter?${params.toString()}`;
        
        showLoadingSpinner();

        fetch(url, { signal })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if(data.success) {
                    renderInsumos(data.data);
                    renderActiveFilters();
                } else {
                    console.error("Error from API:", data.error);
                    showErrorMessage();
                }
            })
            .catch(error => {
                if (error.name === 'AbortError') {
                    console.log('Fetch aborted');
                } else {
                    console.error('Fetch error:', error);
                    showErrorMessage();
                }
            });
    }

    function renderInsumos(insumos) {
        insumosGrid.innerHTML = ''; // Clear existing cards
        
        if (insumos.length === 0) {
            if (noResultsMessage) noResultsMessage.style.display = 'block';
        } else {
            if (noResultsMessage) noResultsMessage.style.display = 'none';
            insumos.forEach(insumo => {
                const card = createInsumoCard(insumo);
                insumosGrid.appendChild(card);
            });
        }
        insumosCount.textContent = `${insumos.length} insumos encontrados`;
    }

    function renderActiveFilters() {
        activeFiltersContainer.innerHTML = '';
        let hasFilters = false;

        if (activeFilters.busqueda) {
            activeFiltersContainer.appendChild(createPill('busqueda', activeFilters.busqueda, `Texto: "${activeFilters.busqueda}"`));
            hasFilters = true;
        }
        if (activeFilters.stock_status === 'bajo') {
            activeFiltersContainer.appendChild(createPill('stock_status', 'bajo', 'Stock Bajo'));
            hasFilters = true;
        }
        activeFilters.categorias.forEach(cat => {
            activeFiltersContainer.appendChild(createPill('categoria', cat, `Cat: ${cat}`));
            hasFilters = true;
        });
        activeFilters.proveedores.forEach(provId => {
            const checkbox = document.querySelector(`.proveedor-checkbox[value="${provId}"]`);
            const provName = checkbox ? checkbox.nextElementSibling.textContent : provId;
            activeFiltersContainer.appendChild(createPill('proveedor', provId, `Prov: ${provName}`));
            hasFilters = true;
        });

        limpiarFiltrosBtn.style.display = hasFilters ? 'inline-block' : 'none';
    }

    function createPill(type, value, text) {
        const pill = document.createElement('span');
        pill.className = 'badge bg-primary d-flex align-items-center gap-2';
        pill.innerHTML = `
            ${text}
            <button type="button" class="btn-close btn-close-white remove-filter-btn" 
                    aria-label="Remove filter"
                    data-filter-type="${type}" 
                    data-filter-value="${value}"></button>
        `;
        return pill;
    }

    function createInsumoCard(insumo) {
        const templateContent = cardTemplate.content.cloneNode(true);
        const cardWrapper = templateContent.querySelector('.insumo-card-wrapper');
        const card = cardWrapper.querySelector('.insumo-card');

        // Conditional classes and badges
        if (!insumo.activo) {
            card.classList.add('insumo-inactivo');
        }
        
        // Populate data
        card.querySelector('.insumo-nombre').textContent = insumo.nombre;
        if (!insumo.activo) {
             const nombreSpan = card.querySelector('.insumo-nombre');
             nombreSpan.innerHTML += ' <span class="badge bg-secondary">Inactivo</span>';
        }
        
        const criticoBadge = card.querySelector('.insumo-es-critico-badge');
        if (insumo.es_critico) {
            criticoBadge.className = 'badge bg-danger-soft text-danger';
            criticoBadge.title = 'Insumo Delicado';
            criticoBadge.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i>Delicado';
        } else {
            criticoBadge.remove();
        }

        card.querySelector('.insumo-categoria').textContent = insumo.categoria;
        card.querySelector('.insumo-codigo').textContent = insumo.codigo_interno;
        card.querySelector('.insumo-unidad').textContent = insumo.unidad_medida;
        card.querySelector('.insumo-precio').textContent = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(insumo.precio_unitario);
        card.querySelector('.insumo-proveedor').textContent = insumo.proveedor ? insumo.proveedor.nombre : 'N/A';

        // Stock info
        const stockValue = card.querySelector('.stock-value');
        const stockMin = card.querySelector('.stock-min');
        const stockActual = insumo.stock_actual != null ? insumo.stock_actual : 0.0;
        
        stockValue.textContent = stockActual;
        stockValue.className = 'stock-value badge fw-normal py-1 fs-6'; // Reset classes
        if (stockActual < insumo.stock_min) {
            stockValue.classList.add('text-bg-danger');
        } else {
            stockValue.classList.add('text-bg-success');
        }
        stockMin.textContent = `/ Min: ${insumo.stock_min}`;

        // Action Buttons (assuming user has permission)
        const actionButtons = card.querySelector('.action-buttons');
        actionButtons.innerHTML = `
            <a href="/api/insumos/catalogo/${insumo.id_insumo}" class="btn btn-sm btn-outline-primary" title="Detalle"><i class="bi bi-eye"></i></a>
        `;
        // NOTE: For simplicity, this template assumes the user has 'gestionar_catalogo_insumos' permission.
        // A more robust solution would pass the user's permissions from Jinja2 to JS.
        if (insumo.activo) {
            actionButtons.innerHTML += `
                <a href="/api/insumos/catalogo/actualizar/${insumo.id_insumo}" class="btn btn-sm btn-outline-primary" title="Modificar insumo"><i class="bi bi-pencil"></i></a>
                <a class="btn btn-sm btn-outline-danger" title="Inhabilitar insumo" onClick="eliminarInsumo('${insumo.id_insumo}')"><i class="bi bi-slash-circle"></i> Inhabilitar</a>
            `;
        } else {
            actionButtons.innerHTML += `
                <a class="btn btn-sm btn-outline-success" title="Habilitar insumo" onClick="habilitarInsumo('${insumo.id_insumo}')"><i class="bi bi-check-circle"></i> Habilitar</a>
            `;
        }

        return cardWrapper;
    }
    
    function showLoadingSpinner() {
        insumosGrid.innerHTML = `
            <div class="col-12 text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Cargando...</span>
                </div>
            </div>
        `;
    }
    
    function showErrorMessage() {
        insumosGrid.innerHTML = `
            <div class="col-12 text-center text-danger py-5">
                <i class="bi bi-exclamation-circle-fill fs-1 d-block mb-2"></i>
                <h4>Ocurrió un error</h4>
                <p>No se pudieron cargar los insumos. Intenta de nuevo más tarde.</p>
            </div>
        `;
    }
});
