document.addEventListener('DOMContentLoaded', function () {
    // --- LÓGICA DEL MODAL DE BÚSQUEDA ---
    const productSearchModal = new bootstrap.Modal(document.getElementById('productSearchModal'));
    const searchFilterInput = document.getElementById('product-search-filter');
    const productSelect = document.getElementById('product-select');
    // Asumimos que los datos de productos están disponibles globalmente en una variable `productos`
    const productosData = typeof productos !== 'undefined' ? productos : [];

    function poblarProductosEnModal() {
        productSelect.innerHTML = ''; // Limpiar opciones existentes
        productosData.forEach(producto => {
            const option = document.createElement('option');
            option.value = producto.id;
            option.textContent = `${producto.nombre} (${format_product_units(producto)})`;
            option.dataset.id = producto.id;
            option.dataset.nombre = producto.nombre;
            option.dataset.precio = producto.precio_unitario;
            option.dataset.unidad = producto.unidad_medida;
            option.dataset.stock = producto.stock_disponible || 0;
            // --- NUEVOS DATASETS PARA FORMAT_PRODUCT_UNITS ---
            option.dataset.unidades_por_paquete = producto.unidades_por_paquete || 1;
            option.dataset.peso_por_paquete_valor = producto.peso_por_paquete_valor || 0;
            option.dataset.peso_por_paquete_unidad = producto.peso_por_paquete_unidad || '';
            productSelect.appendChild(option);
        });
    }

    searchFilterInput.addEventListener('input', function () {
        const searchTerm = this.value.toLowerCase();
        Array.from(productSelect.options).forEach(option => {
            const text = option.textContent.toLowerCase();
            option.style.display = text.includes(searchTerm) ? '' : 'none';
        });
    });

    productSelect.addEventListener('dblclick', function () {
        const selectedOption = this.options[this.selectedIndex];
        if (!selectedOption || !selectedOption.value) return;

        const productoId = selectedOption.dataset.id;

        // Verificar si el producto ya está en la lista
        const yaExiste = document.querySelector(`.producto-selector[value="${productoId}"]`);
        if (yaExiste) {
            // Opcional: podrías mostrar una alerta o simplemente no hacer nada.
            // Por ejemplo, hacer que la fila existente parpadee.
            const filaExistente = yaExiste.closest('tr');
            filaExistente.classList.add('table-warning');
            setTimeout(() => {
                filaExistente.classList.remove('table-warning');
            }, 1000);
            productSearchModal.hide();
            return; // Detener la ejecución
        }

        const itemsContainer = document.getElementById('items-container');
        const itemTemplate = document.getElementById('item-template');
        const totalForms = document.getElementById('id_items-TOTAL_FORMS');
        const formCount = parseInt(totalForms.value);

        const template = itemTemplate.innerHTML.replace(/__prefix__/g, formCount);
        const newRow = document.createElement('tr');
        newRow.innerHTML = template;
        newRow.classList.add('item-row');

        // Poblar los campos directamente con los datos del dataset
        const productoSelector = newRow.querySelector('.producto-selector');
        productoSelector.value = selectedOption.dataset.id;

        const unidadDisplay = newRow.querySelector('.unidad-display');
        unidadDisplay.textContent = format_product_units({
            unidad_medida: selectedOption.dataset.unidad,
            unidades_por_paquete: selectedOption.dataset.unidades_por_paquete,
            peso_por_paquete_valor: selectedOption.dataset.peso_por_paquete_valor,
            peso_por_paquete_unidad: selectedOption.dataset.peso_por_paquete_unidad
        });

        const priceDisplay = newRow.querySelector('.price-display');
        const precio = parseFloat(selectedOption.dataset.precio || 0);
        priceDisplay.value = `$ ${precio.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

        // Configurar el input de cantidad (min, step)
        const cantidadInput = newRow.querySelector('.item-quantity');
        cantidadInput.step = '1';
        cantidadInput.min = '0';
        cantidadInput.value = '0'; // Valor inicial

        // Calcular el subtotal inicial
        const subtotalDisplay = newRow.querySelector('.subtotal-item');
        subtotalDisplay.value = `$ ${precio.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

        itemsContainer.appendChild(newRow);
        totalForms.value = formCount + 1;

        // Ocultar mensaje de "no hay items"
        document.getElementById('no-items-msg').style.display = 'none';

        // Recalcular el total general (la función debe estar disponible globalmente)
        if (typeof actualizarTotalPedido === 'function') {
            actualizarTotalPedido();
        }

        productSearchModal.hide();
    });

    document.getElementById('productSearchModal').addEventListener('shown.bs.modal', function () {
        poblarProductosEnModal();
        searchFilterInput.focus();
    });

    function format_product_units(producto) {
        if (producto.unidad_medida && producto.unidad_medida.startsWith('paquete')) {
            if (producto.unidades_por_paquete > 1) {
                return `paquete(x${producto.unidades_por_paquete}u)`;
            } else if (producto.peso_por_paquete_valor > 0) {
                return `paquete(x${producto.peso_por_paquete_valor}${producto.peso_por_paquete_unidad})`;
            }
        }
        return producto.unidad_medida;
    }
});
