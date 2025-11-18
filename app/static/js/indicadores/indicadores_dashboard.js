document.addEventListener('DOMContentLoaded', function () {
    const tabElements = document.querySelectorAll('#kpiTab .nav-link');
    const filterForm = document.getElementById('filter-form');
    const tabContentContainer = document.getElementById('kpiTabContent');
    let loadedTabs = new Set();
    let chartInstances = {}; // Para almacenar instancias de ECharts

    // --- UTILS ---
    function getApiUrl(category) {
        const startDate = document.getElementById('fecha_inicio').value;
        const endDate = document.getElementById('fecha_fin').value;
        return `/reportes/api/indicadores/${category}?fecha_inicio=${startDate}&fecha_fin=${endDate}`;
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
        content += '</div> <div class="row mt-4"><div class="col-lg-12 mb-4">';
        content += renderChartCard('pareto-desperdicio-chart', 'Análisis de Causas de Desperdicio (Pareto)', 'Identifica las causas más significativas de desperdicio.', 'Regla 80/20 para encontrar las causas vitales.', 'download-pareto');
        content += '</div></div>';
        container.innerHTML = content;
        
        createChart('pareto-desperdicio-chart', {
            tooltip: { trigger: 'axis' },
            xAxis: { type: 'category', data: data.causas_desperdicio_pareto.labels },
            yAxis: [ { type: 'value', name: 'Cantidad' }, { type: 'value', name: 'Porcentaje Acumulado', axisLabel: { formatter: '{value}%' } } ],
            series: [
                { name: 'Cantidad', type: 'bar', data: data.causas_desperdicio_pareto.data },
                { name: 'Acumulado', type: 'line', yAxisIndex: 1, data: data.causas_desperdicio_pareto.line_data }
            ]
        });
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
        let content = '<div class="row mt-4"><div class="col-lg-12 mb-4">';
        content += renderChartCard('facturacion-chart', 'Facturación en el Tiempo', 'Evolución de ingresos por ventas.', 'Suma del valor de pedidos completados.', 'download-facturacion');
        content += '</div></div><div class="row mt-4"><div class="col-lg-7 mb-4">';
        content += renderChartCard('costo-ganancia-chart', 'Costos vs. Ingresos', 'Costos de producción vs. ingresos por ventas.', 'Estimación de costos de materia prima.', 'download-costo-ganancia');
        content += '</div><div class="col-lg-5 mb-4">';
        content += renderChartCard('descomposicion-costos-chart', 'Descomposición de Costos', 'Distribución de costos operativos.', 'Mano de obra y gastos fijos son estimados.', 'download-descomposicion');
        content += '</div></div><div class="row mt-4"><div class="col-lg-12 mb-4">';
        content += renderChartCard('rentabilidad-productos-chart', 'Rentabilidad por Producto (Top 5)', "Ingresos vs. costos de los productos más vendidos. <br><a href='/analisis/rentabilidad' class='text-warning fw-bold text-decoration-underline'><i class='bi bi-exclamation-triangle-fill me-1'></i>Aviso: Esta es una vista general. Para un análisis detallado, haga clic aquí.</a>", 'Basado en recetas activas y precios de catálogo.', 'download-rentabilidad');
        content += '</div></div>';
        container.innerHTML = content;

        createChart('facturacion-chart', {
             tooltip: { trigger: 'axis' },
             xAxis: { type: 'category', data: data.facturacion_periodo.labels },
             yAxis: { type: 'value' },
             series: [{ data: data.facturacion_periodo.data, type: 'line', smooth: true }]
        });
        createChart('costo-ganancia-chart', {
             tooltip: { trigger: 'axis' },
             legend: { data: ['Ingresos', 'Costos'] },
             xAxis: { type: 'category', data: data.costo_vs_ganancia.labels },
             yAxis: { type: 'value' },
             series: [
                { name: 'Ingresos', type: 'line', data: data.costo_vs_ganancia.ingresos, smooth: true },
                { name: 'Costos', type: 'line', data: data.costo_vs_ganancia.costos, smooth: true, lineStyle: { type: 'dashed' } }
             ]
        });
        createChart('descomposicion-costos-chart', {
             tooltip: { trigger: 'item' },
             series: [{ type: 'pie', radius: ['40%', '70%'], data: data.descomposicion_costos.labels.map((name, i) => ({value: data.descomposicion_costos.data[i], name})) }]
        });
        createChart('rentabilidad-productos-chart', {
            tooltip: { trigger: 'axis' },
            legend: { data: ['Ingresos', 'Costos', 'Rentabilidad Neta'] },
            xAxis: { type: 'category', data: data.rentabilidad_productos.labels },
            yAxis: { type: 'value' },
            series: [
                { name: 'Ingresos', type: 'bar', data: data.rentabilidad_productos.ingresos },
                { name: 'Costos', type: 'bar', data: data.rentabilidad_productos.costos },
                { name: 'Rentabilidad Neta', type: 'line', data: data.rentabilidad_productos.rentabilidad_neta }
            ]
        });
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

    // --- EVENT LISTENERS ---

    tabElements.forEach(tab => {
        tab.addEventListener('shown.bs.tab', event => {
            const category = event.target.dataset.category;
            loadTabData(category);
        });
    });

    filterForm.addEventListener('submit', event => {
        event.preventDefault();
        const activeTab = document.querySelector('#kpiTab .nav-link.active');
        if (activeTab) {
            const category = activeTab.dataset.category;
            loadedTabs.clear(); // Forzar recarga de todas las pestañas
            chartInstances = {}; // Limpiar instancias de gráficos
            loadTabData(category);
        }
    });

    // Cargar la primera pestaña activa al inicio
    const initialActiveTab = document.querySelector('#kpiTab .nav-link.active');
    if (initialActiveTab) {
        loadTabData(initialActiveTab.dataset.category);
    }
});