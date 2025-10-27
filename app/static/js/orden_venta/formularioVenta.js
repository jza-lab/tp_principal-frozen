document.addEventListener('DOMContentLoaded', function () {
    try {
        const container = document.getElementById('items-container');
        const addItemBtn = document.getElementById('add-item-btn');
        const itemTemplate = document.getElementById('item-template');
        const totalFormsInput = document.querySelector('input[name="items-TOTAL_FORMS"]');
        const noItemsMsg = document.getElementById('no-items-msg');
        const clienteIdOculto = document.getElementById('id_cliente');

        const recalculate = typeof window.calculateOrderTotals === 'function' ? window.calculateOrderTotals : () => { };
        const attachListeners = typeof window.attachItemListeners === 'function' ? window.attachItemListeners : () => { };
        
        if (!container || !totalFormsInput) {
            console.error("Faltan elementos esenciales (container o TOTAL_FORMS) para inicializar el formset de ítems.");
            return;
        }

        const prefix = 'items';

        function updateAvailableProducts() {
            const selectedProductIds = new Set();
            document.querySelectorAll('.producto-selector').forEach(select => {
                if (select.value) {
                    selectedProductIds.add(select.value);
                }
            });
            document.querySelectorAll('.producto-selector').forEach(currentSelect => {
                const currentValue = currentSelect.value;
                currentSelect.querySelectorAll('option[data-id]').forEach(option => {
                    const optionId = option.getAttribute('data-id');
                    option.disabled = false;
                    option.style.display = 'block';
                    if (selectedProductIds.has(optionId) && optionId !== currentValue) {
                        option.style.display = 'none';
                    }
                });
            });
        }

        /**
          * Helper para actualizar el índice de los campos en una fila.
          * @param {HTMLElement} el Elemento a actualizar.
          * @param {string} prefix Prefijo del formset (e.g., 'items').
          * @param {number} index Nuevo índice.
          */
        function updateElementIndex(el, prefix, index) {
            const idRegex = new RegExp('(' + prefix + '-\\d+-)(.*)');
            const replacement = prefix + '-' + index + '-$2';

            if (el.id) {
                el.id = el.id.replace(idRegex, replacement);
            }
            if (el.name) {
                el.name = el.name.replace(idRegex, replacement);
            }
        }

        function toggleNoItemsMessage() {
            if (noItemsMsg) {
                const rowCount = container.querySelectorAll('.item-row').length;
                noItemsMsg.style.display = rowCount === 0 ? 'block' : 'none';
            }
        }

        /**
          * Actualiza el stock visible cuando se selecciona un producto.
          * También se usa para cargar el stock inicial de filas existentes.
          * @param {Event|object} event - El objeto Event o un objeto simulado con el target.
          */
        function handleProductChange(event) {
            const select = event.target;
            const row = select.closest('.item-row');
            if (!row) return;

            const stockDisplay = row.querySelector('.stock-display');
            const cantidadInput = row.querySelector('.item-quantity');

            const selectedOption = select.options[select.selectedIndex];

            const stock = selectedOption ? (selectedOption.dataset.stock || 0) : 0;
            const unidad = (selectedOption && selectedOption.dataset.unidad) ? selectedOption.dataset.unidad : '';

            const esEntero = unidad.startsWith('paquete') || unidad === 'unidades';

            if (cantidadInput) {
                if (esEntero) {
                    cantidadInput.setAttribute('step', '1');
                    cantidadInput.setAttribute('min', '1');

                    const currentValue = parseFloat(cantidadInput.value);
                    if (!isNaN(currentValue) && currentValue > 1 && currentValue % 1 !== 0) {
                        cantidadInput.value = Math.floor(currentValue);
                    }

                } else {
                    cantidadInput.setAttribute('step', '0.01');
                    cantidadInput.setAttribute('min', '0.01');
                }
            }

            if (stockDisplay) {
                stockDisplay.textContent = parseFloat(stock).toFixed(1);
            }

            const unidadDisplay = row.querySelector('.unidad-display');
            if (unidadDisplay) {
                unidadDisplay.textContent = unidad || '--';
            }
            recalculate();
        }

        function reindexRows() {
            const rows = container.querySelectorAll('.item-row');
            let newIndex = 0;

            rows.forEach(row => {
                row.querySelectorAll('[name^="' + prefix + '-"], [id^="' + prefix + '-"]').forEach(el => {
                    updateElementIndex(el, prefix, newIndex);
                });
                const productSelect = row.querySelector('select[name$="-producto_id"]');
                const removeButton = row.querySelector('.remove-item-btn');

                attachListeners(row);

                if (productSelect) {
                    productSelect.removeEventListener('change', handleProductChange);
                    productSelect.addEventListener('change', handleProductChange);
                    productSelect.removeEventListener('change', updateAvailableProducts);
                    productSelect.addEventListener('change', updateAvailableProducts);
                    handleProductChange({ target: productSelect });
                }

                if (removeButton) {
                    removeButton.removeEventListener('click', removeItem);
                    removeButton.addEventListener('click', removeItem);
                }

                newIndex++;
            });
            if (totalFormsInput) {
                totalFormsInput.value = newIndex;
            }

            toggleNoItemsMessage();
            updateAvailableProducts();
            recalculate()
        }

        function addItem() {
            if (!itemTemplate || !totalFormsInput) return;
            const newIndex = parseInt(totalFormsInput.value, 10);
            const newRowContent = itemTemplate.content.cloneNode(true);
            const newRow = newRowContent.querySelector('.item-row');

            newRow.innerHTML = newRow.innerHTML.replace(/__prefix__/g, newIndex);

            container.appendChild(newRow);

            newRow.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest'
            });
            reindexRows();
            updateAvailableProducts();
        }
        window.addItemRow = addItem;

        /**
          * Elimina una fila de ítem.
          * @param {Event} event 
          */
        function removeItem(event) {
            const row = event.target.closest('.item-row');
            if (row) {
                const nextRow = row.nextElementSibling;
                row.remove();
                reindexRows(); 
                if (nextRow) {
                    nextRow.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
                updateAvailableProducts();
            }
        }
        if (addItemBtn) {
            addItemBtn.addEventListener('click', addItem);
        }
        reindexRows();
        updateAvailableProducts();

    } catch (e) {
        console.error("Error crítico en la inicialización del formset de pedidos:", e);
    }
});

const form = document.getElementById('pedido-form'); 
const itemsContainer = document.getElementById('items-container');


let initialAddressState = {};

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('pedido-form');
    if (!form) {
        console.error("No se encontró el formulario con id 'pedido-form'.");
        return;
    }
    if (isEditing) {
        initialAddressState = {
            calle: document.getElementById('calle').value,
            altura: document.getElementById('altura').value,
            piso: document.getElementById('piso').value,
            depto: document.getElementById('depto').value,
            localidad: document.getElementById('localidad').value,
            provincia: document.getElementById('provincia').value,
            codigo_postal: document.getElementById('codigo_postal').value
        };
    }
    form.addEventListener('submit', handleSubmit);
});


/**
 * Función ASÍNCRONA que maneja el envío del formulario.
 * Previene la recarga de la página, valida los datos y los envía al backend.
 * @param {Event} event - El evento 'submit' del formulario.
 */
async function handleSubmit(event) {
    event.preventDefault();
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;
    const form = event.target; 
    const itemsContainer = document.getElementById('items-container');
    if (!form.checkValidity()) {
        form.classList.add('was-validated');
        showNotificationModal('Campos Incompletos', 'Por favor, complete todos los campos obligatorios correctamente.', 'warning');
        return;
    }
    const itemRows = itemsContainer.querySelectorAll('.item-row');
    if (itemRows.length === 0) {
        showNotificationModal('Faltan Productos', 'Debe añadir al menos un producto al pedido.', 'error');
        itemsContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
    }
    let cantidadEsInvalida = false;
    let productoInvalido = '';

    itemRows.forEach(row => {
        const productoSelect = row.querySelector('select[name*="producto_id"]');
        const cantidadInput = row.querySelector('input[name*="cantidad"]');

        if (productoSelect && cantidadInput) {
            const selectedOption = productoSelect.options[productoSelect.selectedIndex];
            const unidad = selectedOption ? selectedOption.dataset.unidad : '';
            const cantidad = parseFloat(cantidadInput.value);
            const requiereEntero = unidad.startsWith('paquete') || unidad === 'unidades';
            if (requiereEntero && (cantidad % 1 !== 0)) {
                cantidadEsInvalida = true;
                productoInvalido = selectedOption.textContent.trim().split('(')[0].trim();
                cantidadInput.focus();
                return;
            }
        }
    });

    if (cantidadEsInvalida) {
        showNotificationModal(
            'Error en la Cantidad',
            `La cantidad para el producto "${productoInvalido}" debe ser un número entero (sin decimales), ya que se mide por unidades o paquetes.`,
            'error'
        );
        return;
    }

    // Si las validaciones pasan, removemos la clase para futuros envíos.
    form.classList.remove('was-validated');

    // 2. Construimos el objeto JSON (payload) que enviaremos al backend.
    const payload = buildPayload();
    console.log("Enviando Payload:", JSON.stringify(payload, null, 2));

    // 4. Damos feedback visual al usuario en el botón de envío.
    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    submitButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Guardando...`;

    // --- NUEVA LÓGICA DE VALIDACIÓN CONDICIONAL ---
    const addressHasChanged = () => {
        if (!isEditing) return true; // Siempre validar en creación
        const currentState = {
            calle: document.getElementById('calle').value,
            altura: document.getElementById('altura').value,
            piso: document.getElementById('piso').value,
            depto: document.getElementById('depto').value,
            localidad: document.getElementById('localidad').value,
            provincia: document.getElementById('provincia').value,
            codigo_postal: document.getElementById('codigo_postal').value
        };
        return JSON.stringify(currentState) !== JSON.stringify(initialAddressState);
    };

    if (payload.usar_direccion_alternativa && addressHasChanged()) {
        try {
            const direccionParaVerificar = payload.direccion_entrega;
            const verificationUrl = "/api/validar/direccion";

            const verificationResponse = await fetch(verificationUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(direccionParaVerificar),
            });

            const verificationResult = await verificationResponse.json();

            if (verificationResponse.ok && verificationResult.success) {
                await enviarDatos(payload, csrfToken);
            } else {
                let errorMessage = 'La dirección de entrega no es válida o no pudo ser verificada.';
                if (verificationResult && verificationResult.error) {
                    errorMessage = verificationResult.error;
                }
                showNotificationModal('Error de Dirección', errorMessage, 'error');
                form.classList.remove('was-validated');
                submitButton.disabled = false;
                submitButton.innerHTML = `<i class="bi bi-save me-1"></i> ${isEditing ? 'Actualizar Pedido' : 'Guardar Pedido'}`;
            }
        } catch (error) {
            console.error('Error de red al verificar la direccion:', error);
            showNotificationModal('Error de Conexión', 'No se pudo conectar con el servidor para verificar la dirección.', 'error');
            submitButton.disabled = false;
            submitButton.innerHTML = `<i class="bi bi-save me-1"></i> ${isEditing ? 'Actualizar Pedido' : 'Guardar Pedido'}`;
            return;
        }
    } else {
        // Si no se usa dirección alternativa, o si la dirección no ha cambiado, enviar los datos directamente
        await enviarDatos(payload, csrfToken);
    }


}

async function enviarDatos(payload, csrfToken) {
    const submitButton = form.querySelector('button[type="submit"]');
    const url = isEditing ? `/orden-venta/${pedidoId}/editar` : '/orden-venta/nueva';
    const method = isEditing ? 'PUT' : 'POST';

    let response;
    try {
        response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(payload),
        });

        const result = await response.json();

        if (response.ok) {

            // === MODIFICACIÓN CLAVE AQUÍ ===
            // 1. Usar el mensaje y título que vienen del backend
            const messageToShow = result.message || '¡Pedido guardado correctamente!';
            const titleToShow = result.data && result.data.estado_completado_inmediato ? '¡STOCK DISPONIBLE! Pedido Completado' : 'Éxito';

            // 2. Disparar el modal con el mensaje específico
            showNotificationModal(titleToShow, messageToShow, 'success');
            // ===============================

            setTimeout(() => {
                window.location.href = result.redirect_url || "{{ url_for('orden_venta.listar') }}";
            }, 2500);
        } else {
            showNotificationModal('Error al Guardar', 'No se pudo guardar el pedido. Por favor, revise los errores.', 'error');
        }

    } catch (error) {

        console.error('Error en la petición fetch:', error);

        showNotificationModal('Error de Conexión', 'Ocurrió un error inesperado al conectar con el servidor.', 'error');
    } finally {

        if (!response || !response.ok) {
            submitButton.disabled = false;
            submitButton.innerHTML = `<i class="bi bi-save me-1"></i> ${isEditing ? 'Actualizar Pedido' : 'Guardar Pedido'}`;
        }
    }
}

function buildPayload() {
    window.buildPayload = buildPayload;

    function cleanCurrency(value) {
        if (!value) return 0;
        const cleaned = value.toString().replace(/[$\s]/g, '').replace(/\./g, '').replace(',', '.');
        return parseFloat(cleaned) || 0;
    }

    const isClientForm = !!document.getElementById('cuil_cuit_cliente');

    if (document.getElementById('cuil_parte1') && document.getElementById('cuil_parte2') && document.getElementById('cuil_parte3')) {
        const cuilParte1 = document.getElementById('cuil_parte1').value;
        const cuilParte2 = document.getElementById('cuil_parte2').value;
        const cuilParte3 = document.getElementById('cuil_parte3').value;
        if (document.getElementById('cuil')) {
            document.getElementById('cuil').value = `${cuilParte1}-${cuilParte2}-${cuilParte3}`;
        }
    }

    const payload = {
        id_cliente: parseInt(document.getElementById('id_cliente').value),
        nombre_cliente: document.getElementById('nombre_cliente').value,
        fecha_solicitud: document.getElementById('fecha_solicitud')?.value,
        fecha_requerido: document.getElementById('fecha_requerido').value,
        estado: document.getElementById('estado')?.value || 'PENDIENTE',
        condicion_venta: document.getElementById('condicion_venta')?.value,
        precio_orden: cleanCurrency(document.getElementById('total-final').textContent),
        comentarios_adicionales: document.getElementById('comentarios_adicionales')?.value,
        items: []
    };
    const direccionControl = document.getElementById('usar_direccion_alternativa');
    const usar_alternativa = (direccionControl.type === 'checkbox')
        ? direccionControl.checked
        : (direccionControl.dataset.active === 'true');

    payload.usar_direccion_alternativa = usar_alternativa;

    if (usar_alternativa) {
        const idSuffix = isClientForm ? '_alternativa' : '';
        payload.direccion_entrega = {
            calle: document.getElementById(`calle${idSuffix}`).value,
            altura: document.getElementById(`altura${idSuffix}`).value,
            piso: document.getElementById(`piso${idSuffix}`)?.value || null,
            depto: document.getElementById(`depto${idSuffix}`)?.value || null,
            localidad: document.getElementById(`localidad${idSuffix}`).value,
            provincia: document.getElementById(`provincia${idSuffix}`).value,
            codigo_postal: document.getElementById(`codigo_postal${idSuffix}`).value
        };
    }
        const itemRows = document.querySelectorAll('#items-container .item-row');
        itemRows.forEach(row => {
            const productoSelect = row.querySelector('select[name*="producto_id"]');
            const cantidadInput = row.querySelector('input[name*="cantidad"]');
            const idInput = row.querySelector('input[name*="id"]');
            const precioUnitarioInput = row.querySelector('input[name*="precio_unitario"]');

            if (productoSelect && cantidadInput && productoSelect.value) {
                payload.items.push({
                    id: idInput?.value ? parseInt(idInput.value) : null,
                    producto_id: parseInt(productoSelect.value),
                    cantidad: parseFloat(cantidadInput.value) || 0,
                    precio_unitario: precioUnitarioInput ? parseFloat(precioUnitarioInput.value) : 0
                });
            }
        });

        return payload;
    }

    // Para asegurar que la función esté disponible globalmente después de redefinirla.
    window.buildPayload = buildPayload;

