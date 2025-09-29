document.addEventListener('DOMContentLoaded', function () {
    const itemsContainer = document.getElementById('itemsContainer');
    const subtotalInput = document.getElementById('subtotal');
    const ivaInput = document.getElementById('iva');
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
        const iva = parseFloat(ivaInput.value) || 0;
        totalInput.value = (subtotalTotal + iva).toFixed(2);
    }

    // Eventos para inputs existentes
    itemsContainer.addEventListener('input', calcularSubtotales);
    ivaInput.addEventListener('input', calcularSubtotales);

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
                <input type="number" step="0.01" class="form-control cantidad" name="cantidad_solicitada[]" value="0">
            </div>
            <div class="col-md-2">
                <label class="form-label">Precio Unitario</label>
                <input type="number" step="0.01" class="form-control precio_unitario" name="precio_unitario[]" value="0">
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