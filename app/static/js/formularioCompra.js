document.addEventListener('DOMContentLoaded', function () {
    const itemsContainer = document.getElementById('itemsContainer');
    const subtotalInput = document.getElementById('subtotal');
    const ivaCheckbox = document.getElementById('iva'); // ahora es checkbox
    const totalInput = document.getElementById('total');

    function calcularSubtotales() {
        let subtotalTotal = 0;
        document.querySelectorAll('.item-row').forEach(row => {
            const cantidad = parseFloat(row.querySelector('.cantidad').value) || 0;
            const precio = parseFloat(row.querySelector('.precio_unitario').value) || 0;
            const subtotal = cantidad * precio;
            row.querySelector('.subtotal-item').value = subtotal.toFixed(2);
            subtotalTotal += subtotal;
        });
        subtotalInput.value = subtotalTotal.toFixed(2);

        // IVA al 21% si está tildado
        let total = subtotalTotal;
        if (ivaCheckbox.checked) {
            total += subtotalTotal * 0.21;
        }
        totalInput.value = total.toFixed(2);
    }

    // Eventos para inputs existentes
    itemsContainer.addEventListener('input', calcularSubtotales);
    ivaCheckbox.addEventListener('change', calcularSubtotales); // cambio de input a checkbox

    // Añadir ítem
    document.getElementById('addItemBtn').addEventListener('click', function () {
        const row = document.createElement('div');
        row.className = 'row g-3 align-items-end item-row mb-2';

        let optionsHtml = '<option value="">Seleccione un insumo...</option>';
        if (typeof INSUMOS_DATA !== 'undefined' && Array.isArray(INSUMOS_DATA)) {
            INSUMOS_DATA.forEach(insumo => {
                optionsHtml += `<option value="${insumo.id}">${insumo.nombre}</option>`;
            });
        }

        row.innerHTML = `
            <div class="col-md-4">
                <label class="form-label">Insumo</label>
                <select class="form-select" name="insumo_id[]">
                    ${optionsHtml}
                </select>
            </div>
            <div class="col-md-2">
                <label class="form-label">Cantidad</label>
                <input type="number" min="1" max="5000" step="0.1" class="form-control cantidad" name="cantidad_solicitada[]" value="0">
            </div>
            <div class="col-md-2">
                <label class="form-label">Precio Unitario</label>
                <input type="number" step="0.01" min="1" class="form-control precio_unitario" name="precio_unitario[]" value="0">
            </div>
            <div class="col-md-2">
                <label class="form-label">Subtotal</label>
                <input type="number" step="0.01" min="1" class="form-control subtotal-item" value="0.00" readonly>
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-outline-danger removeItemBtn">Eliminar</button>
            </div>
        `;
        itemsContainer.appendChild(row);
    });

    // Eliminar ítem
    itemsContainer.addEventListener('click', function(e) {
        if(e.target.classList.contains('removeItemBtn')) {
            e.target.closest('.item-row').remove();
            calcularSubtotales();
        }
    });

    // Cálculo inicial
    calcularSubtotales();
});
