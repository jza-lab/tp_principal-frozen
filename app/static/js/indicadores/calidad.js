// app/static/js/indicadores/calidad.js

window.renderCalidadTab = async function(data, container, utils) {
    // 1. KPIs Top Row
    let kpiHTML = '<div class="row g-3 mb-4">';
    
    // Alertas Activas
    kpiHTML += utils.renderKpiCard(
        'Alertas Activas', 
        data.alertas_activas, 
        'Pendientes de resolución', 
        'bi-exclamation-triangle', 
        'Cantidad de alertas de riesgo que requieren atención inmediata.', 
        'danger'
    );

    // Tasa de Rechazo Interno
    kpiHTML += utils.renderKpiCard(
        'Rechazo Interno', 
        `${data.tasa_rechazo_interno.valor.toFixed(2)}%`, 
        `${data.tasa_rechazo_interno.rechazadas} un. rechazadas`, 
        'bi-x-octagon', 
        'Porcentaje de inspecciones de calidad en productos terminados que resultaron en rechazo.', 
        'warning'
    );

    // Reclamos Clientes (Tasa)
    kpiHTML += utils.renderKpiCard(
        'Tasa Reclamos', 
        `${data.tasa_reclamos_clientes.valor.toFixed(2)}%`, 
        `${data.tasa_reclamos_clientes.reclamos} reclamos`, 
        'bi-emoji-frown', 
        'Porcentaje de pedidos entregados que generaron un reclamo formal.', 
        'info'
    );

    // Incidentes de Desperdicio
    kpiHTML += utils.renderKpiCard(
        'Desperdicios', 
        data.incidentes_desperdicio, 
        'Reportes registrados', 
        'bi-trash', 
        'Cantidad total de eventos de desperdicio registrados (insumos + productos) en el periodo.', 
        'secondary'
    );

    kpiHTML += '</div>';

    // 2. Charts Grid
    // Row 1: Reclamos (Separados)
    let chartsHTML = '<div class="row g-4 mb-4">';
    
    // Col 1: Reclamos Clientes
    chartsHTML += `
    <div class="col-lg-6">
        ${utils.createSmartCardHTML(
            'chart-reclamos-clientes',
            'Reclamos de Clientes',
            'Evolución temporal de reclamos recibidos.',
            data.evolucion_reclamos_clientes.insight,
            data.evolucion_reclamos_clientes.tooltip
        )}
    </div>`;

    // Col 2: Reclamos Proveedores
    chartsHTML += `
    <div class="col-lg-6">
        ${utils.createSmartCardHTML(
            'chart-reclamos-proveedores',
            'Reclamos a Proveedores',
            'Evolución temporal de reclamos emitidos.',
            data.evolucion_reclamos_proveedores.insight,
            data.evolucion_reclamos_proveedores.tooltip
        )}
    </div>`;
    
    chartsHTML += '</div>';

    // Row 2: Distribución Alertas + Motivos
    chartsHTML += '<div class="row g-4 mb-4">';
    
    // Col 1: Distribución Alertas (Donut)
    chartsHTML += `
    <div class="col-lg-4">
        ${utils.createSmartCardHTML(
            'chart-distribucion-alertas',
            'Origen de Riesgos',
            'Distribución de alertas según la entidad afectada.',
            data.distribucion_alertas.insight,
            data.distribucion_alertas.tooltip
        )}
    </div>`;

    // Col 2: Motivos Alerta (Bar Horizontal)
    chartsHTML += `
    <div class="col-lg-8">
        ${utils.createSmartCardHTML(
            'chart-motivos-alerta',
            'Top Motivos de Riesgo',
            'Causas principales declaradas en las alertas de riesgo.',
            data.motivos_alerta.insight,
            data.motivos_alerta.tooltip
        )}
    </div>`;

    chartsHTML += '</div>';

    // Row 3: Resultados Calidad + Desperdicios
    chartsHTML += '<div class="row g-4 mb-4">';
    
    // Col 1: Resultados Calidad (Stacked Bar)
    chartsHTML += `
    <div class="col-lg-6">
        ${utils.createSmartCardHTML(
            'chart-resultados-calidad',
            'Resultados de Inspección',
            'Desglose de inspecciones por decisión (Aprobado, Rechazado, Cuarentena).',
            data.resultados_calidad.insight,
            data.resultados_calidad.tooltip
        )}
    </div>`;

    // Col 2: Evolución Desperdicios
    chartsHTML += `
    <div class="col-lg-6">
        ${utils.createSmartCardHTML(
            'chart-evolucion-desperdicios-calidad',
            'Tendencia de Desperdicios',
            'Evolución del número de incidentes de desperdicio registrados.',
            data.evolucion_desperdicios.insight,
            data.evolucion_desperdicios.tooltip
        )}
    </div>`;
    chartsHTML += '</div>';

    // Row 4: Top Items Desperdicio
    chartsHTML += '<div class="row g-4 mb-4">';
    chartsHTML += `
    <div class="col-12">
        ${utils.createSmartCardHTML(
            'chart-top-items-desperdicio',
            'Detalle de Desperdicios por Ítem',
            'Insumos y productos con mayor cantidad de reportes de desperdicio.',
            data.top_items_desperdicio.insight,
            data.top_items_desperdicio.tooltip
        )}
    </div>`;
    chartsHTML += '</div>';

    // Inject HTML
    container.innerHTML = kpiHTML + chartsHTML;

    // 3. Init Charts

    // Chart 1: Reclamos Clientes
    if (data.evolucion_reclamos_clientes && data.evolucion_reclamos_clientes.categories.length > 0) {
        utils.createChart('chart-reclamos-clientes', {
            tooltip: { trigger: 'axis' },
            grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
            xAxis: { type: 'category', boundaryGap: false, data: data.evolucion_reclamos_clientes.categories },
            yAxis: { type: 'value' },
            series: data.evolucion_reclamos_clientes.series.map(s => ({
                name: s.name,
                type: 'line',
                smooth: true,
                data: s.data,
                itemStyle: { color: '#0dcaf0' },
                areaStyle: { opacity: 0.1, color: '#0dcaf0' }
            }))
        });
    }

    // Chart 2: Reclamos Proveedores
    if (data.evolucion_reclamos_proveedores && data.evolucion_reclamos_proveedores.categories.length > 0) {
        utils.createChart('chart-reclamos-proveedores', {
            tooltip: { trigger: 'axis' },
            grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
            xAxis: { type: 'category', boundaryGap: false, data: data.evolucion_reclamos_proveedores.categories },
            yAxis: { type: 'value' },
            series: data.evolucion_reclamos_proveedores.series.map(s => ({
                name: s.name,
                type: 'line',
                smooth: true,
                data: s.data,
                itemStyle: { color: '#6c757d' },
                areaStyle: { opacity: 0.1, color: '#6c757d' }
            }))
        });
    }

    // Chart 3: Distribución Alertas (Donut)
    if (data.distribucion_alertas && data.distribucion_alertas.data.length > 0) {
        utils.createChart('chart-distribucion-alertas', {
            tooltip: { trigger: 'item' },
            legend: { bottom: 0, type: 'scroll' },
            series: [{
                name: 'Origen',
                type: 'pie',
                radius: ['40%', '70%'],
                avoidLabelOverlap: false,
                itemStyle: { borderRadius: 5, borderColor: '#fff', borderWidth: 2 },
                label: { show: false, position: 'center' },
                emphasis: { label: { show: true, fontSize: '14', fontWeight: 'bold' } },
                labelLine: { show: false },
                data: data.distribucion_alertas.data
            }]
        });
    }

    // Chart 4: Motivos Alerta (Bar Horizontal)
    if (data.motivos_alerta && data.motivos_alerta.categories.length > 0) {
        utils.createChart('chart-motivos-alerta', {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            xAxis: { type: 'value' },
            yAxis: { type: 'category', data: data.motivos_alerta.categories, inverse: true }, // Inverse to show top on top
            series: [{
                name: 'Alertas',
                type: 'bar',
                data: data.motivos_alerta.values,
                itemStyle: { color: '#6610f2' } // Purple theme
            }]
        });
    }

    // Chart 5: Resultados Calidad (Stacked Bar)
    if (data.resultados_calidad && data.resultados_calidad.categories.length > 0) {
        utils.createChart('chart-resultados-calidad', {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            legend: { bottom: 0 },
            grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
            xAxis: { type: 'value' },
            yAxis: { type: 'category', data: data.resultados_calidad.categories },
            series: data.resultados_calidad.series.map(s => ({
                name: s.name,
                type: 'bar',
                stack: 'total',
                emphasis: { focus: 'series' },
                data: s.data,
                itemStyle: { color: s.color } // Usar colores definidos en backend
            }))
        });
    }

    // Chart 6: Evolución Desperdicios
    if (data.evolucion_desperdicios && data.evolucion_desperdicios.categories.length > 0) {
        utils.createChart('chart-evolucion-desperdicios-calidad', {
            tooltip: { trigger: 'axis' },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            xAxis: { type: 'category', boundaryGap: false, data: data.evolucion_desperdicios.categories },
            yAxis: { type: 'value' },
            series: [{
                name: 'Incidentes',
                type: 'line',
                smooth: true,
                data: data.evolucion_desperdicios.values,
                itemStyle: { color: '#fd7e14' }, // Orange
                areaStyle: { opacity: 0.1, color: '#fd7e14' }
            }]
        });
    }

    // Chart 7: Top Items Desperdicio
    if (data.top_items_desperdicio && data.top_items_desperdicio.categories.length > 0) {
        utils.createChart('chart-top-items-desperdicio', {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            xAxis: { type: 'value' },
            yAxis: { type: 'category', data: data.top_items_desperdicio.categories, inverse: true },
            series: [{
                name: 'Reportes',
                type: 'bar',
                data: data.top_items_desperdicio.values,
                itemStyle: { color: '#6c757d' }, // Secondary gray
                barMaxWidth: 40
            }]
        });
    }
};
