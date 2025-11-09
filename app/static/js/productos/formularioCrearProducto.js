document.addEventListener('DOMContentLoaded', function () {
    const itemsContainer = document.getElementById('itemsContainer');
    const subtotalInput = document.getElementById('subtotal');
    const ivaCheckbox = document.getElementById('iva');
    const totalInput = document.getElementById('total');
    const addItemBtn = document.getElementById('addItemBtn');
    const porcentajeExtraInput = document.getElementById('porcentaje_extra');
    const formulario = document.getElementById('formulario-producto');
    const insumosData = typeof INSUMOS_DATA !== 'undefined' && Array.isArray(INSUMOS_DATA) ? INSUMOS_DATA : [];

    // [FUNCIONES DE FORMATO DE DINERO]

    function limpiarFormatoDinero(valorConFormato) {
        if (!valorConFormato) return 0;
        // 1. Eliminar '$' y espacios. 2. Reemplazar '.' (miles) por nada. 3. Reemplazar ',' (decimal) por '.'.
        const cleanString = valorConFormato.toString().replace(/[$.]/g, '').replace(/[^\d,]/g, '');
        const numeroSinFormato = cleanString.replace(',', '.');
        return parseFloat(numeroSinFormato) || 0;
    }

    function formatearADinero(numero) {
        if (isNaN(numero) || numero === null) return '$ 0,00';
        
        const numeroRedondeado = Math.round(numero * 100) / 100;

        const formatter = new Intl.NumberFormat('es-AR', {
            style: 'currency',
            currency: 'ARS',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });

        return formatter.format(numeroRedondeado);
    }
    
    // [FUNCIÓN DE ACTUALIZACIÓN DE UNIDAD]
    function updateUnitDisplay(row) {
        const selector = row.querySelector('.insumo-selector');
        const unidadDisplay = row.querySelector('.unidad-receta-display');
        
        const selectedOption = selector.options[selector.selectedIndex];
        const unidad = selectedOption ? selectedOption.dataset.unidad : '';
        
        if (unidadDisplay) {
            unidadDisplay.textContent = unidad ? `(${unidad})` : '';
        }
    }

    function calcularTotales() {
        let subtotalTotal = 0;
        itemsContainer.querySelectorAll('.item-row').forEach(row => {
            updateUnitDisplay(row); 
            
            const precioInput = row.querySelector('.precio_unitario');
            const cantidadInput = row.querySelector('.cantidad');
            
            const cantidad = parseFloat(cantidadInput.value) || 0;
            // [CORRECCIÓN DE ÁMBITO Y FUNCIÓN] Aseguramos que precio sea el valor limpio del input
            const precio = limpiarFormatoDinero(precioInput.value); 
            
            const subtotal = cantidad * precio;
            
            // Aplicar formato
            row.querySelector('.subtotal-item').value = formatearADinero(subtotal);
            
            subtotalTotal += subtotal;
        });

        // Aplicar formato a Subtotal General y Total
        subtotalInput.value = formatearADinero(subtotalTotal);

        const porcentaje = parseFloat(porcentajeExtraInput.value) || 0;
        let total = subtotalTotal * (1 + ( porcentaje / 100));

        if (ivaCheckbox.checked) {
            total *= 1.21;
        }
        
        totalInput.value = formatearADinero(total);
    }

    function updateAvailableInsumos() {
        const selectedInsumoIds = new Set();
        // ... (resto del código de exclusión de insumos) ...
        itemsContainer.querySelectorAll('.insumo-selector').forEach(select => {
            if (select.value) {
                selectedInsumoIds.add(select.value);
            }
        });

        itemsContainer.querySelectorAll('.insumo-selector').forEach(currentSelect => {
            const currentValue = currentSelect.value;
            currentSelect.querySelectorAll('option[data-id]').forEach(option => {
                const optionId = option.getAttribute('data-id');
                option.disabled = selectedInsumoIds.has(optionId) && optionId !== currentValue;
                option.hidden = selectedInsumoIds.has(optionId) && optionId !== currentValue;
            });
        });
    }
    
    // [EVENT LISTENER: INPUT] Manejo de input de cantidad
    itemsContainer.addEventListener('input', function (e) {
        if (e.target.classList.contains('cantidad')) {
            const row = e.target.closest('.item-row');
            const precioInput = row.querySelector('.precio_unitario');

            const precio = limpiarFormatoDinero(precioInput.value) || 0;
            const cantidad = parseFloat(e.target.value) || 0;
            const subtotal = cantidad * precio;

            row.querySelector('.subtotal-item').value = formatearADinero(subtotal);
            
            calcularTotales();
        }
    });

    // [EVENT LISTENER: CHANGE] Manejo de cambio de insumo
    itemsContainer.addEventListener('change', function (e) {
        if (e.target.classList.contains('insumo-selector')) {
            const option = e.target.selectedOptions[0];
            const row = e.target.closest('.item-row');
            
            // Actualizar unidad y precio
            updateUnitDisplay(row); 

            const rawPrice = parseFloat(option.dataset.precio) || 0;
            row.querySelector('.precio_unitario').value = formatearADinero(rawPrice); 

            // Recalcular subtotal
            const cantidadInput = row.querySelector('.cantidad');
            const cantidad = parseFloat(cantidadInput.value) || 0;
            const subtotal = cantidad * rawPrice;
            
            row.querySelector('.subtotal-item').value = formatearADinero(subtotal);
            
            calcularTotales();
            updateAvailableInsumos();
        }
    });

    porcentajeExtraInput.addEventListener('input', calcularTotales);
    ivaCheckbox.addEventListener('change', calcularTotales);

    // [FUNCIÓN CLAVE: AÑADIR ITEM SIN TEMPLATE]
    addItemBtn.addEventListener('click', function () {
        const row = document.createElement('div');
        row.className = 'row g-3 align-items-end item-row mb-2';

        let optionsHtml = '<option value="">Seleccione un insumo...</option>';
        insumosData.forEach(insumo => {
            optionsHtml += `<option value="${insumo.id}" data-id="${insumo.id}" data-unidad="${insumo.unidad_medida}" data-precio="${insumo.precio_unitario}">${insumo.nombre}</option>`;
        });

        // Generación de HTML como string (sin usar <template>)
        row.innerHTML = `
            <div class="col-md-4">
                <label class="form-label">Insumo</label>
                <select class="form-select insumo-selector" name="insumo_id[]" required>${optionsHtml}</select>
            </div>
            <div class="col-md-2">
                <label class="form-label">Cantidad <span class="unidad-receta-display"></span></label>
                <input type="number" min="0.01" step="0.01" max="5000" class="form-control cantidad" name="cantidad[]" value="1" required>
            </div>
            <div class="col-md-2">
                <label class="form-label">Precio Unitario</label>
                <input type="text" class="form-control precio_unitario" name="precio_unitario[]" readonly>
            </div>
            <div class="col-md-2">
                <label class="form-label">Subtotal</label>
                <input type="text" class="form-control subtotal-item" value="${formatearADinero(0.00)}" readonly>
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-outline-danger removeItemBtn">Eliminar</button>
            </div>
        `;
        itemsContainer.appendChild(row);
        updateAvailableInsumos();
    });


    itemsContainer.addEventListener('click', function (e) {
        if (e.target.classList.contains('removeItemBtn')) {
            e.target.closest('.item-row').remove();
            calcularTotales();
            updateAvailableInsumos();
        }
    });

    // [INICIALIZACIÓN DE FORMATO Y UNIDADES]
    document.querySelectorAll('#itemsContainer .item-row').forEach(row => {
        updateUnitDisplay(row);
        
        const precioInput = row.querySelector('.precio_unitario');
        const subtotalInput = row.querySelector('.subtotal-item');
    
        // [CORRECCIÓN] Priorizar parseFloat para valores numéricos directos.
        // limpiarFormatoDinero se usa como fallback si el valor ya tiene formato de moneda.
        const precioLimpio = parseFloat(precioInput.value) || limpiarFormatoDinero(precioInput.value) || 0;
        precioInput.value = formatearADinero(precioLimpio);
    
        // Formatear Subtotal Item (corregido de la misma manera)
        const rawSubtotal = parseFloat(subtotalInput.value) || limpiarFormatoDinero(subtotalInput.value) || 0;
        subtotalInput.value = formatearADinero(rawSubtotal);
    });

    calcularTotales();
    updateAvailableInsumos();

 const form = document.getElementById('formulario-producto');
    form.addEventListener('submit', async function (event) {
        event.preventDefault();
        event.stopPropagation();
        
        if (!form.checkValidity()) {
            form.classList.add('was-validated');
            return;
        }

        const formData = new FormData(form);

        const unidadMedida = formData.get('unidad_medida');

        let unidadesPorPaquete = 1;
        let pesoPorPaqueteValor = 0;
        let pesoPorPaqueteUnidad = 'kg';
        
        let unidadMedidaFinal = unidadMedida;

        if ( unidadMedida === 'paquete') {
            const tipoPaquete = document.getElementById('tipo_paquete').value;

            if (tipoPaquete === 'unidades') {
                unidadesPorPaquete = parseInt(document.getElementById('unidades_por_paquete').value) || 1;
                // Formato de unidad para la BD: 'paquete(x12u)'
                unidadMedidaFinal = `paquete(x${unidadesPorPaquete}u)`; 

            } else if (tipoPaquete === 'peso_volumen') {
                pesoPorPaqueteValor = parseFloat(document.getElementById('peso_por_paquete_valor').value) || 0.01;
                pesoPorPaqueteUnidad = document.getElementById('peso_por_paquete_unidad').value || 'kg';
                // Formato de unidad para la BD: 'paquete(x1.5kg)'
                unidadMedidaFinal = `paquete(x${pesoPorPaqueteValor}${pesoPorPaqueteUnidad})`; 
            }
        }

        const productoData = {
            codigo: formData.get('codigo'),
            nombre: formData.get('nombre'),
            categoria: formData.get('categoria'),
            // Usamos la unidad_medida con el sufijo (x...) para que el backend sepa si es por unidad o peso.
            unidad_medida: unidadMedidaFinal, 
            descripcion: formData.get('descripcion'),
            porcentaje_extra: formData.get('porcentaje_extra'),
            iva: formData.get('iva') === '1',
            precio_unitario: limpiarFormatoDinero(document.getElementById('total').value) || 0,
            unidades_por_paquete: unidadesPorPaquete,
            peso_por_paquete_valor: pesoPorPaqueteValor,
            peso_por_paquete_unidad: pesoPorPaqueteUnidad,
            receta_items: []
        };

        const itemRows = itemsContainer.querySelectorAll('.item-row');

        if (itemRows.length === 0) {
            showNotificationModal('No se ha asignado una receta al producto', 'Por favor, ingrese al menos un ingrediente para crear el producto.', 'warning');
            return;
        }

        itemRows.forEach(row => {
            const selector = row.querySelector('.insumo-selector');
            const selectedOption = selector.options[selector.selectedIndex];
            const insumoId = selector.value;
            const cantidad = parseFloat(row.querySelector('.cantidad').value);

            if (insumoId && cantidad && selectedOption.dataset.unidad) {
                productoData.receta_items.push({
                    id_insumo: insumoId,
                    cantidad: cantidad,
                    unidad_medida: selectedOption.dataset.unidad
                });
            }
        });

        if (productoData.receta_items.length === 0) {
            showNotificationModal('Receta Vacía', 'Debe especificar el insumo y la cantidad para cada ítem de la receta.', 'error');
            return;
        }

        const url = isEditBoolean ? `/catalogo/actualizar/${ID_producto}` : '/catalogo/nuevo';
        const method = isEditBoolean ? 'PUT' : 'POST';

        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(productoData)
            });

            const result = await response.json();

            if (response.ok && result.success) {
                let mensaje;
                if (isEditBoolean) {
                    mensaje = 'Se ha modificado el producto correctamente.'
                }
                else {
                    mensaje = 'Se creó el producto exitosamente.'
                }
                showNotificationModal(result.message || 'Operación exitosa', mensaje);
                setTimeout(() => { window.location.href = productoS_LISTA_URL; }, 1500);
            } else {
                let errorMessage = 'Ocurrió un error.';
                if (result && result.error) {
                    errorMessage = typeof result.error === 'object' ? Object.values(result.error).flat().join('\n') : result.error;
                }
                showNotificationModal(errorMessage, 'error');
            }
        } catch (error) {
            console.error('Error en el fetch:', error);
            showNotificationModal('No se pudo conectar con el servidor.', 'Por favor, intente nuevamente más tarde o contacte a administración.');
        }
    });
});