document.addEventListener('DOMContentLoaded', function () {
    const itemsContainer = document.getElementById('itemsContainer');
    const subtotalInput = document.getElementById('subtotal');
    const ivaCheckbox = document.getElementById('iva');
    const totalInput = document.getElementById('total');
    const addItemBtn = document.getElementById('addItemBtn');

    // Mapeo de insumos para facilitar la construcción de opciones
    const insumosData = typeof INSUMOS_DATA !== 'undefined' && Array.isArray(INSUMOS_DATA) ? INSUMOS_DATA : [];

    /**
     * Calcula los subtotales de las filas, el subtotal general y el total con/sin IVA.
     * También llama a la función de exclusión de insumos.
     */
    function calcularSubtotales() {
        let subtotalTotal = 0;
        document.querySelectorAll('.item-row').forEach(row => {
            // Usamos parseFloat y toFixed(2) para manejo de moneda
            const cantidad = parseFloat(row.querySelector('.cantidad').value) || 0;
            const precio = parseFloat(row.querySelector('.precio_unitario').value) || 0;
            const subtotal = cantidad * precio;
            
            row.querySelector('.subtotal-item').value = subtotal.toFixed(2);
            subtotalTotal += subtotal;
        });

        subtotalInput.value = subtotalTotal.toFixed(2);

        // Cálculo de Total con IVA
        let total = subtotalTotal;
        if (ivaCheckbox.checked) {
            total += subtotalTotal * 0.21;
        }
        totalInput.value = total.toFixed(2);
        
        // Llamada a la función de exclusión
        updateAvailableInsumos(); 
    }

    /**
     * Itera sobre todos los selectores de insumos, recopila los IDs ya usados
     * y deshabilita esas opciones en los demás selectores.
     */
    function updateAvailableInsumos() {
        // 1. Recopilar todos los IDs de insumos seleccionados.
        const selectedInsumoIds = new Set();
        document.querySelectorAll('.insumo-selector').forEach(select => {
            if (select.value) {
                selectedInsumoIds.add(select.value);
            }
        });

        // 2. Iterar sobre todos los selectores para aplicar la exclusión.
        document.querySelectorAll('.insumo-selector').forEach(currentSelect => {
            const currentValue = currentSelect.value;
            
            // Iterar sobre todas las opciones con data-id
            currentSelect.querySelectorAll('option[data-id]').forEach(option => {
                const optionId = option.getAttribute('data-id');

                // Habilitar la opción por defecto (limpiar el estado anterior)
                option.disabled = false;
                option.hidden = false; // Opcional: para asegurarnos de que sean visibles

                // 3. Lógica de Inhabilitación:
                // Deshabilita la opción si ha sido seleccionada, Y NO es la opción actual de ESTA fila.
                if (selectedInsumoIds.has(optionId) && optionId !== currentValue) {
                    option.disabled = true;
                }
            });
        });
    }

    // -------------------------------------------------------------------------
    // Eventos 
    // -------------------------------------------------------------------------

    // Eventos para inputs existentes (Cantidad, Precio, y Checkbox de IVA)
    itemsContainer.addEventListener('input', function(e) {
        // Ejecuta cálculo solo si el input es de cantidad o precio
        if (e.target.classList.contains('cantidad') || e.target.classList.contains('precio_unitario')) {
            calcularSubtotales();
        }
    });
    
    // Evento de cambio para los selectores de insumos
    itemsContainer.addEventListener('change', function(e) {
        // Ejecuta exclusión y cálculo si el cambio viene de un selector de insumo
        if (e.target.classList.contains('insumo-selector')) {
            calcularSubtotales();
            // No es necesario llamar updateAvailableInsumos aquí, ya está en calcularSubtotales()
        }
    });

    // Evento de IVA
    ivaCheckbox.addEventListener('change', calcularSubtotales);

    // Añadir ítem
    addItemBtn.addEventListener('click', function () {
        const row = document.createElement('div');
        row.className = 'row g-3 align-items-end item-row mb-2';

        let optionsHtml = '<option value="" data-id="">Seleccione un insumo...</option>';
        insumosData.forEach(insumo => {
            // Incluimos data-id en las opciones generadas
            optionsHtml += `<option value="${insumo.id}" data-id="${insumo.id}">${insumo.nombre}</option>`;
        });

        row.innerHTML = `
            <div class="col-md-4">
                <label class="form-label">Insumo</label>
                <select class="form-select insumo-selector" name="insumo_id[]">
                    ${optionsHtml}
                </select>
            </div>
            <div class="col-md-2">
                <label class="form-label">Cantidad</label>
                <input type="number" min="1" max="5000" step="0.1" class="form-control cantidad" name="cantidad_solicitada[]" value="1">
            </div>
            <div class="col-md-2">
                <label class="form-label">Precio Unitario</label>
                <input type="number" step="0.01" min="1" class="form-control precio_unitario" name="precio_unitario[]" value="1.00">
            </div>
            <div class="col-md-2">
                <label class="form-label">Subtotal</label>
                <input type="number" step="0.01" min="1" class="form-control subtotal-item" value="1.00" readonly>
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-outline-danger removeItemBtn">Eliminar</button>
            </div>
        `;
        itemsContainer.appendChild(row);
        
        // Actualizar la exclusión de insumos inmediatamente
        updateAvailableInsumos();
    });

    // Eliminar ítem
    itemsContainer.addEventListener('click', function(e) {
        if(e.target.classList.contains('removeItemBtn')) {
            e.target.closest('.item-row').remove();
            // Volver a calcular y actualizar las opciones disponibles
            calcularSubtotales();
        }
    });

    // Cálculo y exclusión inicial
    calcularSubtotales();
    updateAvailableInsumos();
});