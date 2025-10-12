
window.PRODUCT_PRICES = {};
const IVA_RATE = 0.21; // Mantenemos esta constante global

document.querySelectorAll('.product-selector option[data-precio]').forEach(option => {
    const productId = option.value;
    const price = parseFloat(option.getAttribute('data-precio')) || 0;
    if (productId) {
        window.PRODUCT_PRICES[productId] = price;
    }
});

// Función Global de Cálculo
window.calculateOrderTotals = function () {
    const itemsContainer = document.getElementById('items-container');
    const noItemsMsg = document.getElementById('no-items-msg');
    const totalFinalInput = document.getElementById('total-final');

    let subtotalNeto = 0;

    if (!itemsContainer || !totalFinalInput) return;

    document.querySelectorAll('#items-container .item-row').forEach(row => {
        const productSelect = row.querySelector('.product-selector');
        const quantityInput = row.querySelector('.item-quantity');
        const subtotalItemInput = row.querySelector('.subtotal-item');

        if (productSelect && quantityInput) {
            const productId = productSelect.value;
            const quantity = parseFloat(quantityInput.value) || 0;

            let price = window.PRODUCT_PRICES[productId];

            if (price === undefined) {
                const selectedOption = productSelect.options[productSelect.selectedIndex];
                price = parseFloat(selectedOption?.getAttribute('data-precio')) || 0;
            }

            const itemSubtotal = price * quantity;

            if (subtotalItemInput) {
                subtotalItemInput.value = itemSubtotal.toFixed(2);
            }

            const priceDisplay = row.querySelector('.price-display');

            if (priceDisplay) {
                // Actualizar el valor del precio unitario mostrado
                priceDisplay.value = price.toFixed(2);

            }
            subtotalNeto += itemSubtotal;
        }
    });

    let totalFinal = subtotalNeto;
    if (totalFinalInput) totalFinalInput.value = totalFinal.toFixed(2);

    const visibleRows = itemsContainer.querySelectorAll('.item-row').length;
    if (noItemsMsg) noItemsMsg.style.display = visibleRows === 0 ? 'block' : 'none';
};

// Función Global para adjuntar listeners (llamada por el script del FormSet)
window.attachItemListeners = function (row) {
    const productSelect = row.querySelector('.product-selector');
    const quantityInput = row.querySelector('.item-quantity');
    const removeBtn = row.querySelector('.remove-item-btn');

    // Los listeners llaman directamente a la función de cálculo
    if (productSelect && !productSelect.disabled) {
        productSelect.addEventListener('change', window.calculateOrderTotals);
    }
    if (quantityInput && !quantityInput.disabled) {
        quantityInput.addEventListener('input', window.calculateOrderTotals);
    }

    // El listener de eliminación solo llama a la función removeItem del script del FormSet
    // El script del FormSet llamará a calculateOrderTotals después de eliminar y re-indexar.
};


// 3. Inicialización de precios, IVA y listeners al cargar el DOM
document.addEventListener('DOMContentLoaded', function () {

    // Cargar precios en el objeto global
    document.querySelectorAll('.product-selector option[data-precio]').forEach(option => {
        const productId = option.value;
        const price = parseFloat(option.getAttribute('data-precio')) || 0;
        if (productId) {
            window.PRODUCT_PRICES[productId] = price;
        }
    });

    const ivaCheckbox = document.getElementById('iva-checkbox');
    if (ivaCheckbox) {
        ivaCheckbox.addEventListener('change', window.calculateOrderTotals);
    }

    // Adjuntar listeners a todos los ítems existentes (precargados)
    document.querySelectorAll('#items-container .item-row').forEach(window.attachItemListeners);

    // Ejecutar cálculo inicial
    window.calculateOrderTotals();
});