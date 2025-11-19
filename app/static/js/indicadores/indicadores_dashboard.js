document.addEventListener('DOMContentLoaded', function () {
    const tabElements = document.querySelectorAll('#kpiTab .nav-link');
    const tabContentContainer = document.getElementById('kpiTabContent');
    let loadedTabs = new Set();
    let chartInstances = {}; // Para almacenar instancias de ECharts

    // --- UTILS ---
    function getApiUrl(category) {
        const selectedPeriodInput = document.querySelector('input[name="periodo"]:checked');
        const periodo = selectedPeriodInput ? selectedPeriodInput.value : 'semanal';
        return `/reportes/api/indicadores/${category}?periodo=${periodo}`;
    }

    function showLoading(tabPane) {
        tabPane.innerHTML = `
            <div class="loading-placeholder text-center p-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Cargando...</span>
                </div>
                <p class="mt-2">Cargando datos...</p>
            </div>`;
    }

    function showError(tabPane, message) {
        // --- MODIFICADO: Añadido console.log para debugging ---
        console.log("Mostrando error en UI:", message); 
        // --- MODIFICADO: Mensaje de error más claro ---
        tabPane.innerHTML = `
            <div class="alert alert-danger text-center p-5" role="alert">
                <strong>Error al cargar:</strong> ${message || 'No se pudieron cargar los datos.'}
            </div>`;
    }
    
    // --- RENDER FUNCTIONS ---

    function createChart(containerId, options, category) {
        const chartDom = document.getElementById(containerId);
        if (!chartDom) return;

        // Limpiar instancia previa si existe
        if (chartInstances[containerId]) {
            chartInstances[containerId].dispose();
        }

        // --- NUEVA LÓGICA: Mostrar mensaje si no hay datos ---
        const hasData = options.series && options.series.some(s => s.data && s.data.length > 0);
        
        if (!hasData) {
            chartDom.innerHTML = `<div class="d-flex justify-content-center align-items-center h-100 text-muted">No hay datos disponibles para el período seleccionado.</div>`;
            return; // No inicializar ECharts
        }
        // --- FIN NUEVA LÓGICA ---

        const chart = echarts.init(chartDom);
        chart.setOption(options);
        chartInstances[containerId] = chart;
    }

    function renderKpiCard(title, value, subtitle, iconClass = 'bi-bar-chart-line') {
        return `
        <div class="col-md-4 mb-4">
            <div class="card text-center h-100">
                <div class="card-header">${title}</div>
                <div class="card-body">
                    <i class="bi ${iconClass} fs-1 text-primary"></i>
                    <h2 class="card-title my-2">${value}</h2>
                    <p class="card-text text-muted">${subtitle}</p>
                </div>
            </div>
        </div>`;
    }

    function renderChartCard(chartId, title, subtitle, tooltip, downloadId, chartHeight = '400px') {
         return `
            <div class="card h-100">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="card-title mb-0">${title}</h5>
                        <small class="text-muted">${subtitle}</small>
                    </div>
                    <i class="bi bi-info-circle" data-bs-toggle="tooltip" title="${tooltip}"></i>
                </div>
                <div class="card-body">
                    <div id="${chartId}" style="height: ${chartHeight};"></div>
                    <p id="${chartId}-descripcion" class="mt-2 text-center small"></p>
                </div>
                <div class="card-footer text-end">
                    <button id="${downloadId}" class="btn btn-sm btn-outline-secondary">Descargar</button>
                </div>
            </div>`;
    }
    
    // --- DATA LOADING & RENDERING ---
    
    async function loadTabData(category) {
        const tabPane = document.querySelector(`#${category}`);
        if (!tabPane || loadedTabs.has(category)) {
            return; // Ya cargado o no encontrado
        }
        
        showLoading(tabPane);
        
        try {
            const response = await fetch(getApiUrl(category));
            if (!response.ok) {
                throw new Error(`Error del servidor: ${response.statusText} (Status: ${response.status})`);
            }
            const data = await response.json();
            
            // Limpiar contenido de carga y renderizar
            tabPane.innerHTML = '';
            
            // Mapeo para llamar a la función de renderizado correcta
            const renderFunctions = {
                'produccion': renderProduccion,
                'calidad': renderCalidad,
                'comercial': renderComercial,
                'financiera': renderFinanciera,
                'inventario': renderInventario,
            };

            if (renderFunctions[category]) {
                renderFunctions[category](data);
            } else {
                 showError(tabPane, `No hay una función de renderizado para '${category}'.`);
            }
            
            loadedTabs.add(category); // Marcar como cargado
            
            // Re-inicializar tooltips de Bootstrap
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
            var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl)
            });

        } catch (error) {
            // --- MODIFICADO: Añadido console.error para debugging ---
            console.error(`Error detallado al cargar datos para ${category}:`, error);
            showError(tabPane, error.message);
        }
    }
    
    function renderProduccion(data) {
        const container = document.getElementById('produccion');
        let content = '<div class="row mt-4">';
        content += renderKpiCard('OEE', `${data.oee.valor.toFixed(2)}%`, `Disponibilidad: ${(data.oee.disponibilidad * 100).toFixed(1)}% | Rendimiento: ${(data.oee.rendimiento * 100).toFixed(1)}% | Calidad: ${(data.oee.calidad * 100).toFixed(1)}%`);
        content += renderKpiCard('Cumplimiento del Plan', `${data.cumplimiento_plan.valor.toFixed(2)}%`, `${data.cumplimiento_plan.completadas_a_tiempo} de ${data.cumplimiento_plan.planificadas} órdenes a tiempo`);
        content += '</div>';
        container.innerHTML = content;
    }

    function renderCalidad(data) {
        const container = document.getElementById('calidad');
        let content = '<div class="row mt-4">';
        content += renderKpiCard('Rechazo Interno', `${data.tasa_rechazo_interno.valor.toFixed(2)}%`, `${data.tasa_rechazo_interno.rechazadas} de ${data.tasa_rechazo_interno.inspeccionadas} unidades rechazadas`);
        content += renderKpiCard('Reclamos de Clientes', `${data.tasa_reclamos_clientes.valor.toFixed(2)}%`, `${data.tasa_reclamos_clientes.reclamos} reclamos en ${data.tasa_reclamos_clientes.pedidos_entregados} pedidos`);
        content += renderKpiCard('Rechazo de Proveedores', `${data.tasa_rechazo_proveedores.valor.toFixed(2)}%`, `${data.tasa_rechazo_proveedores.rechazados} de ${data.tasa_rechazo_proveedores.recibidos} lotes rechazados`);
        content += '</div>';
        container.innerHTML = content;
    }

    function renderComercial(data) {
        const container = document.getElementById('comercial');
        let content = '<div class="row mt-4">';
        content += renderKpiCard('Cumplimiento de Pedidos', `${data.kpis_comerciales.cumplimiento_pedidos.valor.toFixed(2)}%`, `${data.kpis_comerciales.cumplimiento_pedidos.completados} de ${data.kpis_comerciales.cumplimiento_pedidos.total} pedidos a tiempo`);
        content += renderKpiCard('Valor Promedio Pedido', `$${data.kpis_comerciales.valor_promedio_pedido.valor.toFixed(2)}`, `Basado en ${data.kpis_comerciales.valor_promedio_pedido.num_pedidos} pedidos`);
        content += '</div><div class="row mt-4"><div class="col-lg-6 mb-4">';
        content += renderChartCard('top-productos-chart', 'Top 5 Productos Vendidos', 'Productos más vendidos por cantidad.', 'Suma de cantidades en pedidos completados.', 'download-top-productos');
        content += '</div><div class="col-lg-6 mb-4">';
        content += renderChartCard('top-clientes-chart', 'Top 5 Clientes', 'Clientes con mayor valor de compra.', 'Suma del total de pedidos completados.', 'download-top-clientes');
        content += '</div></div>';
        container.innerHTML = content;

        renderPeriodFilter('comercial', 'comercial');

        createChart('top-productos-chart', {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            xAxis: { type: 'category', data: data.top_productos_vendidos.labels },
            yAxis: { type: 'value' },
            series: [{ data: data.top_productos_vendidos.data, type: 'bar' }]
        });
        
        createChart('top-clientes-chart', {
             tooltip: { trigger: 'item' },
             series: [{ type: 'pie', radius: '50%', data: data.top_clientes.labels.map((name, i) => ({value: data.top_clientes.data[i], name})) }]
        });
    }

    function renderFinanciera(data) {
        const container = document.getElementById('financiera');
        let content = '<div class="row mt-4">';
        // Aquí podrías renderizar KPIs financieros si los hubiera en el futuro.
        // Por ahora, como no hay KPIs numéricos definidos para esta sección,
        // podrías mostrar un mensaje o simplemente dejarlo vacío.
        // Para este caso, mostraremos los KPIs que ya se calculan en el backend
        // aunque no estuvieran visibles antes.
        if (data.kpis_financieros) {
            content += renderKpiCard(data.kpis_financieros.facturacion_total.etiqueta, `$${data.kpis_financieros.facturacion_total.valor.toFixed(2)}`, `Período seleccionado`);
            content += renderKpiCard(data.kpis_financieros.costo_total.etiqueta, `$${data.kpis_financieros.costo_total.valor.toFixed(2)}`, `Costo de Ventas (COGS)`);
            content += renderKpiCard(data.kpis_financieros.beneficio_bruto.etiqueta, `$${data.kpis_financieros.beneficio_bruto.valor.toFixed(2)}`, `Facturación - Costo Total`);
            content += renderKpiCard(data.kpis_financieros.margen_beneficio.etiqueta, `${data.kpis_financieros.margen_beneficio.valor.toFixed(2)}%`, `(Beneficio / Facturación) * 100`);
        }
        content += '</div>';
        container.innerHTML = content;
    }
    
    function renderInventario(data) {
        const container = document.getElementById('inventario');
        let content = '<div class="row mt-4">';
        content += renderKpiCard('Rotación de Inventario', data.kpis_inventario.rotacion_inventario.valor.toFixed(2), `Basado en un COGS de $${data.kpis_inventario.rotacion_inventario.cogs.toFixed(0)} y stock valorizado de $${data.kpis_inventario.rotacion_inventario.inventario_valorizado.toFixed(0)}`);
        content += '</div><div class="row mt-4"><div class="col-lg-6 mb-4">';
        content += renderChartCard('antiguedad-insumos-chart', 'Antigüedad de Stock (Insumos)', 'Valor del inventario por antigüedad.', 'Basado en fecha de ingreso de lotes.', 'download-antiguedad-insumos');
        content += '</div><div class="col-lg-6 mb-4">';
        content += renderChartCard('antiguedad-productos-chart', 'Antigüedad de Stock (Productos)', 'Valor del inventario por antigüedad.', 'Basado en fecha de producción de lotes.', 'download-antiguedad-productos');
        content += '</div></div>';
        container.innerHTML = content;

        createChart('antiguedad-insumos-chart', {
             tooltip: { trigger: 'item' },
             series: [{ type: 'pie', data: data.antiguedad_stock_insumos.labels.map((name, i) => ({value: data.antiguedad_stock_insumos.data[i], name})) }]
        });
        createChart('antiguedad-productos-chart', {
             tooltip: { trigger: 'item' },
             series: [{ type: 'pie', data: data.antiguedad_stock_productos.labels.map((name, i) => ({value: data.antiguedad_stock_productos.data[i], name})) }]
        });
    }

    function renderPeriodFilter(containerId, category) {
        const filterHtml = `
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Filtrar por Período</h5>
                    <div id="period-filter-${category}" class="btn-group" role="group" aria-label="Selector de período">
                        <input type="radio" class="btn-check" name="periodo-${category}" id="periodo_semanal_${category}" value="semanal" autocomplete="off" checked>
                        <label class="btn btn-outline-primary" for="periodo_semanal_${category}">Semanal</label>
                        <input type="radio" class="btn-check" name="periodo-${category}" id="periodo_mensual_${category}" value="mensual" autocomplete="off">
                        <label class="btn btn-outline-primary" for="periodo_mensual_${category}">Mensual</label>
                        <input type="radio" class="btn-check" name="periodo-${category}" id="periodo_anual_${category}" value="anual" autocomplete="off">
                        <label class="btn btn-outline-primary" for="periodo_anual_${category}">Anual</label>
                    </div>
                </div>
            </div>`;
        
        const container = document.getElementById(containerId);
        if(container) {
            const firstChild = container.firstChild;
            container.insertAdjacentHTML('afterbegin', filterHtml);

            // Añadir el listener
            const periodFilterGroup = document.getElementById(`period-filter-${category}`);
            periodFilterGroup.addEventListener('change', event => {
                loadedTabs.delete(category);
                chartInstances = {};
                loadTabData(category);
            });
        }
    }

    // --- EVENT LISTENERS ---

    tabElements.forEach(tab => {
        tab.addEventListener('shown.bs.tab', event => {
            const category = event.target.dataset.category;
            loadTabData(category);
        });
    });

    // Cargar la primera pestaña activa al inicio
    const initialActiveTab = document.querySelector('#kpiTab .nav-link.active');
    if (initialActiveTab) {
        loadTabData(initialActiveTab.dataset.category);
    }
});