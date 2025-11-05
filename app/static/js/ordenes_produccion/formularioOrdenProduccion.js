document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('insumo-search');
    const insumoSelect = document.getElementById('insumo-select');
    const options = Array.from(insumoSelect.options);
    const addItemBtn = document.getElementById('addItemBtn');
    const itemsContainer = document.getElementById('itemsContainer');
    const subtotalInput = document.getElementById('subtotal');
    const ivaCheckbox = document.getElementById('iva');
    const totalInput = document.getElementById('total');

    // --- 1. Filtrado del select de insumos ---
    searchInput.addEventListener('input', function () {
        const query = searchInput.value.toLowerCase();
        options.forEach(option => {
            const shouldShow = option.textContent.toLowerCase().includes(query);
            option.style.display = shouldShow ? '' : 'none';
        });
    });

    // --- 2. Añadir ítem seleccionado ---
    addItemBtn.addEventListener('click', function() {
        const selectedOption = insumoSelect.options[insumoSelect.selectedIndex];
        if (!selectedOption || selectedOption.value === "") {
            // Opcional: mostrar una alerta si no hay nada seleccionado
            alert("Por favor, seleccione un insumo de la lista.");
            return;
        }

        const insumoId = selectedOption.value;
        const insumoNombre = selectedOption.getAttribute('data-nombre');
        const insumoPrecio = selectedOption.getAttribute('data-precio');

        // Evitar añadir duplicados
        if (document.querySelector(`.item-row input[name="insumo_id[]"][value="${insumoId}"]`)) {
            alert("Este insumo ya ha sido añadido.");
            return;
        }

        const newRow = document.createElement('div');
        newRow.className = 'row g-3 align-items-center item-row mb-3 p-2 border rounded';
        newRow.innerHTML = `
            <input type="hidden" name="insumo_id[]" value="${insumoId}">
            <input type="hidden" class="precio_unitario" name="precio_unitario[]" value="${insumoPrecio}">
            
            <div class="col-md-6">
                <label class="form-label small">Insumo</label>
                <input type="text" class="form-control form-control-sm" value="${insumoNombre}" readonly>
            </div>
            <div class="col-md-4">
                <label class="form-label small">Cantidad</label>
                <input type="number" step="0.1" min="1" max="5000" class="form-control form-control-sm cantidad" name="cantidad_solicitada[]" value="1">
            </div>
            <div class="col-md-2 d-flex align-items-end">
                <button type="button" class="btn btn-sm btn-outline-danger removeItemBtn w-100">X</button>
            </div>
        `;
        itemsContainer.appendChild(newRow);
        calcularSubtotales();
    });

    // --- 3. Eliminar ítem ---
    itemsContainer.addEventListener('click', function(e) {
        if (e.target.classList.contains('removeItemBtn')) {
            e.target.closest('.item-row').remove();
            calcularSubtotales();
        }
    });

    // --- 4. Recalcular totales al cambiar cantidad o IVA ---
    itemsContainer.addEventListener('input', function(e) {
        if (e.target.classList.contains('cantidad')) {
            calcularSubtotales();
        }
    });
    ivaCheckbox.addEventListener('change', calcularSubtotales);

    // --- 5. Función de cálculo ---
    function calcularSubtotales() {
        let subtotalTotal = 0;
        document.querySelectorAll('.item-row').forEach(row => {
            const cantidad = parseFloat(row.querySelector('.cantidad').value) || 0;
            const precio = parseFloat(row.querySelector('.precio_unitario').value) || 0;
            subtotalTotal += cantidad * precio;
        });

        subtotalInput.value = subtotalTotal.toFixed(2);
        
        let total = subtotalTotal;
        if (ivaCheckbox.checked) {
            total += subtotalTotal * 0.21;
        }
        totalInput.value = total.toFixed(2);
    }
    
    // Cálculo inicial por si hay ítems precargados
    calcularSubtotales();
});
