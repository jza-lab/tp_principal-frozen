google.charts.load('current', { 'packages': ['sankey'] });

document.addEventListener('DOMContentLoaded', function () {
    const TIPO_ENTIDAD = 'orden_compra';
    const ID_ENTIDAD = window.ORDEN_COMPRA_ID;

    // Elementos del DOM
    const trazabilidadTab = document.querySelector('#trazabilidad-tab');
    const sankeyContainer = document.getElementById('sankey_trazabilidad');
    const nivelSwitch = document.getElementById('trazabilidad-nivel-switch');
    const accordionButton = document.querySelector('#accordionDiagrama .accordion-button');

    let chart = null;
    let datosCompletosCache = null;

    // --- Funciones auxiliares ---
    function agruparPorTipo(items) {
        return items.reduce((acc, item) => {
            (acc[item.tipo] = acc[item.tipo] || []).push(item);
            return acc;
        }, {});
    }

    function formatearTipo(tipo) {
        const titulos = {
            'orden_compra': 'Órdenes de Compra',
            'lote_insumo': 'Lotes de Insumo',
            'orden_produccion': 'Órdenes de Producción',
            'lote_producto': 'Lotes de Producto',
            'pedido': 'Pedidos de Venta'
        };
        return titulos[tipo] || tipo.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    // --- Funciones de renderizado ---
    function mostrarCargando() {
        const contenedorOrigen = document.getElementById('resumen-trazabilidad-origen');
        const contenedorDestino = document.getElementById('resumen-trazabilidad-destino');
        
        if (contenedorOrigen) contenedorOrigen.innerHTML = ''; // Origen no aplica para OC
        if (contenedorDestino) {
            contenedorDestino.innerHTML = `<div class="text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Cargando...</span></div><p class="mt-2">Cargando resumen...</p></div>`;
        }
        if (sankeyContainer) {
            sankeyContainer.innerHTML = `<div class="d-flex justify-content-center align-items-center h-100"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Cargando...</span></div><p class="ms-2">Cargando diagrama...</p></div>`;
        }
    }

    function renderizarResumen(resumen) {
        const contenedorOrigen = document.getElementById('resumen-trazabilidad-origen');
        const contenedorDestino = document.getElementById('resumen-trazabilidad-destino');

        if (!contenedorOrigen || !contenedorDestino) return;

        // Limpiar contenedores
        contenedorOrigen.innerHTML = '';
        contenedorDestino.innerHTML = '';

        if (!resumen || (!resumen.origen.length && !resumen.destino.length)) {
            contenedorDestino.innerHTML = '<p class="text-muted">No hay datos de resumen para mostrar.</p>';
            return;
        }

        // Para una OC, el origen es ella misma o un ingreso manual, por lo que no se muestra.
        
        // Procesar Destino (Hacia adelante)
        if (resumen.destino.length > 0) {
            const destinoAgrupado = agruparPorTipo(resumen.destino);
            let destinoHtml = '<h5 class="mb-3 border-bottom pb-2"><i class="bi bi-arrow-down-circle-fill text-success me-2"></i>Destino / Hacia adelante</h5>';
            
            for (const tipo in destinoAgrupado) {
                destinoHtml += `<h6>${formatearTipo(tipo)}</h6>`;
                destinoHtml += '<ul class="list-group list-group-flush mb-3">';
                destinoHtml += destinoAgrupado[tipo].map(item => `
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                            <a href="${(urls[item.tipo] || '#').replace('<id>', item.id)}" class="fw-bold text-decoration-none">${item.nombre}</a>
                            <div class="text-muted small">${item.detalle || ''}</div>
                        </div>
                        ${item.cantidad ? `<span class="badge bg-secondary rounded-pill">${item.cantidad}</span>` : ''}
                    </li>
                `).join('');
                destinoHtml += '</ul>';
            }
            contenedorDestino.innerHTML = destinoHtml;
        } else {
            contenedorDestino.innerHTML = `
                <h5 class="mb-3 border-bottom pb-2"><i class="bi bi-arrow-down-circle-fill text-success me-2"></i>Destino / Hacia adelante</h5>
                <p class="text-muted">No hay entidades posteriores en la trazabilidad.</p>`;
        }
    }

    function renderizarSankey(diagrama) {
        if (!sankeyContainer) return;

        if (!diagrama || !diagrama.edges || !diagrama.edges.length) {
            sankeyContainer.innerHTML = '<div class="alert alert-info m-3">No hay flujos de trazabilidad para mostrar en el diagrama.</div>';
            if (accordionButton) {
                accordionButton.textContent = 'No hay diagrama disponible';
                accordionButton.classList.add('disabled');
            }
            return;
        }

        if (accordionButton) {
            accordionButton.textContent = 'Ver Diagrama de Flujo (Sankey)';
            accordionButton.classList.remove('disabled');
        }

        const data = new google.visualization.DataTable();
        data.addColumn('string', 'De');
        data.addColumn('string', 'A');
        data.addColumn('number', 'Cantidad');

        const nodeLabels = {};
        diagrama.nodes.forEach(node => {
            nodeLabels[node.id] = node.label;
        });

        const rows = diagrama.edges.map(edge => [
            nodeLabels[edge.from],
            nodeLabels[edge.to],
            parseFloat(edge.label) || 0
        ]);

        data.addRows(rows);
        const options = { width: '100%', height: 600, sankey: { node: { label: { fontSize: 12 } }, link: { colorMode: 'gradient' } } };
        
        if (chart) chart.clearChart();
        chart = new google.visualization.Sankey(sankeyContainer);
        chart.draw(data, options);
    }

    // --- Lógica de Carga ---
    function cargarDatosTrazabilidad(nivel = 'simple') {
        if (!ID_ENTIDAD) return;

        if (nivel === 'completo' && datosCompletosCache) {
            renderizarResumen(datosCompletosCache.resumen);
            google.charts.setOnLoadCallback(() => renderizarSankey(datosCompletosCache.diagrama));
            return;
        }

        mostrarCargando();
        fetch(`/api/trazabilidad/${TIPO_ENTIDAD}/${ID_ENTIDAD}?nivel=${nivel}`)
            .then(response => response.ok ? response.json() : Promise.reject('Error de red'))
            .then(result => {
                if (result.success && result.data) {
                    if (nivel === 'completo') datosCompletosCache = result.data;
                    renderizarResumen(result.data.resumen);
                    google.charts.setOnLoadCallback(() => renderizarSankey(result.data.diagrama));
                } else {
                    const errorMsg = result.error || 'No se pudieron cargar los datos.';
                    const contenedorDestino = document.getElementById('resumen-trazabilidad-destino');
                    if (contenedorDestino) contenedorDestino.innerHTML = `<div class="alert alert-warning">${errorMsg}</div>`;
                    if (sankeyContainer) sankeyContainer.innerHTML = '';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                const contenedorDestino = document.getElementById('resumen-trazabilidad-destino');
                if (contenedorDestino) contenedorDestino.innerHTML = `<div class="alert alert-danger">Error de conexión al cargar el resumen.</div>`;
                if (sankeyContainer) sankeyContainer.innerHTML = `<div class="alert alert-danger m-3">Error de conexión al cargar el diagrama.</div>`;
            });
    }

    // --- Event Listeners ---
    if (trazabilidadTab) {
        trazabilidadTab.addEventListener('shown.bs.tab', () => cargarDatosTrazabilidad('simple'), { once: true });
    }

    if (nivelSwitch) {
        nivelSwitch.addEventListener('change', function () {
            cargarDatosTrazabilidad(this.checked ? 'completo' : 'simple');
        });
    }

    const urls = {
        orden_compra: '/compras/detalle/<id>',
        lote_insumo: '/inventario/lote/<id>',
        orden_produccion: '/ordenes_produccion/<id>/detalle',
        lote_producto: '/lotes-productos/<id>/detalle',
        pedido: '/orden-venta/<id>/detalle'
    };
});
