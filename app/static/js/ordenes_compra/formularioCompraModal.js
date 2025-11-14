document.addEventListener('DOMContentLoaded', function () {
    const itemsContainer = document.getElementById('itemsContainer');
    const itemTemplate = document.getElementById('item-template');
    const subtotalInput = document.getElementById('subtotal');
    const ivaCheckbox = document.getElementById('iva');
    const totalInput = document.getElementById('total');
    const form = document.getElementById('ordenCompraForm');
    const submitButton = document.getElementById('submitBtn');

    // --- LÓGICA DEL MODAL DE BÚSQUEDA ---
    const insumoSearchModal = new bootstrap.Modal(document.getElementById('insumoSearchModal'));
    const searchFilterInput = document.getElementById('insumo-search-filter');
    const insumoSelect = document.getElementById('insumo-select');
    // Asumimos que los datos de insumos están disponibles globalmente en una variable `insumos`
    const insumosData = typeof insumos !== 'undefined' ? insumos : [];
    const proveedoresData = typeof proveedores !== 'undefined' ? proveedores : [];

    function poblarInsumosEnModal() {
        insumoSelect.innerHTML = ''; // Limpiar opciones existentes
        insumosData.forEach(insumo => {
            const proveedor = proveedoresData.find(p => p.id === insumo.proveedor.id);
            const rating_stars = proveedor ? ('★'.repeat(proveedor.rating) + '☆'.repeat(5 - proveedor.rating)) : '';

            const option = document.createElement('option');
            option.value = insumo.id_insumo;
            option.textContent = `${insumo.nombre} - ${insumo.proveedor.nombre} ${rating_stars}`;
            option.dataset.nombre = insumo.nombre;
            option.dataset.precio = insumo.precio_unitario;
            option.dataset.proveedorId = insumo.proveedor.id;
            option.dataset.proveedorNombre = insumo.proveedor.nombre;
            option.dataset.stockActual = insumo.stock_actual || 0;
            option.dataset.stockMax = insumo.stock_max || 999999;
            option.dataset.id_insumo = insumo.id_insumo;
            insumoSelect.appendChild(option);
        });
    }

    searchFilterInput.addEventListener('input', function () {
        const searchTerm = this.value.toLowerCase();
        Array.from(insumoSelect.options).forEach(option => {
            const text = option.textContent.toLowerCase();
            option.style.display = text.includes(searchTerm) ? '' : 'none';
        });
    });

    insumoSelect.addEventListener('dblclick', function () {
        const selectedOption = this.options[this.selectedIndex];
        if (!selectedOption || !selectedOption.value) return;

        agregarItemAOrden(selectedOption.dataset);
        insumoSearchModal.hide();
    });

    document.getElementById('insumoSearchModal').addEventListener('shown.bs.modal', function () {
        poblarInsumosEnModal();
        searchFilterInput.focus();
    });

    function agregarItemAOrden(insumo) {
        const templateContent = itemTemplate.content.cloneNode(true);
        const newRow = templateContent.querySelector('.item-row');
        
        newRow.dataset.stockActual = insumo.stockActual;
        newRow.dataset.stockMax = insumo.stockMax;
        newRow.querySelector('.insumo-id').value = insumo.id_insumo;
        newRow.querySelector('.insumo-nombre').value = insumo.nombre;
        newRow.querySelector('.proveedor-nombre').value = insumo.proveedorNombre;
        newRow.querySelector('.precio_unitario').value = `$${parseFloat(insumo.precio).toFixed(2)}`;
        
        itemsContainer.appendChild(newRow);
        updateUI();
        calcularSubtotales();
    }
    // --- FIN LÓGICA DEL MODAL ---

    // Eventos para el contenedor de ítems (eliminar, cambiar cantidad)
    if (itemsContainer) {
        itemsContainer.addEventListener('click', function (e) {
            if (e.target.closest('.removeItemBtn')) {
                e.target.closest('.item-row').remove();
                updateUI();
                calcularSubtotales();
            }
        });

        itemsContainer.addEventListener('input', function (e) {
            if (e.target.classList.contains('cantidad')) {
                const currentRow = e.target.closest('.item-row');
                const cantidadInput = e.target;
                const stockActual = parseFloat(currentRow.dataset.stockActual);
                const stockMax = parseFloat(currentRow.dataset.stockMax);
                const cantidadComprar = parseFloat(cantidadInput.value);

                if (isNaN(cantidadComprar) || cantidadComprar <= 0) {
                     cantidadInput.classList.add('is-invalid');
                } else if (stockActual + cantidadComprar > stockMax) {
                    cantidadInput.classList.add('is-invalid');
                    const insumoNombre = currentRow.querySelector('.insumo-nombre').value;
                    showNotificationModal(
                        "Error de Stock",
                        `La cantidad para "${insumoNombre}" supera el stock máximo permitido (${stockMax} unidades).`
                    );
                } else {
                    cantidadInput.classList.remove('is-invalid');
                }
                
                validarTodasLasFilas();
                calcularSubtotales();
            }
        });
    }

    // Evento de cambio de IVA
    if (ivaCheckbox) {
        ivaCheckbox.addEventListener('change', calcularSubtotales);
    }
    
    // Función para validar todas las filas
    function validarTodasLasFilas() {
        let todasValidas = true;
        document.querySelectorAll('.item-row .cantidad').forEach(input => {
            if (input.classList.contains('is-invalid') || input.value.trim() === '' || parseFloat(input.value) <= 0) {
                todasValidas = false;
            }
        });
        if (submitButton) {
            submitButton.disabled = !todasValidas;
        }
    }

    // Función para calcular subtotales
    function calcularSubtotales() {
        let subtotal = 0;
        document.querySelectorAll('.item-row').forEach(row => {
            const cantidad = parseFloat(row.querySelector('.cantidad').value) || 0;
            const precioStr = row.querySelector('.precio_unitario').value.replace('$', '').trim();
            const precio = parseFloat(precioStr) || 0;
            subtotal += cantidad * precio;
        });

        if (subtotalInput) {
            subtotalInput.value = `$${subtotal.toFixed(2)}`;
        }

        let total = subtotal;
        if (ivaCheckbox && ivaCheckbox.checked) {
            total += subtotal * 0.21;
        }
        if (totalInput) {
            totalInput.value = `$${total.toFixed(2)}`;
        }
    }

    // Función para actualizar la UI (mensaje de "sin ítems")
    function updateUI() {
        const noItemsMsg = document.getElementById('no-items-msg');
        if (noItemsMsg) {
            noItemsMsg.style.display = itemsContainer.children.length > 0 ? 'none' : 'block';
        }
    }

    // Adjuntar el event listener para el envío del formulario
    if (form && submitButton) {
        form.addEventListener('submit', function(event) {
            // Deshabilitar el botón inmediatamente para evitar clics múltiples
            submitButton.disabled = true;
            submitButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Guardando...`;

            // Prevenir el envío si no hay ítems
            if (itemsContainer.children.length === 0) {
                event.preventDefault(); 
                showNotificationModal('Error', 'Debe añadir al menos un ítem a la orden.', 'error');
                // Rehabilitar el botón si el envío se cancela
                submitButton.disabled = false;
                submitButton.innerHTML = `<i class="bi bi-check-circle me-1"></i> Crear Orden`;
            }
        });
    }

    // Llamadas iniciales al cargar la página
    updateUI();
    calcularSubtotales();
});
