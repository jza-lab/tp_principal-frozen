document.addEventListener('DOMContentLoaded', function () {
    // --- Lógica Común: Botón de Actualizar y Timestamp ---
    const updateButton = document.getElementById('actualizar-lotes');
    const lastUpdatedSpan = document.getElementById('last-updated');

    if (updateButton && lastUpdatedSpan) {
        const pageId = window.location.pathname; // Usar la ruta para una clave única
        const storageKey = `lastUpdatedTimestamp_${pageId}`;

        // Al cargar la página, mostrar el timestamp guardado o un texto por defecto
        const savedTimestamp = localStorage.getItem(storageKey);
        if (savedTimestamp) {
            lastUpdatedSpan.textContent = `Última actualización: ${savedTimestamp}`;
        } else {
            lastUpdatedSpan.textContent = 'Última actualización: Pendiente';
        }

        // Al hacer clic en el botón, guardar timestamp y recargar
        updateButton.addEventListener('click', function () {
            const now = new Date();
            const formattedTimestamp = now.toLocaleString('es-AR', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            localStorage.setItem(storageKey, formattedTimestamp);
            window.location.reload();
        });
    }

    // --- Lógica Desplegable Genérica ---
    function setupDropdown(inputId, listId, filterFunction) {
        const input = document.getElementById(inputId);
        const list = document.getElementById(listId);
        if (!input || !list) return;

        const items = list.querySelectorAll('.dropdown-item');

        input.addEventListener('focus', () => list.classList.add('show'));

        input.addEventListener('blur', () => {
            // Pequeño retraso para permitir el clic en un item
            setTimeout(() => list.classList.remove('show'), 200);
        });

        input.addEventListener('input', () => {
            const filter = input.value.toLowerCase();
            items.forEach(item => {
                const text = item.textContent.toLowerCase();
                item.style.display = text.includes(filter) ? '' : 'none';
            });
            filterFunction(); // Llama a la función de filtrado principal
        });

        items.forEach(item => {
            item.addEventListener('mousedown', (e) => {
                e.preventDefault();
                input.value = item.textContent;
                list.classList.remove('show');
                filterFunction(); // Llama a la función de filtrado principal
            });
        });
    }


    // --- Lógica de Filtrado: Inventario de Insumos ---
    const filtroInsumo = document.getElementById('filtro-insumo');
    const filtroLoteInsumo = document.getElementById('filtro-lote');
    const tablaInsumosBody = document.getElementById('tabla-insumos-body');

    if (filtroInsumo && tablaInsumosBody) {
        const rows = tablaInsumosBody.querySelectorAll('tr.table-group-header');
        const noResultsRow = tablaInsumosBody.querySelector('#no-results');

        function aplicarFiltrosInsumos() {
            const insumoQuery = filtroInsumo.value.toLowerCase().trim();
            const loteQuery = filtroLoteInsumo.value.toLowerCase().trim();
            let visibleRows = 0;

            rows.forEach(row => {
                const insumoNombre = row.dataset.insumoNombre.toLowerCase();
                const collapseTargetId = row.querySelector('.btn-expand').dataset.bsTarget;
                const collapseElement = document.querySelector(collapseTargetId);

                const matchInsumo = insumoNombre.includes(insumoQuery);

                let matchLote = false;
                if (loteQuery === '') {
                    matchLote = true;
                } else if (collapseElement) {
                    const lotesRows = collapseElement.querySelectorAll('tbody tr');
                    lotesRows.forEach(loteRow => {
                        const loteNumeroCell = loteRow.cells[1]; // El número de lote está en la segunda celda
                        if (loteNumeroCell) {
                           const loteNumero = loteNumeroCell.textContent.toLowerCase().trim();
                            if (loteNumero.includes(loteQuery)) {
                                matchLote = true;
                            }
                        }
                    });
                }

                if (matchInsumo && matchLote) {
                    row.style.display = '';
                    row.nextElementSibling.style.display = '';
                    visibleRows++;
                } else {
                    row.style.display = 'none';
                    row.nextElementSibling.style.display = 'none';
                }
            });

            if (noResultsRow) {
                noResultsRow.style.display = visibleRows === 0 ? '' : 'none';
            }
        }

        filtroLoteInsumo.addEventListener('input', aplicarFiltrosInsumos);
        setupDropdown('filtro-insumo', 'lista-insumos', aplicarFiltrosInsumos);
    }


    // --- Lógica de Filtrado: Inventario de Productos ---
    const filtroProducto = document.getElementById('filtro-producto');
    const filtroLoteProducto = document.getElementById('filtro-lote');
    const tablaLotesBody = document.getElementById('tablaLotesBody');

    if (filtroProducto && tablaLotesBody) {
        const rows = tablaLotesBody.querySelectorAll('.fila-lote');
        const noResultsRow = tablaLotesBody.querySelector('#fila-sin-resultados');

        function aplicarFiltrosProductos() {
            const productoQuery = filtroProducto.value.toLowerCase().trim();
            const loteQuery = filtroLoteProducto.value.toLowerCase().trim();
            let visibleRows = 0;

            rows.forEach(row => {
                const productoNombre = row.dataset.productoNombre.toLowerCase();
                const loteNumero = row.dataset.loteNumero.toLowerCase();

                const matchProducto = productoNombre.includes(productoQuery);
                const matchLote = loteNumero.includes(loteQuery);

                if (matchProducto && matchLote) {
                    row.style.display = '';
                    visibleRows++;
                } else {
                    row.style.display = 'none';
                }
            });
            
            if (noResultsRow) {
                noResultsRow.style.display = visibleRows === 0 ? '' : 'none';
            }
        }

        filtroLoteProducto.addEventListener('input', aplicarFiltrosProductos);
        setupDropdown('filtro-producto', 'lista-productos', aplicarFiltrosProductos);
    }
});
