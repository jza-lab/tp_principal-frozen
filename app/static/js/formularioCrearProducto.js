    document.addEventListener('DOMContentLoaded', function () {
        const itemsContainer = document.getElementById('itemsContainer');
        const subtotalInput = document.getElementById('subtotal');
        const ivaCheckbox = document.getElementById('iva');
        const totalInput = document.getElementById('total');
        const addItemBtn = document.getElementById('addItemBtn');
        const porcentajeExtraInput = document.getElementById('porcentaje_extra');

        // Mapeo de insumos para facilitar la construcción de opciones
        const insumosData = typeof INSUMOS_DATA !== 'undefined' && Array.isArray(INSUMOS_DATA) ? INSUMOS_DATA : [];

        function calcularTotales() {
            let subtotalTotal = 0;
            itemsContainer.querySelectorAll('.item-row').forEach(row => {
                const cantidad = parseFloat(row.querySelector('.cantidad').value) || 0;
                const precio = parseFloat(row.querySelector('.precio_unitario').value) || 0;
                const subtotal = cantidad * precio;
                row.querySelector('.subtotal-item').value = subtotal.toFixed(2);
                subtotalTotal += subtotal;
            });

            subtotalInput.value = subtotalTotal.toFixed(2);

            // Aplica porcentaje extra (mano de obra/ganancia)
            const porcentaje = parseFloat(porcentajeExtraInput.value) || 0;
            let total = subtotalTotal + (subtotalTotal * porcentaje / 100);

            // Aplica IVA si corresponde
            if (ivaCheckbox.checked) {
                total += subtotalTotal * 0.21;
            }
            totalInput.value = total.toFixed(2);

            updateAvailableInsumos();
        }

        function updateAvailableInsumos() {
            // Recopilar todos los IDs de insumos seleccionados.
            const selectedInsumoIds = new Set();
            itemsContainer.querySelectorAll('.insumo-selector').forEach(select => {
                if (select.value) {
                    selectedInsumoIds.add(select.value);
                }
            });

            // Iterar sobre todos los selectores para aplicar la exclusión.
            itemsContainer.querySelectorAll('.insumo-selector').forEach(currentSelect => {
                const currentValue = currentSelect.value;
                currentSelect.querySelectorAll('option[data-id]').forEach(option => {
                    const optionId = option.getAttribute('data-id');
                    option.disabled = false;
                    option.hidden = false;
                    if (selectedInsumoIds.has(optionId) && optionId !== currentValue) {
                        option.disabled = true;
                    }
                });
            });
        }

        // Evento para inputs de cantidad y precio
        itemsContainer.addEventListener('input', function (e) {
            if (e.target.classList.contains('cantidad')) {
                const row = e.target.closest('.item-row');
                const precio = parseFloat(row.querySelector('.precio_unitario').value) || 0;
                const cantidad = parseFloat(e.target.value) || 0;
                row.querySelector('.subtotal-item').value = (cantidad * precio).toFixed(2);
                calcularTotales();
            }
        });

        // Evento de cambio para los selectores de insumos
        itemsContainer.addEventListener('change', function (e) {
            if (e.target.classList.contains('insumo-selector')) {
                const option = e.target.selectedOptions[0];
                const row = e.target.closest('.item-row');
                const unidadLabel = row.querySelector('.unidad-label');
                const precioInput = row.querySelector('.precio_unitario');
                if (unidadLabel) unidadLabel.textContent = `(${option.dataset.unidad || ''})`;
                if (precioInput) precioInput.value = option.dataset.precio || '';
                // recalcula subtotal si hay cantidad
                const cantidadInput = row.querySelector('.cantidad');
                if (cantidadInput) {
                    const cantidad = parseFloat(cantidadInput.value) || 0;
                    const precio = parseFloat(precioInput.value) || 0;
                    row.querySelector('.subtotal-item').value = (cantidad * precio).toFixed(2);
                }
                calcularTotales();
            }
        });

        // Evento para porcentaje extra
        porcentajeExtraInput.addEventListener('input', calcularTotales);

        // Evento para IVA
        ivaCheckbox.addEventListener('change', calcularTotales);

        // Añadir ítem
        addItemBtn.addEventListener('click', function () {
            const row = document.createElement('div');
            row.className = 'row g-3 align-items-end item-row mb-2';

            let optionsHtml = '<option value="" data-id="">Seleccione un insumo...</option>';
            insumosData.forEach(insumo => {
                optionsHtml += `<option value="${insumo.id}" data-id="${insumo.id}" data-unidad="${insumo.unidad_medida}" data-precio="${insumo.precio_unitario}">${insumo.nombre}</option>`;
            });

            row.innerHTML = `
            <div class="col-md-4">
                <label class="form-label">Insumo</label>
                <select class="form-select insumo-selector" name="insumo_id[]" required>
                    ${optionsHtml}
                </select>
            </div>
            <div class="col-md-2">
                <label class="form-label">Cantidad <span class="unidad-label"></span></label>
                <input type="number" min="0.01" step="0.01" class="form-control cantidad" name="cantidad[]" value="1" required>
            </div>
            <div class="col-md-2">
                <label class="form-label">Precio Unitario</label>
                <input type="number" class="form-control precio_unitario" name="precio_unitario[]" readonly>
            </div>
            <div class="col-md-2">
                <label class="form-label">Subtotal</label>
                <input type="number" step="0.01" class="form-control subtotal-item" value="0.00" readonly>
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-outline-danger removeItemBtn">Eliminar</button>
            </div>
        `;
            itemsContainer.appendChild(row);
            calcularTotales();
        });

        // Eliminar ítem
        itemsContainer.addEventListener('click', function (e) {
            if (e.target.classList.contains('removeItemBtn')) {
                e.target.closest('.item-row').remove();
                calcularTotales();
            }
        });

        // Cálculo y exclusión inicial
        calcularTotales();
        updateAvailableInsumos();
    });

    // Validación al enviar el formulario
    const form = document.getElementById('formulario-producto');
    const itemsContainer = document.getElementById('itemsContainer');

    form.addEventListener('submit', function (event) {
        if (!form.checkValidity()) {
            event.preventDefault();
            form.classList.add('was-validated');
            return;
        }
        const itemRows = itemsContainer.querySelectorAll('.item-row');
        if (itemRows.length === 0) {
            event.preventDefault();
            alert('Debe añadir al menos un insumo a la receta del producto.');
            itemsContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }
        form.classList.remove('was-validated');
    });