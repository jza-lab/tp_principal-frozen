// NUEVA FUNCIÓN: Formatea el número al estándar argentino ($ 1.234,56)
function formatToARS(number) {
    if (typeof number === 'string') {
        // En caso de que recibas un string, intenta limpiarlo y convertirlo a flotante
        const cleaned = number.replace(/[$\s]/g, '').replace(/\./g, '').replace(',', '.');
        number = parseFloat(cleaned);
    }
    if (isNaN(number)) return '$ 0,00';

    // Usamos Intl.NumberFormat para formateo local
    const formatter = new Intl.NumberFormat('es-AR', {
        style: 'currency',
        currency: 'ARS',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });

    return formatter.format(number);
}

// NUEVO OBJETO: Para almacenar las unidades de medida
window.PRODUCT_UNITS = {}; 

window.PRODUCT_PRICES = {};
const IVA_RATE = 0.21; // Mantenemos esta constante global

document.querySelectorAll('.producto-selector option[data-precio]').forEach(option => {
    const productId = option.value;
    const price = parseFloat(option.getAttribute('data-precio')) || 0;
    const unit = option.getAttribute('data-unidad') || '--'; // Leer la unidad
    if (productId) {
        window.PRODUCT_PRICES[productId] = price;
        window.PRODUCT_UNITS[productId] = unit; // Almacenar la unidad
    }
});

// Función Global de Cálculo (MODIFICADA)
window.calculateOrderTotals = function () {
    const itemsContainer = document.getElementById('items-container');
    const noItemsMsg = document.getElementById('no-items-msg');
    const totalFinalInput = document.getElementById('total-final');

    const resumenSubtotalEl = document.getElementById('resumen-subtotal');
    const resumenIvaEl = document.getElementById('resumen-iva');
    const resumenTotalEl = document.getElementById('total-final');
    const tipoFacturaInput = document.getElementById('tipo_factura')

    let subtotalNeto = 0;

    if (!itemsContainer) return;

    document.querySelectorAll('#items-container .item-row').forEach(row => {
        const productSelect = row.querySelector('.producto-selector');
        const quantityInput = row.querySelector('.item-quantity');
        const subtotalItemInput = row.querySelector('.subtotal-item');
        const priceDisplay = row.querySelector('.price-display');
        const unitDisplay = row.querySelector('.unidad-display');
        const priceUnitValueInput = row.querySelector('.item-price-unit-value');

        if (productSelect && quantityInput) {
            const productId = productSelect.value;
            const quantity = parseFloat(quantityInput.value) || 0;
            
            const selectedOption = productSelect.options[productSelect.selectedIndex];
            let price = 0;
            let unit = '--';

            if (priceDisplay && priceDisplay.value) {
                const cleanedPrice = priceDisplay.value.replace(/[$\s.]/g, '').replace(',', '.');
                price = parseFloat(cleanedPrice) || 0;
            } else if (selectedOption && selectedOption.value) {
                price = parseFloat(selectedOption.getAttribute('data-precio')) || window.PRODUCT_PRICES[productId] || 0;
            }

            if (selectedOption && selectedOption.value) {
                unit = selectedOption.getAttribute('data-unidad') || window.PRODUCT_UNITS[productId] || '--';
            }
            const itemSubtotal = price * quantity;
            if (unitDisplay) {
                unitDisplay.textContent = unit;
            }
            if (priceUnitValueInput) {
                priceUnitValueInput.value = price;
            }
            if (priceDisplay) {
                priceDisplay.value = formatToARS(price);
            }
            
            if (subtotalItemInput) {
                subtotalItemInput.value = formatToARS(itemSubtotal);
            }

            subtotalNeto += itemSubtotal;
        }
    });

    let totalFinal = subtotalNeto;
    if (totalFinalInput) {
        totalFinalInput.value = formatToARS(subtotalNeto); // O el total con IVA si corresponde
    }
    
    const ivaRowEl = document.getElementById('iva-row');
    // Para el formulario de cliente (con resumen detallado)
    if (resumenSubtotalEl && resumenIvaEl && resumenTotalEl) {
        let costoFlete = 0; // Por ahora, flete es 0. Se puede extender en el futuro.
        let montoIva = 0;

        const tipoFactura = document.getElementById('tipo_factura');
        const tipoFacturaValue = tipoFactura ? tipoFactura.value : 'B';

        if (tipoFactura === 'A') {
            montoIva = subtotalNeto * 0.21;
            ivaRowEl.style.display = 'block';
        }
        else{
            montoIva = 0;
            ivaRowEl.style.display = 'none';
        }
        
        const totalFinalConIvaYFlete = subtotalNeto + costoFlete;
        
        resumenSubtotalEl.textContent = formatToARS(subtotalNeto);
        resumenIvaEl.textContent = formatToARS(montoIva);
        resumenTotalEl.textContent = formatToARS(totalFinalConIvaYFlete);
    }

    const visibleRows = itemsContainer.querySelectorAll('.item-row').length;
    if (noItemsMsg) noItemsMsg.style.display = visibleRows === 0 ? 'block' : 'none';
};

// Función Global para adjuntar listeners (MODIFICADA PARA FORZAR EL CÁLCULO EN 'CHANGE')
window.attachItemListeners = function (row) {
    const productSelect = row.querySelector('.producto-selector');
    const quantityInput = row.querySelector('.item-quantity');
    const removeBtn = row.querySelector('.remove-item-btn');

    // Los listeners llaman directamente a la función de cálculo
    if (productSelect && !productSelect.disabled) {
        // Al cambiar el producto, disparamos el cálculo
        productSelect.addEventListener('change', window.calculateOrderTotals); 
    }
    if (quantityInput && !quantityInput.disabled) {
        quantityInput.addEventListener('input', window.calculateOrderTotals);
    }
};


// 3. Inicialización de precios, IVA y listeners al cargar el DOM
document.addEventListener('DOMContentLoaded', function () {

    // Cargar precios y unidades en los objetos globales
    document.querySelectorAll('.producto-selector option[data-precio]').forEach(option => {
        const productId = option.value;
        const price = parseFloat(option.getAttribute('data-precio')) || 0;
        const unit = option.getAttribute('data-unidad') || '--'; // Leer y almacenar unidad
        if (productId) {
            window.PRODUCT_PRICES[productId] = price;
            window.PRODUCT_UNITS[productId] = unit;
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