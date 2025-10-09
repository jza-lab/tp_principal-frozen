document.addEventListener('DOMContentLoaded', function () {
    const itemsContainer = document.getElementById('itemsContainer');
    const subtotalInput = document.getElementById('subtotal');
    const ivaCheckbox = document.getElementById('iva');
    const totalInput = document.getElementById('total');
    const addItemBtn = document.getElementById('addItemBtn');
    const porcentajeExtraInput = document.getElementById('porcentaje_extra');

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

        const porcentaje = parseFloat(porcentajeExtraInput.value) || 0;
        let total = subtotalTotal * (1 + ( porcentaje / 100));

        if (ivaCheckbox.checked) {
            total *= 1.21;
        }
        totalInput.value = total.toFixed(2);
    }

    function updateAvailableInsumos() {
        const selectedInsumoIds = new Set();
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

    itemsContainer.addEventListener('input', function (e) {
        if (e.target.classList.contains('cantidad')) {
            const row = e.target.closest('.item-row');
            const precio = parseFloat(row.querySelector('.precio_unitario').value) || 0;
            const cantidad = parseFloat(e.target.value) || 0;
            row.querySelector('.subtotal-item').value = (cantidad * precio).toFixed(2);
            calcularTotales();
        }
    });

    itemsContainer.addEventListener('change', function (e) {
        if (e.target.classList.contains('insumo-selector')) {
            const option = e.target.selectedOptions[0];
            const row = e.target.closest('.item-row');
            row.querySelector('.precio_unitario').value = option.dataset.precio || '0';
            const cantidadInput = row.querySelector('.cantidad');
            const cantidad = parseFloat(cantidadInput.value) || 0;
            const precio = parseFloat(option.dataset.precio) || 0;
            row.querySelector('.subtotal-item').value = (cantidad * precio).toFixed(2);
            calcularTotales();
        }
    });

    porcentajeExtraInput.addEventListener('input', calcularTotales);
    ivaCheckbox.addEventListener('change', calcularTotales);

    addItemBtn.addEventListener('click', function () {
        const row = document.createElement('div');
        row.className = 'row g-3 align-items-end item-row mb-2';

        let optionsHtml = '<option value="">Seleccione un insumo...</option>';
        insumosData.forEach(insumo => {
            optionsHtml += `<option value="${insumo.id}" data-id="${insumo.id}" data-unidad="${insumo.unidad_medida}" data-precio="${insumo.precio_unitario}">${insumo.nombre}</option>`;
        });

        row.innerHTML = `
            <div class="col-md-4">
                <label class="form-label">Insumo</label>
                <select class="form-select insumo-selector" name="insumo_id[]" required>${optionsHtml}</select>
            </div>
            <div class="col-md-2">
                <label class="form-label">Cantidad</label>
                <input type="number" min="0.01" step="0.01" max="5000" class="form-control cantidad" name="cantidad[]" value="1" required>
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
        updateAvailableInsumos();
    });

    itemsContainer.addEventListener('click', function (e) {
        if (e.target.classList.contains('removeItemBtn')) {
            e.target.closest('.item-row').remove();
            calcularTotales();
            updateAvailableInsumos();
        }
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
        const productoData = {
            codigo: formData.get('codigo'),
            nombre: formData.get('nombre'),
            categoria: formData.get('categoria'),
            unidad_medida: formData.get('unidad_medida'),
            descripcion: formData.get('descripcion'),
            porcentaje_extra: formData.get('porcentaje_extra'),
            iva: formData.get('iva') === '1',
            precio_unitario: parseFloat(document.getElementById('total').value) || 0,
            receta_items: []
        };

        itemsContainer.querySelectorAll('.item-row').forEach(row => {
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

        const url = isEditBoolean ? `/api/productos/catalogo/actualizar/${ID_producto}` : '/api/productos/catalogo/nuevo';
        const method = isEditBoolean ? 'PUT' : 'POST';

        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(productoData)
            });

            const result = await response.json();

            if (response.ok && result.success) {
                showNotificationModal(result.message || 'Operación exitosa', 'success');
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
            showNotificationModal('No se pudo conectar con el servidor.', 'error');
        }
    });
});