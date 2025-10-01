document.addEventListener('DOMContentLoaded', function() {
    try {
        const container = document.getElementById('items-container');
        const addItemBtn = document.getElementById('add-item-btn');
        const itemTemplate = document.getElementById('item-template');
        const totalFormsInput = document.querySelector('input[name="items-TOTAL_FORMS"]');
        const noItemsMsg = document.getElementById('no-items-msg');
        
        // Si faltan elementos esenciales, salimos para evitar errores de null
        if (!container || !totalFormsInput) {
            console.error("Faltan elementos esenciales (container o TOTAL_FORMS) para inicializar el formset de ítems.");
            return;
        }

        // Prefijo utilizado por el formset framework (e.g., 'items')
        const prefix = 'items';

        /**
         * Gestiona la exclusión de productos ya seleccionados en otros selectores.
         * Deshabilita las opciones para evitar duplicados.
         */
        function updateAvailableProducts() {
            // 1. Recopilar todos los IDs de producto seleccionados en CUALQUIER fila.
            const selectedProductIds = new Set();
            document.querySelectorAll('.producto-selector').forEach(select => {
                if (select.value) {
                    selectedProductIds.add(select.value);
                }
            });

            // 2. Iterar sobre todos los selectores para aplicar la exclusión.
            document.querySelectorAll('.producto-selector').forEach(currentSelect => {
                const currentValue = currentSelect.value;
                
                // Iterar sobre todas las opciones con data-id
                currentSelect.querySelectorAll('option[data-id]').forEach(option => {
                    const optionId = option.getAttribute('data-id');

                    // Habilitar la opción por defecto (limpiar el estado anterior)
                    option.disabled = false;

                    // 3. Lógica de Inhabilitación:
                    // Deshabilita la opción si ha sido seleccionada, Y NO es la opción actual de ESTA fila.
                    if (selectedProductIds.has(optionId) && optionId !== currentValue) {
                        option.disabled = true;
                    }
                });
            });
        }

        /**
          * Helper para actualizar el índice de los campos en una fila.
          * @param {HTMLElement} el Elemento a actualizar.
          * @param {string} prefix Prefijo del formset (e.g., 'items').
          * @param {number} index Nuevo índice.
          */
        function updateElementIndex(el, prefix, index) {
            // Expresión regular para encontrar el índice anterior (e.g., -0-, -1-, etc.)
            const idRegex = new RegExp('(' + prefix + '-\\d+-)(.*)');
            // El reemplazo se hará con el nuevo índice
            const replacement = prefix + '-' + index + '-$2';

            if (el.id) {
                el.id = el.id.replace(idRegex, replacement);
            }
            if (el.name) {
                el.name = el.name.replace(idRegex, replacement);
            }
        }

        /**
          * Gestiona la visibilidad del mensaje "Añada productos".
          */
        function toggleNoItemsMessage() {
            if (noItemsMsg) {
                const rowCount = container.querySelectorAll('.item-row').length;
                noItemsMsg.style.display = rowCount === 0 ? 'block' : 'none';
            }
        }

        /**
          * Actualiza el stock visible cuando se selecciona un producto.
          * También se usa para cargar el stock inicial de filas existentes.
          * @param {Event|object} event - El objeto Event o un objeto simulado con el target.
          */
        function handleProductChange(event) {
            const select = event.target;
            const row = select.closest('.item-row');
            
            // Verificación defensiva
            if (!row) return; 

            const stockDisplay = row.querySelector('.stock-display');
            
            // Buscamos la opción seleccionada
            const selectedOption = select.options[select.selectedIndex];
            
            // Obtiene el stock del atributo data-stock de la opción seleccionada
            const stock = selectedOption ? (selectedOption.dataset.stock || 0) : 0;
            
            if (stockDisplay) {
                // Muestra stock con un decimal
                stockDisplay.textContent = parseFloat(stock).toFixed(1); 
            }
        }

        /**
          * Re-indexa todas las filas después de una adición o eliminación.
          */
        function reindexRows() {
            const rows = container.querySelectorAll('.item-row');
            let newIndex = 0;

            rows.forEach(row => {
                // Re-indexar todos los elementos con atributos 'name' o 'id' que empiecen con el prefijo
                row.querySelectorAll('[name^="' + prefix + '-"], [id^="' + prefix + '-"]').forEach(el => {
                    updateElementIndex(el, prefix, newIndex);
                });
                
                // Re-adjuntar listeners y actualizar stock para la fila re-indexada
                const productSelect = row.querySelector('select[name$="-producto_id"]');
                const removeButton = row.querySelector('.remove-item-btn');
                
                if (productSelect) {
                    // Limpiar y adjuntar listener de cambio de producto/stock
                    productSelect.removeEventListener('change', handleProductChange);
                    productSelect.addEventListener('change', handleProductChange);

                    // Limpiar y adjuntar listener para la EXCLUSIÓN DE PRODUCTOS
                    productSelect.removeEventListener('change', updateAvailableProducts);
                    productSelect.addEventListener('change', updateAvailableProducts);

                    // Llamar a handleProductChange para actualizar el stock visible
                    handleProductChange({ target: productSelect });
                }

                if (removeButton) {
                    // Limpiar y adjuntar listener de eliminación
                    removeButton.removeEventListener('click', removeItem);
                    removeButton.addEventListener('click', removeItem);
                }

                newIndex++;
            });

            // Actualizar TOTAL_FORMS
            if (totalFormsInput) {
                totalFormsInput.value = newIndex;
            }

            toggleNoItemsMessage();
        }

        /**
          * Añade una nueva fila de ítem.
          */
        function addItem() {
            if (!itemTemplate || !totalFormsInput) return;

            // Clonar la plantilla y reemplazar el prefijo con el índice actual
            const newIndex = parseInt(totalFormsInput.value, 10);
            const newRowContent = itemTemplate.content.cloneNode(true);
            const newRow = newRowContent.querySelector('.item-row');
            
            newRow.innerHTML = newRow.innerHTML.replace(/__prefix__/g, newIndex);
            
            container.appendChild(newRow);
            
            // La reindexación se encarga de adjuntar los listeners
            reindexRows(); 
            
            // Aplicar la lógica de exclusión después de añadir una fila
            updateAvailableProducts(); 
        }

        /**
          * Elimina una fila de ítem.
          * @param {Event} event 
          */
        function removeItem(event) {
            const row = event.target.closest('.item-row');
            if (row) {
                row.remove();
                reindexRows(); // Reindexar después de eliminar
                
                // Re-habilitar los productos después de eliminar una fila
                updateAvailableProducts();
            }
        }

        // --- Inicialización y Event Listeners ---
        
        // 1. Botón de añadir ítem
        if (addItemBtn) {
            addItemBtn.addEventListener('click', addItem);
        }
        
        // 2. Inicializar listeners para filas existentes (al cargar la página)
        reindexRows(); 
        
        // 3. Aplicar la lógica de exclusión inicial para cualquier producto precargado
        updateAvailableProducts();

    } catch (e) {
        console.error("Error crítico en la inicialización del formset de pedidos:", e);
    }
});