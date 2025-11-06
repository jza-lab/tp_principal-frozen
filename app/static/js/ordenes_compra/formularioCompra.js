document.addEventListener('DOMContentLoaded', function () {
    const proveedorSelect = document.getElementById('proveedor_id');
    const searchInput = document.getElementById('insumo-search');
    const resultsContainer = document.getElementById('insumo-results');
    const itemsContainer = document.getElementById('itemsContainer');
    const itemTemplate = document.getElementById('item-template');
    const noItemsMsg = document.getElementById('no-items-msg');
    const subtotalInput = document.getElementById('subtotal');
    const ivaCheckbox = document.getElementById('iva');
    const totalInput = document.getElementById('total');
    let itemIndex = itemsContainer.querySelectorAll('.item-row').length;

    // --- 1. Habilitar/Deshabilitar búsqueda de insumos ---
    function toggleInsumoSearch() {
        if (proveedorSelect.value) {
            searchInput.disabled = false;
            searchInput.placeholder = "Buscar insumo por nombre o código...";
        } else {
            searchInput.disabled = true;
            searchInput.placeholder = "Seleccione un proveedor primero";
            searchInput.value = '';
            resultsContainer.innerHTML = '';
            resultsContainer.style.display = 'none';
        }
    }

    proveedorSelect.addEventListener('change', toggleInsumoSearch);

    // --- 2. Búsqueda dinámica de insumos ---
    searchInput.addEventListener('input', debounce(async function () {
        const query = searchInput.value.trim();
        const proveedorId = proveedorSelect.value;

        if (query.length < 2 || !proveedorId) {
            resultsContainer.innerHTML = '';
            resultsContainer.style.display = 'none';
            return;
        }

        try {
            const response = await fetch(`${INSUMOS_API_URL}?search=${encodeURIComponent(query)}&proveedor_id=${proveedorId}`);
            if (!response.ok) throw new Error('Error en la red');
            const insumos = await response.json();

            resultsContainer.innerHTML = '';
            if (insumos.length > 0) {
                insumos.forEach(insumo => {
                    const div = document.createElement('a');
                    div.href = '#';
                    div.className = 'list-group-item list-group-item-action';
                    div.textContent = `${insumo.nombre} ($${parseFloat(insumo.precio_unitario || 0).toFixed(2)})`;
                    div.dataset.id = insumo.id_insumo;
                    div.dataset.nombre = insumo.nombre;
                    div.dataset.precio = insumo.precio_unitario || 0;
                    resultsContainer.appendChild(div);
                });
                resultsContainer.style.display = 'block';
            } else {
                resultsContainer.innerHTML = '<div class="list-group-item">No se encontraron insumos para este proveedor.</div>';
                resultsContainer.style.display = 'block';
            }
        } catch (error) {
            console.error("Error al buscar insumos:", error);
            resultsContainer.innerHTML = '<div class="list-group-item list-group-item-danger">Error al cargar.</div>';
            resultsContainer.style.display = 'block';
        }
    }, 300));

    // --- 3. Añadir ítem desde los resultados de búsqueda ---
    resultsContainer.addEventListener('click', function (e) {
        e.preventDefault();
        if (e.target.classList.contains('list-group-item-action')) {
            const selectedInsumo = e.target;
            const insumoId = selectedInsumo.dataset.id;
            const insumoNombre = selectedInsumo.dataset.nombre;
            const insumoPrecio = parseFloat(selectedInsumo.dataset.precio).toFixed(2);

            if (document.querySelector(`input.insumo-id[value="${insumoId}"]`)) {
                showNotificationModal("Error de validación", "Este insumo ya ha sido añadido.");
                return;
            }

            const templateContent = itemTemplate.content.cloneNode(true);
            const newRow = templateContent.querySelector('.item-row');

            newRow.querySelector('.insumo-id').name = `items[${itemIndex}][insumo_id]`;
            newRow.querySelector('.insumo-id').value = insumoId;
            newRow.querySelector('.insumo-nombre').value = insumoNombre;
            newRow.querySelector('.cantidad').name = `items[${itemIndex}][cantidad_solicitada]`;
            newRow.querySelector('.precio_unitario').name = `items[${itemIndex}][precio_unitario]`;
            newRow.querySelector('.precio_unitario').value = `$${insumoPrecio}`;


            itemsContainer.appendChild(newRow);
            itemIndex++;
            
            searchInput.value = '';
            resultsContainer.style.display = 'none';

            updateUI();
            calcularSubtotales();
        }
    });

    // --- 4. Eliminar ítem ---
    itemsContainer.addEventListener('click', function (e) {
        if (e.target.closest('.removeItemBtn')) {
            e.target.closest('.item-row').remove();
            updateItemIndices();
            updateUI();
            calcularSubtotales();
        }
    });

    // --- 5. Recalcular totales al cambiar cantidad o IVA ---
    itemsContainer.addEventListener('input', function (e) {
        if (e.target.classList.contains('cantidad')) {
            calcularSubtotales();
        }
    });
    ivaCheckbox.addEventListener('change', calcularSubtotales);

    // --- 6. Funciones auxiliares ---
    function calcularSubtotales() {
        let subtotal = 0;
        document.querySelectorAll('.item-row').forEach(row => {
            const cantidad = parseFloat(row.querySelector('.cantidad').value) || 0;
            const precioStr = row.querySelector('.precio_unitario').value.replace('$', '').trim();
            const precio = parseFloat(precioStr) || 0;
            subtotal += cantidad * precio;
        });

        subtotalInput.value = `$${subtotal.toFixed(2)}`;

        let total = subtotal;
        if (ivaCheckbox.checked) {
            total += subtotal * 0.21;
        }
        totalInput.value = `$${total.toFixed(2)}`;
    }

    function updateUI() {
        const hasItems = itemsContainer.children.length > 0;
        noItemsMsg.style.display = hasItems ? 'none' : 'block';
    }

    function updateItemIndices() {
        let index = 0;
        itemsContainer.querySelectorAll('.item-row').forEach(row => {
            row.querySelectorAll('input').forEach(input => {
                const name = input.getAttribute('name');
                if (name) {
                    input.setAttribute('name', name.replace(/items\[\d+\]/, `items[${index}]`));
                }
            });
            index++;
        });
        itemIndex = index;
    }

    function debounce(func, delay) {
        let timeout;
        return function (...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }

    // Ocultar resultados si se hace clic fuera
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !resultsContainer.contains(e.target)) {
            resultsContainer.style.display = 'none';
        }
    });

    // --- Inicialización ---
    toggleInsumoSearch();
    updateUI();
    calcularSubtotales();
});
