// app/static/js/orden_venta/addItem.js

/**
 * Añade una nueva fila de producto al formulario de pedido.
 * Si se proporciona un producto, rellena la fila con sus datos.
 */
function addItemRow(product = null) {
    const itemsContainer = document.getElementById('items-container');
    const template = document.getElementById('item-template');

    if (!itemsContainer || !template) {
        console.error('No se encontró el contenedor de ítems o la plantilla.');
        showNotificationModal('Error', 'No se pueden añadir productos. Faltan elementos clave en la página.', 'error');
        return;
    }

    const newFragment = template.content.cloneNode(true);
    const newRow = newFragment.querySelector('.item-row');
    
    if (product) {
        // Rellenar los datos del producto en la nueva fila
        const searchInput = newRow.querySelector('.producto-search');
        const productSelect = newRow.querySelector('.producto-selector');
        const quantityInput = newRow.querySelector('.item-quantity');

        if (searchInput) searchInput.value = product.nombre;
        if (productSelect) productSelect.value = product.id;
        if (quantityInput) quantityInput.value = 1; // Cantidad por defecto
    }

    itemsContainer.appendChild(newFragment);
    reindexarFilas();
    
    // Enfocar en la cantidad de la nueva fila si se añadió un producto
    if (product) {
        const newQuantityInput = itemsContainer.lastElementChild.querySelector('.item-quantity');
        if (newQuantityInput) {
            newQuantityInput.focus();
            newQuantityInput.select();
        }
    }
    
    // Disparar el cálculo de totales y la actualización del estado del botón
    if (window.calculateOrderTotals) {
        window.calculateOrderTotals();
    }
    if (window.updateProformaButtonState) {
        window.updateProformaButtonState();
    }
}

/**
 * Reindexa los nombres de los campos de todas las filas de productos.
 * Es crucial para que el backend (formsets) procese correctamente los datos.
 */
function reindexarFilas() {
    const itemsContainer = document.getElementById('items-container');
    const rows = itemsContainer.querySelectorAll('.item-row');
    const totalFormsInput = document.getElementById('id_items-TOTAL_FORMS');
    const noItemsMsg = document.getElementById('no-items-msg');

    rows.forEach((row, index) => {
        // Actualizar los atributos 'name' de todos los inputs, selects, etc.
        row.querySelectorAll('[name*="__prefix__"]').forEach(input => {
            const name = input.getAttribute('name');
            if (name) {
                input.setAttribute('name', name.replace('__prefix__', index));
            }
        });
    });

    // Actualizar el contador total de formularios
    if (totalFormsInput) {
        totalFormsInput.value = rows.length;
    }

    // Mostrar u ocultar el mensaje de "no hay productos"
    if (noItemsMsg) {
        noItemsMsg.style.display = rows.length === 0 ? 'block' : 'none';
    }
}
