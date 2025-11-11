document.addEventListener('DOMContentLoaded', function () {
    // State
    let activeFilters = {
        busqueda: '',
    };
    let debounceTimer;
    let fetchController = new AbortController();

    // DOM Elements
    const searchInput = document.getElementById('busqueda-filtro');
    const suggestionsContainer = document.getElementById('suggestions-container');
    const productosGrid = document.getElementById('productos-grid');
    const productosCount = document.getElementById('productos-count');
    const noResultsMessage = document.getElementById('no-results-message');
    const cardTemplate = document.getElementById('producto-card-template');

    // --- Event Listeners ---
    searchInput.addEventListener('input', () => {
        activeFilters.busqueda = searchInput.value;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetchProductos();
        }, 300); // 300ms delay
    });

    // --- Core Functions ---
    function fetchProductos() {
        fetchController.abort();
        fetchController = new AbortController();
        const signal = fetchController.signal;

        const params = new URLSearchParams();
        if (activeFilters.busqueda) params.append('busqueda', activeFilters.busqueda);

        const url = `/api/productos/filter?${params.toString()}`;
        
        showLoadingSpinner();

        fetch(url, { signal })
            .then(response => response.json())
            .then(data => {
                renderProductos(data.data || []);
            })
            .catch(error => {
                if (error.name !== 'AbortError') {
                    console.error('Fetch error:', error);
                    showErrorMessage();
                }
            });
    }

    function renderProductos(productos) {
        productosGrid.innerHTML = '';
        if (productos.length === 0) {
            if (noResultsMessage) noResultsMessage.style.display = 'block';
        } else {
            if (noResultsMessage) noResultsMessage.style.display = 'none';
            productos.forEach(producto => {
                const card = createProductoCard(producto);
                productosGrid.appendChild(card);
            });
        }
        productosCount.textContent = `${productos.length} productos encontrados`;
    }

    function createProductoCard(producto) {
        const templateContent = cardTemplate.content.cloneNode(true);
        const cardWrapper = templateContent.querySelector('.col-lg-4');
        const card = cardWrapper.querySelector('.producto-card');

        if (!producto.activo) {
            card.classList.add('insumo-inactivo');
        }

        card.querySelector('.producto-nombre').textContent = producto.nombre;
        if(!producto.activo){
            card.querySelector('.producto-nombre').innerHTML += ' <span class="badge bg-secondary">Inactivo</span>';
        }
        card.querySelector('.producto-categoria').textContent = producto.categoria;
        card.querySelector('.producto-codigo').textContent = producto.codigo;
        card.querySelector('.producto-unidad').textContent = producto.unidad_medida;
        card.querySelector('.producto-precio').textContent = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(producto.precio_unitario);
        
        const actionButtons = card.querySelector('.action-buttons');
        actionButtons.innerHTML = ''; // Clear any existing buttons

        if (producto.activo) {
            actionButtons.innerHTML += `<a onClick="recargarPrecioProducto('${producto.id}')" class="btn btn-sm btn-outline-primary" title="Actualizar precio"><i class="bi bi-arrow-repeat"></i></a>`;
            actionButtons.innerHTML += `<a href="/productos/actualizar/${producto.id}" class="btn btn-sm btn-outline-primary" title="Modificar producto"><i class="bi bi-pencil"></i></a>`;
            actionButtons.innerHTML += `<a href="/productos/${producto.id}" class="btn btn-sm btn-outline-primary" title="Detalle"><i class="bi bi-eye"></i></a>`;
            actionButtons.innerHTML += `<a class="btn btn-sm btn-outline-danger" title="Inhabilitar producto" onClick="eliminarProducto('${producto.id}')"><i class="bi bi-slash-circle"></i> Inhabilitar</a>`;
        } else {
            actionButtons.innerHTML += `<a class="btn btn-sm btn-outline-success" title="Habilitar producto" onClick="habilitarProducto('${producto.id}')"><i class="bi bi-check-circle"></i> Habilitar</a>`;
        }
        
        return cardWrapper;
    }
    
    function showLoadingSpinner() {
        productosGrid.innerHTML = '<div class="col-12 text-center py-5"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Cargando...</span></div></div>';
    }
    
    function showErrorMessage() {
        productosGrid.innerHTML = '<div class="col-12 text-center text-danger py-5"><i class="bi bi-exclamation-circle-fill fs-1 d-block mb-2"></i><h4>Ocurrió un error</h4><p>No se pudieron cargar los productos. Intenta de nuevo más tarde.</p></div>';
    }

    // Initial load
    fetchProductos();
});
