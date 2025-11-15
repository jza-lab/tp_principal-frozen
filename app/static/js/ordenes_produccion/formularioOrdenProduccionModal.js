document.addEventListener('DOMContentLoaded', function () {
    const itemsContainer = document.getElementById('items-container');
    const itemTemplate = document.getElementById('item-template');
    const noItemsMsg = document.getElementById('no-items-msg');
    const form = document.getElementById('ordenProduccionForm');
    const submitButton = form.querySelector('button[type="submit"]');

    // --- LÓGICA DEL MODAL DE BÚSQUEDA ---
    const productSearchModal = new bootstrap.Modal(document.getElementById('productSearchModal'));
    const searchFilterInput = document.getElementById('product-search-filter');
    const productSelect = document.getElementById('product-select');
    // Asumimos que los datos de productos están disponibles globalmente en una variable `productos`
    const productosData = typeof productos !== 'undefined' ? productos : [];
    let itemIndex = 0;

    function poblarProductosEnModal() {
        productSelect.innerHTML = ''; // Limpiar opciones existentes
        productosData.forEach(producto => {
            const option = document.createElement('option');
            option.value = producto.id;
            option.textContent = `${producto.nombre} (${format_product_units(producto)})`;
            // Guardar el objeto producto completo como un string JSON en el dataset
            option.dataset.producto = JSON.stringify(producto);
            productSelect.appendChild(option);
        });
    }

    searchFilterInput.addEventListener('input', function () {
        const searchTerm = this.value.toLowerCase();
        Array.from(productSelect.options).forEach(option => {
            const text = option.textContent.toLowerCase();
            option.style.display = text.includes(searchTerm) ? '' : 'none';
        });
    });

    productSelect.addEventListener('dblclick', function () {
        const selectedOption = this.options[this.selectedIndex];
        if (!selectedOption || !selectedOption.value) return;

        // Parsear el objeto producto desde el dataset
        const productoData = JSON.parse(selectedOption.dataset.producto);
        agregarItemAOrden(productoData);
        productSearchModal.hide();
    });

    document.getElementById('productSearchModal').addEventListener('shown.bs.modal', function () {
        poblarProductosEnModal();
        searchFilterInput.focus();
    });

    function agregarItemAOrden(producto) {
        const template = itemTemplate.innerHTML.replace(/__prefix__/g, itemIndex);
        const newRow = document.createElement('tr');
        newRow.innerHTML = template;
        newRow.classList.add('item-row');

        // Usar el objeto producto completo
        newRow.querySelector('.product-id').value = producto.id;
        newRow.querySelector('.product-name').textContent = producto.nombre;
        newRow.querySelector('.unidad-display').textContent = format_product_units(producto);
        
        itemsContainer.appendChild(newRow);
        itemIndex++;
        updateUI();
    }
    // --- FIN LÓGICA DEL MODAL ---

    // Evento para eliminar una fila
    itemsContainer.addEventListener('click', function (e) {
        if (e.target.closest('.remove-item-btn')) {
            e.target.closest('.item-row').remove();
            updateUI();
        }
    });

    // Función para actualizar la UI (mensaje de "sin ítems")
    function updateUI() {
        noItemsMsg.style.display = itemsContainer.children.length > 0 ? 'none' : 'block';
    }

    // --- LÓGICA DE ENVÍO DEL FORMULARIO CON FETCH ---
    if (form && submitButton) {
        form.addEventListener('submit', function (event) {
            event.preventDefault(); // Prevenir el envío tradicional siempre

            const productosParaEnviar = [];
            const itemRows = itemsContainer.querySelectorAll('.item-row');

            if (itemRows.length === 0) {
                showNotificationModal('Error', 'Debe añadir al menos un producto para crear las órdenes de producción.', 'error');
                return;
            }
            
            let datosValidos = true;
            let cantidadInvalida = false;
            itemRows.forEach((row, index) => {
                const id = row.querySelector('.product-id').value;
                const cantidadInput = row.querySelector('.cantidad');
                const cantidad = parseInt(cantidadInput.value, 10);

                if (isNaN(cantidad) || cantidad <= 0) {
                    cantidadInput.classList.add('is-invalid');
                    datosValidos = false;
                    cantidadInvalida = true;
                } else {
                    cantidadInput.classList.remove('is-invalid');
                }

                productosParaEnviar.push({
                    id: id,
                    cantidad: cantidad
                });
            });

            if (cantidadInvalida) {
                showNotificationModal('Error', 'Por favor, ingrese una cantidad válida (mayor a cero) para todos los productos.', 'error');
                return;
            }

            const formData = new FormData(form);
            const payload = {
                fecha_meta: formData.get('fecha_meta'),
                observaciones: formData.get('observaciones'),
                productos: productosParaEnviar
            };
            
            submitButton.disabled = true;
            submitButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creando...`;

            fetch(CREAR_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': formData.get('csrf_token') 
                },
                body: JSON.stringify(payload)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotificationModal('Éxito', data.message || 'Órdenes de producción creadas correctamente.', 'success', () => {
                        window.location.href = data.redirect_url || '/ordenes/';
                    });
                } else {
                    showNotificationModal('Error', data.error || 'Ocurrió un error al crear las órdenes.', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotificationModal('Error de Red', 'No se pudo conectar con el servidor.', 'error');
            })
            .finally(() => {
                submitButton.disabled = false;
                submitButton.innerHTML = 'Guardar Órdenes de Producción';
            });
        });
    }

    function format_product_units(producto) {
        if (producto.unidad_medida && producto.unidad_medida.startsWith('paquete')) {
            if (producto.unidades_por_paquete > 1) {
                return `paquete(x${producto.unidades_por_paquete}u)`;
            } else if (producto.peso_por_paquete_valor > 0) {
                return `paquete(x${producto.peso_por_paquete_valor}${producto.peso_por_paquete_unidad})`;
            }
        }
        return producto.unidad_medida;
    }
});
