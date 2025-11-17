// app/static/js/orden_venta/productSearch.js

document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('productSearchInput');
    const searchResultsContainer = document.getElementById('productSearchResults');

    if (!searchInput || !searchResultsContainer) {
        return;
    }

    // Función para mostrar y filtrar los resultados
    function showAndFilterResults() {
        const filter = searchInput.value.toLowerCase();
        searchResultsContainer.innerHTML = '';

        const filteredProducts = PRODUCTOS_DATA.filter(product =>
            product.nombre.toLowerCase().includes(filter)
        );

        if (filteredProducts.length > 0) {
            searchResultsContainer.style.display = 'block';
            filteredProducts.forEach(product => {
                const item = document.createElement('a');
                item.href = '#';
                item.className = 'list-group-item list-group-item-action';
                item.dataset.productId = product.id;
                item.innerHTML = `
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${product.nombre}</h6>
                        <small class="text-muted">${formatToARS(product.precio_unitario)}</small>
                    </div>
                    <p class="mb-1 small text-muted">Unidad: ${product.unidad_medida}</p>
                `;
                searchResultsContainer.appendChild(item);
            });
        } else {
            searchResultsContainer.style.display = 'none';
        }
    }

    // Evento para mostrar y filtrar al escribir
    searchInput.addEventListener('input', showAndFilterResults);
    searchInput.addEventListener('focus', showAndFilterResults);

    // Evento para seleccionar un producto
    searchResultsContainer.addEventListener('click', function(event) {
        event.preventDefault();
        const clickedItem = event.target.closest('.list-group-item');
        if (clickedItem) {
            const productId = clickedItem.dataset.productId;
            const product = PRODUCTOS_DATA.find(p => p.id == productId);
            if (product) {
                addItemRow(product);
                searchInput.value = ''; // Limpiar el buscador
                searchResultsContainer.style.display = 'none'; // Ocultar resultados
            }
        }
    });

    // Ocultar resultados si se hace clic fuera
    document.addEventListener('click', function(event) {
        if (!searchInput.contains(event.target) && !searchResultsContainer.contains(event.target)) {
            searchResultsContainer.style.display = 'none';
        }
    });
});
