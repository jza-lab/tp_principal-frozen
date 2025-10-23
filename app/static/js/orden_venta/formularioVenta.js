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

        // Si faltan elementos esenciales, salimos para evitar errores de null
        if (!container || !totalFormsInput) {
            console.error("Faltan elementos esenciales (container o TOTAL_FORMS) para inicializar el formset de ítems.");
            return;
        }

        // Prefijo utilizado por el formset framework (e.g., 'items')
        const prefix = 'items';

        /**
         * Gestiona la exclusión de productos ya seleccionados en otros selectores.
         * Deshabilita las opciones para evitar duplicados.
         */
        function updateAvailableProducts() {
            // 1. Recopilar todos los IDs de producto seleccionados en CUALQUIER fila.
            const selectedProductIds = new Set();
            document.querySelectorAll('.producto-selector').forEach(select => {
                if (select.value) {
                    selectedProductIds.add(select.value);
                }
            });

            // 2. Iterar sobre todos los selectores para aplicar la exclusión.
            document.querySelectorAll('.producto-selector').forEach(currentSelect => {
                const currentValue = currentSelect.value;

                // Iterar sobre todas las opciones con data-id
                currentSelect.querySelectorAll('option[data-id]').forEach(option => {
                    const optionId = option.getAttribute('data-id');

                    // Habilitar la opción por defecto (limpiar el estado anterior)
                    option.disabled = false;
                    option.style.display = 'block';

                    // 3. Lógica de Inhabilitación:
                    // Deshabilita la opción si ha sido seleccionada, Y NO es la opción actual de ESTA fila.
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
            // Expresión regular para encontrar el índice anterior (e.g., -0-, -1-, etc.)
            const idRegex = new RegExp('(' + prefix + '-\\d+-)(.*)');
            // El reemplazo se hará con el nuevo índice
            const replacement = prefix + '-' + index + '-$2';

            if (el.id) {
                el.id = el.id.replace(idRegex, replacement);
            }
            if (el.name) {
                el.name = el.name.replace(idRegex, replacement);
            }
        }

        /**
          * Gestiona la visibilidad del mensaje "Añada productos".
          */
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

            // Verificación defensiva
            if (!row) return;

            const stockDisplay = row.querySelector('.stock-display');
            // Nota: Se asume que el input de cantidad tiene la clase 'item-quantity'
            const cantidadInput = row.querySelector('.item-quantity');

            // Buscamos la opción seleccionada
            const selectedOption = select.options[select.selectedIndex];

            // Obtiene el stock y la unidad del atributo data-* de la opción seleccionada
            const stock = selectedOption ? (selectedOption.dataset.stock || 0) : 0;
            const unidad = (selectedOption && selectedOption.dataset.unidad) ? selectedOption.dataset.unidad : '';

            // --- LÓGICA DE CONTROL DE DECIMALES Y STEP ---
            // Es entero si la unidad es 'unidades' O si empieza con 'paquete'
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

        /**
          * Re-indexa todas las filas después de una adición o eliminación.
          */
        function reindexRows() {
            const rows = container.querySelectorAll('.item-row');
            let newIndex = 0;

            rows.forEach(row => {
                // Re-indexar todos los elementos con atributos 'name' o 'id' que empiecen con el prefijo
                row.querySelectorAll('[name^="' + prefix + '-"], [id^="' + prefix + '-"]').forEach(el => {
                    updateElementIndex(el, prefix, newIndex);
                });

                // Re-adjuntar listeners y actualizar stock para la fila re-indexada
                const productSelect = row.querySelector('select[name$="-producto_id"]');
                const removeButton = row.querySelector('.remove-item-btn');

                attachListeners(row);

                if (productSelect) {
                    // Limpiar y adjuntar listener de cambio de producto/stock
                    productSelect.removeEventListener('change', handleProductChange);
                    productSelect.addEventListener('change', handleProductChange);

                    // Limpiar y adjuntar listener para la EXCLUSIÓN DE PRODUCTOS
                    productSelect.removeEventListener('change', updateAvailableProducts);
                    productSelect.addEventListener('change', updateAvailableProducts);

                    // Llamar a handleProductChange para actualizar el stock visible
                    handleProductChange({ target: productSelect });
                }

                if (removeButton) {
                    // Limpiar y adjuntar listener de eliminación
                    removeButton.removeEventListener('click', removeItem);
                    removeButton.addEventListener('click', removeItem);
                }

                newIndex++;
            });

            // Actualizar TOTAL_FORMS
            if (totalFormsInput) {
                totalFormsInput.value = newIndex;
            }

            toggleNoItemsMessage();
            updateAvailableProducts();
            recalculate()
        }

        /**
          * Añade una nueva fila de ítem.
          */
        function addItem() {
            if (!itemTemplate || !totalFormsInput) return;

            // Clonar la plantilla y reemplazar el prefijo con el índice actual
            const newIndex = parseInt(totalFormsInput.value, 10);
            const newRowContent = itemTemplate.content.cloneNode(true);
            const newRow = newRowContent.querySelector('.item-row');

            newRow.innerHTML = newRow.innerHTML.replace(/__prefix__/g, newIndex);

            container.appendChild(newRow);

            newRow.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest'
            });

            // La reindexación se encarga de adjuntar los listeners
            reindexRows();

            // Aplicar la lógica de exclusión después de añadir una fila
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
                reindexRows(); // Reindexar después de eliminar
                if (nextRow) {
                    // Usamos 'start' para alinear el tope del nuevo elemento con el tope de la vista,
                    // lo cual obliga al scroll a moverse hacia arriba para seguir el contenido.
                    nextRow.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }

                // Re-habilitar los productos después de eliminar una fila
                updateAvailableProducts();
            }
        }

        // --- Inicialización y Event Listeners ---

        // 1. Botón de añadir ítem
        if (addItemBtn) {
            addItemBtn.addEventListener('click', addItem);
        }

        // 2. Inicializar listeners para filas existentes (al cargar la página)
        reindexRows();

        // 3. Aplicar la lógica de exclusión inicial para cualquier producto precargado
        updateAvailableProducts();

    } catch (e) {
        console.error("Error crítico en la inicialización del formset de pedidos:", e);
    }
});

const form = document.getElementById('pedido-form'); // Usamos el ID del formulario en tu HTML
const itemsContainer = document.getElementById('items-container');


// Espera a que el DOM esté completamente cargado para ejecutar el script.
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('pedido-form');
    if (!form) {
        console.error("No se encontró el formulario con id 'pedido-form'.");
        return;
    }

    // Asociamos la función handleSubmit al evento 'submit' del formulario.
    form.addEventListener('submit', handleSubmit);
});


/**
 * Función ASÍNCRONA que maneja el envío del formulario.
 * Previene la recarga de la página, valida los datos y los envía al backend.
 * @param {Event} event - El evento 'submit' del formulario.
 */
async function handleSubmit(event) {
    // 1. Prevenimos que la página se recargue (comportamiento por defecto del formulario).
    event.preventDefault();

    // --- VALIDACIONES DEL LADO DEL CLIENTE ---
    const form = event.target; // Obtenemos el formulario desde el evento
    const itemsContainer = document.getElementById('items-container');

    // Validación A: Campos requeridos, patrones, etc. de HTML5
    if (!form.checkValidity()) {
        form.classList.add('was-validated');
        // MODIFICADO: Usamos el modal personalizado
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

    if (payload.usar_direccion_alternativa) {
        try {
            const direccionParaVerificar = payload.direccion_entrega;
            const verificationUrl = "/api/validar/direccion";

            const verificationResponse = await fetch(verificationUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(direccionParaVerificar),
            });

            const verificationResult = await verificationResponse.json();

            if (verificationResponse.ok && verificationResult.success) {
                await enviarDatos(payload);
            } else {
                let errorMessage = 'Dirección no válida o error de verificación.';
                if (verificationResult && verificationResult.error) {
                    errorMessage = verificationResult.error;
                }
                showNotificationModal(errorMessage, 'Error al verificar la dirección');
                form.classList.remove('was-validated');
                submitButton.disabled = false;
                submitButton.innerHTML = `<i class="bi bi-save me-1"></i> ${isEditing ? 'Actualizar Pedido' : 'Guardar Pedido'}`;
            }
        } catch (error) {
            console.error('Error de red al verificar la direccion:', error);
            showNotificationModal('No se pudo conectar con el servidor de verificación.', 'error');
            submitButton.disabled = false;
            submitButton.innerHTML = `<i class="bi bi-save me-1"></i> ${isEditing ? 'Actualizar Pedido' : 'Guardar Pedido'}`;
            return;
        }
    } else {
        // Si no se usa dirección alternativa, enviar los datos directamente
        await enviarDatos(payload);
    }


}

async function enviarDatos(payload) {
    const submitButton = form.querySelector('button[type="submit"]');
    const url = isEditing ? `/orden-venta/${pedidoId}/editar` : '/orden-venta/nueva';
    const method = isEditing ? 'PUT' : 'POST';

    let response;
    try {
        response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
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
        // 1. Remover $ y espacios. 2. Reemplazar punto (miles) por nada. 3. Reemplazar coma (decimal) por punto.
        const cleaned = value.toString().replace(/[$\s]/g, '').replace(/\./g, '').replace(',', '.');
        return parseFloat(cleaned) || 0;
    }

    const cuilParte1 = document.getElementById('cuil_parte1').value;
    const cuilParte2 = document.getElementById('cuil_parte2').value;
    const cuilParte3 = document.getElementById('cuil_parte3').value;
    document.getElementById('cuil').value = `${cuilParte1}-${cuilParte2}-${cuilParte3}`;

    const payload = {
        id_cliente: parseInt(document.getElementById('id_cliente').value),
        nombre_cliente: document.getElementById('nombre_cliente').value,
        fecha_solicitud: document.getElementById('fecha_solicitud').value,
        fecha_requerido: document.getElementById('fecha_requerido').value,
        estado: document.getElementById('estado') ? document.getElementById('estado').value : 'PENDIENTE',
        precio_orden: cleanCurrency(document.getElementById('total-final').value),
        comentarios_adicionales: document.getElementById('comentarios_adicionales').value,
        usar_direccion_alternativa: document.getElementById('usar_direccion_alternativa').checked,
        items: []
    };

    if (payload.usar_direccion_alternativa) {
        payload.direccion_entrega = {
            calle: document.getElementById('calle').value,
            altura: document.getElementById('altura').value,
            piso: document.getElementById('piso').value || null,
            depto: document.getElementById('depto').value || null,
            localidad: document.getElementById('localidad').value,
            provincia: document.getElementById('provincia').value,
            codigo_postal: document.getElementById('codigo_postal').value
        };
    }

    const itemRows = document.querySelectorAll('#items-container .item-row');
    itemRows.forEach(row => {
        const productoSelect = row.querySelector('select[name*="producto_id"]');
        const cantidadInput = row.querySelector('input[name*="cantidad"]');
        const idInput = row.querySelector('input[name*="id"]');
        // INICIO MODIFICACIÓN: Referencia al campo hidden del precio unitario
        const precioUnitarioInput = row.querySelector('input[name*="precio_unitario"]');
        // FIN MODIFICACIÓN
        
        if (productoSelect && cantidadInput && productoSelect.value) {
            payload.items.push({
                id: idInput && idInput.value ? parseInt(idInput.value) : null,
                producto_id: parseInt(productoSelect.value),
                cantidad: parseFloat(cantidadInput.value) || 0, // Usar parseFloat para la cantidad para mayor robustez
                // INICIO MODIFICACIÓN: Añadir el precio unitario del campo hidden
                precio_unitario: precioUnitarioInput ? parseFloat(precioUnitarioInput.value) : 0 
                // FIN MODIFICACIÓN
            });
        }
    });

    return payload;
}

window.buildPayload = buildPayload;