google.charts.load('current', { 'packages': ['sankey'] });

document.addEventListener('DOMContentLoaded', function () {
    const TIPO_ENTIDAD = 'orden_compra';
    const ID_ENTIDAD = window.ORDEN_COMPRA_ID;

    // Elementos del DOM
    const trazabilidadTab = document.querySelector('#trazabilidad-tab');
    const sankeyContainer = document.getElementById('sankey_trazabilidad');
    const resumenContenedor = document.getElementById('resumen-trazabilidad-contenedor');
    const nivelSwitch = document.getElementById('trazabilidad-nivel-switch');
    const accordionButton = document.querySelector('#accordionDiagrama .accordion-button');

    let chart = null;
    let datosCompletosCache = null;

    function mostrarCargando() {
        resumenContenedor.innerHTML = `<div class="card-header"><i class="bi bi-list-ul me-1"></i> Resumen de Trazabilidad</div><div class="card-body text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Cargando...</span></div><p class="mt-2">Cargando resumen...</p></div>`;
        sankeyContainer.innerHTML = `<div class="d-flex justify-content-center align-items-center h-100"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Cargando gráfico...</span></div></div>`;
    }

    function renderizarResumen(resumen) {
        if (!resumen || (!resumen.origen.length && !resumen.destino.length)) {
            resumenContenedor.innerHTML = '<div class="card-header"><i class="bi bi-list-ul me-1"></i> Resumen de Trazabilidad</div><div class="card-body"><p class="text-muted">No hay datos de resumen para mostrar.</p></div>';
            return;
        }

        // Para OC, el origen es ella misma o manual, no se muestra. El destino es lo importante.
        const destinoHtml = resumen.destino.length ? resumen.destino.map(item => `
            <li class="list-group-item">
                <a href="${urls[item.tipo] || '#'}${item.id}" class="fw-bold">${item.nombre}</a>
                <div class="text-muted small">${item.detalle}</div>
            </li>`).join('') : '<li class="list-group-item text-muted">No se han generado lotes de insumo desde esta orden.</li>';

        resumenContenedor.innerHTML = `
            <div class="card-header"><i class="bi bi-list-ul me-1"></i> Resumen de Trazabilidad</div>
            <div class="card-body">
                <h5 class="mb-3 border-bottom pb-2"><i class="bi bi-arrow-down-circle-fill text-success me-2"></i>Destino (Hacia Adelante)</h5>
                <ul class="list-group list-group-flush">${destinoHtml}</ul>
            </div>`;
    }

    function renderizarSankey(diagrama) {
        if (!diagrama || !diagrama.edges || !diagrama.edges.length) {
            sankeyContainer.innerHTML = '<div class="alert alert-info">No hay flujos de trazabilidad para mostrar en el diagrama.</div>';
            accordionButton.textContent = 'No hay diagrama disponible';
            accordionButton.classList.add('disabled');
            return;
        }

        accordionButton.textContent = 'Ver Diagrama de Flujo Completo';
        accordionButton.classList.remove('disabled');

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
        const options = { width: '100%', height: 300, sankey: { node: { label: { fontSize: 12 } }, link: { colorMode: 'gradient' } } };
        
        if (chart) chart.clearChart();
        chart = new google.visualization.Sankey(sankeyContainer);
        chart.draw(data, options);
    }

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
                    resumenContenedor.innerHTML = `<div class="card-header">...</div><div class="card-body"><div class="alert alert-warning">${result.error || 'No se pudieron cargar los datos.'}</div></div>`;
                    sankeyContainer.innerHTML = '';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                resumenContenedor.innerHTML = `<div class="card-header">...</div><div class="card-body"><div class="alert alert-danger">Error de conexión.</div></div>`;
                sankeyContainer.innerHTML = '';
            });
    }

    if (trazabilidadTab) {
        trazabilidadTab.addEventListener('shown.bs.tab', () => cargarDatosTrazabilidad('simple'), { once: true });
    }

    if (nivelSwitch) {
        nivelSwitch.addEventListener('change', function () {
            cargarDatosTrazabilidad(this.checked ? 'completo' : 'simple');
        });
    }

    const urls = {
        orden_compra: '/compras/detalle/',
        lote_insumo: '/inventario/lote/',
        orden_produccion: '/ordenes_produccion/detalle/',
        lote_producto: '/lotes-productos/detalle/',
        pedido: '/orden-venta/detalle/'
    };
});
