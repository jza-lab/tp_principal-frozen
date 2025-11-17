document.addEventListener('DOMContentLoaded', function () {
    const itemsContainer = document.getElementById('items-container');
    const form = document.getElementById('pedido-form');

    if (!itemsContainer || !form) {
        console.error("Elementos clave del formulario no encontrados (items-container o pedido-form).");
        return;
    }

    // --- LÓGICA CENTRALIZADA DE EVENTOS PARA LA TABLA DE ÍTEMS ---
    
    // 1. ELIMINAR ÍTEM
    itemsContainer.addEventListener('click', function (event) {
        if (event.target.closest('.remove-item-btn')) {
            const row = event.target.closest('.item-row');
            if (row) {
                row.remove();
                reindexarFilas();
                window.calculateOrderTotals();
                if (window.updateProformaButtonState) {
                    window.updateProformaButtonState();
                }
            }
        }
    });

    // 2. RECALCULAR TOTALES AL CAMBIAR CANTIDAD
    itemsContainer.addEventListener('input', function (event) {
        if (event.target.classList.contains('item-quantity')) {
            window.calculateOrderTotals();
        }
    });
    
    // --- FUNCIÓN DE REINDEXADO (ESENCIAL PARA FORMSETS) ---
    function reindexarFilas() {
        const rows = itemsContainer.querySelectorAll('.item-row');
        const totalFormsInput = document.getElementById('id_items-TOTAL_FORMS');
        const noItemsMsg = document.getElementById('no-items-msg');
        
        rows.forEach((row, index) => {
            row.querySelectorAll('[name^="items-"]').forEach(input => {
                const name = input.getAttribute('name');
                if (name) {
                    const newName = name.replace(/items-\d+-/, `items-${index}-`);
                    input.setAttribute('name', newName);
                }
            });
        });

        if (totalFormsInput) {
            totalFormsInput.value = rows.length;
        }
        
        if (noItemsMsg) {
            noItemsMsg.style.display = rows.length === 0 ? 'block' : 'none';
        }
    }
    
    // --- LÓGICA DE ENVÍO DEL FORMULARIO ---
    form.addEventListener('submit', handleSubmit);
    
    // --- INICIALIZACIÓN AL CARGAR LA PÁGINA ---
    reindexarFilas();
    window.calculateOrderTotals();
});

async function handleSubmit(event) {
    event.preventDefault();
    const form = event.target;
    // ... (El resto de la lógica de handleSubmit, enviarDatos, buildPayload que ya estaba bien)
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;
    const itemsContainer = document.getElementById('items-container');
    if (!form.checkValidity()) {
        form.classList.add('was-validated');
        showNotificationModal('Campos Incompletos', 'Por favor, complete todos los campos obligatorios correctamente.', 'warning');
        return;
    }
    const itemRows = itemsContainer.querySelectorAll('.item-row');
    if (itemRows.length === 0) {
        showNotificationModal('Faltan Productos', 'Debe añadir al menos un producto al pedido.', 'error');
        return;
    }

    let invalidQuantity = false;
    itemRows.forEach(row => {
        const cantidadInput = row.querySelector('input[name*="cantidad"]');
        if (parseInt(cantidadInput.value, 10) === 0) {
            invalidQuantity = true;
        }
    });

    if (invalidQuantity) {
        showNotificationModal('Cantidad Inválida', 'No puede haber productos con cantidad 0.', 'error');
        return;
    }

    const payload = buildPayload();
    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    submitButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Guardando...`;

    await enviarDatos(payload, csrfToken);
}

async function enviarDatos(payload, csrfToken) {
    const form = document.getElementById('pedido-form');
    const submitButton = form.querySelector('button[type="submit"]');
    const url = isEditing ? `/orden-venta/${pedidoId}/editar` : (typeof CREAR_URL !== 'undefined' ? CREAR_URL : '/orden-venta/nueva');
    const method = isEditing ? 'PUT' : 'POST';

    try {
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (response.ok) {
            showNotificationModal('Éxito', result.message || 'Pedido guardado.', 'success', () => {
                window.location.href = result.redirect_url || "/orden-venta/";
            });
        } else {
            showNotificationModal('Error', result.error || 'No se pudo guardar el pedido.', 'error');
            submitButton.disabled = false;
            submitButton.innerHTML = `<i class="bi bi-save me-1"></i> ${isEditing ? 'Actualizar Pedido' : 'Guardar Pedido'}`;
        }
    } catch (error) {
        showNotificationModal('Error de Conexión', 'Ocurrió un error al conectar con el servidor.', 'error');
        submitButton.disabled = false;
        submitButton.innerHTML = `<i class="bi bi-save me-1"></i> ${isEditing ? 'Actualizar Pedido' : 'Guardar Pedido'}`;
    }
}

function buildPayload() {
    const form = document.getElementById('pedido-form');
    const formData = new FormData(form);
    const payload = {
        id_cliente: parseInt(formData.get('id_cliente')),
        nombre_cliente: formData.get('nombre_cliente'),
        fecha_solicitud: formData.get('fecha_solicitud'),
        fecha_requerido: formData.get('fecha_requerido'),
        estado: formData.get('estado') || 'PENDIENTE',
        condicion_venta: formData.get('condicion_venta'),
        comentarios_adicionales: formData.get('comentarios_adicionales'),
        items: []
    };
    
    const itemRows = document.querySelectorAll('#items-container .item-row');
    itemRows.forEach(row => {
        const productoSelect = row.querySelector('select[name*="producto_id"]');
        const cantidadInput = row.querySelector('input[name*="cantidad"]');
        const idInput = row.querySelector('input[name*="id"]');
        
        if (productoSelect && cantidadInput && productoSelect.value) {
            const priceDisplay = row.querySelector('.price-display');
            let precioUnitario = 0;
            if(priceDisplay && priceDisplay.value){
                const cleanedPrice = priceDisplay.value.replace(/[$\s.]/g, '').replace(',', '.');
                precioUnitario = parseFloat(cleanedPrice) || 0;
            }

            payload.items.push({
                id: idInput?.value ? parseInt(idInput.value) : null,
                producto_id: parseInt(productoSelect.value),
                cantidad: parseInt(cantidadInput.value, 10) || 0,
                precio_unitario: precioUnitario
            });
        }
    });

    let totalPedido = 0;
    payload.items.forEach(item => {
        totalPedido += item.cantidad * item.precio_unitario;
    });
    payload.precio_orden = totalPedido;
    
    return payload;
}
