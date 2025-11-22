const finanzasColors = ['#198754', '#dc3545', '#0d6efd', '#ffc107', '#6610f2'];

window.renderFinanciera = function(data, container, utils) {
    const { renderKpiCard, createSmartCardHTML, createChart } = utils;

    let content = '<div class="row g-3 mb-3">';
    if (data.kpis_financieros) {
        content += renderKpiCard(
            'Ventas', 
            `$${data.kpis_financieros.ventas_totales.valor.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, 
            `Total (Devengado)`, 'bi-receipt', 
            'Total de ventas facturadas/confirmadas (aunque no se hayan cobrado).', 'primary');
        
        content += renderKpiCard(
            'Flujo Caja', 
            `$${data.kpis_financieros.flujo_caja_real.valor.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, 
            `Real (Percibido)`, 'bi-wallet2', 
            'Dinero real ingresado por cobros verificados en este periodo.', 'success');

        content += renderKpiCard(
            'Por Cobrar', 
            `$${data.kpis_financieros.ingreso_pendiente.valor.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, 
            `Pendiente`, 'bi-hourglass-split', 
            'Ventas confirmadas que aún no tienen el pago verificado.', 'warning');

        content += renderKpiCard(
            'Egresos', 
            `$${data.kpis_financieros.costo_total.valor.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, 
            `Est. Operativos`, 'bi-cash-stack', 
            'Estimación de costos operativos asociados a lo producido/vendido.', 'danger');
    } else {
        content += '<div class="col-12"><div class="alert alert-light border text-center text-muted small">Sin datos financieros.</div></div>';
    }
    content += '</div>';

    // Row 1: Ingresos Evolución & Egresos Básicos (with Drilldown)
    content += '<div class="row g-3 mb-4">';
    
    // 1. Evolución de Ingresos
    content += '<div class="col-lg-8">';
    content += createSmartCardHTML(
        'evolucion-ingresos-chart',
        'Evolución de Ingresos por Ventas',
        'Tendencia temporal de la facturación.',
        data.evolucion_ingresos?.insight || 'Sin datos.',
        'Muestra cómo han variado los ingresos por ventas confirmadas a lo largo del periodo seleccionado.'
    );
    content += '</div>';

    // 2. Egresos Básicos (Pie / Drilldown)
    content += '<div class="col-lg-4">';
    // Container for the pie chart, which might be replaced by drilldown
    content += createSmartCardHTML(
        'descomposicion-costos-chart',
        'Egresos Básicos (Desglose)',
        'Distribución de costos principales.',
        data.descomposicion_costos?.insight || 'Sin datos.',
        'Desglose de Materia Prima, Mano de Obra y Costos Fijos. Haga clic en "Costos Fijos" para ver detalle.'
    );
    content += '</div>';
    content += '</div>'; // End Row 1

    // Row 2: Ingresos vs Egresos & Evolución Costos Fijos
    content += '<div class="row g-3 mb-4">';
    
    // 3. Ingresos vs Egresos
    content += '<div class="col-lg-6">';
    content += createSmartCardHTML(
        'ingresos-vs-egresos-chart',
        'Ingresos vs Egresos Básicos',
        'Comparativa de flujo de caja operativo (estimado).',
        data.ingresos_vs_egresos?.insight || 'Sin datos.',
        'Comparación directa. Nota: Los egresos son valores aproximados calculados sobre estándares.'
    );
    content += '</div>';

    // 4. Evolución Costos Fijos
    content += '<div class="col-lg-6">';
    content += createSmartCardHTML(
        'evolucion-costos-fijos-chart',
        'Evolución de Egresos Fijos',
        'Historial del valor total de costos fijos.',
        data.evolucion_costos_fijos?.insight || 'Sin datos.',
        'Muestra cómo ha variado la carga mensual de costos fijos registrados en el sistema.'
    );
    content += '</div>';
    content += '</div>'; // End Row 2

    // Row 3: Matriz Rentabilidad (Scatter)
    content += '<div class="row g-3">';
    content += '<div class="col-12">';
    content += createSmartCardHTML(
        'treemap-rentabilidad-chart',
        'Matriz de Rentabilidad (Ventas vs Margen)',
        'Posicionamiento de productos según su desempeño.',
        'Cuadrante superior derecho: Productos Estrella (Alta Venta, Alto Margen).',
        'Eje X: Ventas Totales ($). Eje Y: Margen de Ganancia (%). Las líneas punteadas indican el promedio.'
    );
    content += '</div>';
    content += '</div>'; // End Row 3

    container.innerHTML = content;

    // --- CHART CONFIGURATION ---

    // 1. Evolución Ingresos
    if (data.evolucion_ingresos) {
        const seriesConfig = (data.evolucion_ingresos.series || []).map(s => ({
            name: s.name,
            type: 'line',
            smooth: true,
            connectNulls: true,
            symbol: 'circle', 
            symbolSize: 6,
            areaStyle: { opacity: 0.05 },
            data: s.data,
            itemStyle: { 
                color: s.name.includes('Ventas') ? '#0d6efd' : '#198754' 
            }
        }));

        createChart('evolucion-ingresos-chart', {
            tooltip: { 
                trigger: 'axis',
                formatter: function (params) {
                    let res = `<div class="mb-1 fw-bold small">${params[0].name}</div>`;
                    let sales = 0;
                    let cash = 0;
                    params.forEach(item => {
                        const val = parseFloat(item.value) || 0;
                        res += `<div class="d-flex justify-content-between align-items-center gap-3 small">
                                    <span>${item.marker} ${item.seriesName}</span>
                                    <span class="fw-bold">$${val.toLocaleString()}</span>
                                </div>`;
                        if (item.seriesName.includes('Ventas')) sales = val;
                        if (item.seriesName.includes('Flujo')) cash = val;
                    });
                    
                    let pending = sales - cash;
                    if (pending > 0.01) {
                         res += `<div class="mt-2 pt-1 border-top border-light-subtle text-warning d-flex justify-content-between align-items-center small">
                            <span><i class="bi bi-hourglass-split"></i> Pendiente</span>
                            <span class="fw-bold">$${pending.toLocaleString()}</span>
                         </div>`;
                    }
                    return res;
                }
            },
            legend: { bottom: 0, icon: 'circle' },
            grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
            xAxis: { type: 'category', data: data.evolucion_ingresos.categories },
            yAxis: { type: 'value' },
            series: seriesConfig
        });
    }

    // 2. Descomposición Costos (with Drilldown Logic)
    if (data.descomposicion_costos) {
        const mainData = data.descomposicion_costos.data;
        const drilldownData = data.descomposicion_costos.drilldown_data;
        const chartDom = document.getElementById('descomposicion-costos-chart');
        
        if (chartDom && mainData.length > 0) {
            const chart = echarts.init(chartDom);
            
            const renderMain = () => {
                chart.setOption({
                    tooltip: { trigger: 'item', formatter: '{b}: ${c} ({d}%)' },
                    legend: { bottom: '0%', left: 'center' },
                    series: [{
                        name: 'Egresos',
                        type: 'pie',
                        radius: ['40%', '70%'],
                        avoidLabelOverlap: false,
                        itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
                        label: { show: false, position: 'center' },
                        emphasis: { label: { show: true, fontSize: '16', fontWeight: 'bold' } },
                        data: mainData
                    }],
                    graphic: null // Remove back button if exists
                }, true); // Merge = false (replace)
                
                // Click event for drilldown
                chart.off('click');
                chart.on('click', (params) => {
                    if (params.name === 'Costos Fijos' && drilldownData && drilldownData.length > 0) {
                        renderDrilldown();
                    }
                });
            };

            const renderDrilldown = () => {
                chart.setOption({
                    title: { 
                        text: 'Detalle Costos Fijos', 
                        left: 'center', 
                        top: 'middle',
                        textStyle: { fontSize: 14, color: '#6c757d' }
                    },
                    tooltip: { trigger: 'item', formatter: '{b}: ${c}' },
                    legend: { show: false },
                    series: [{
                        type: 'pie',
                        radius: ['0%', '0%'], // Hide main pie
                        data: [] 
                    }, {
                        name: 'Detalle Fijos',
                        type: 'bar',
                        data: drilldownData.map(d => d.value),
                        itemStyle: { color: '#dc3545' },
                        label: { show: true, position: 'right', formatter: '${c}' }
                    }],
                    xAxis: { type: 'value' },
                    yAxis: { type: 'category', data: drilldownData.map(d => d.name) },
                    grid: { left: '3%', right: '10%', bottom: '3%', top: '15%', containLabel: true },
                    // Back button
                    graphic: [{
                        type: 'group',
                        left: 10,
                        top: 10,
                        children: [{
                            type: 'rect',
                            z: 100,
                            left: 'center', top: 'middle',
                            shape: { width: 80, height: 25, r: 5 },
                            style: { fill: '#f8f9fa', stroke: '#dee2e6', lineWidth: 1 }
                        }, {
                            type: 'text',
                            z: 100,
                            left: 'center', top: 'middle',
                            style: { fill: '#333', text: '← Volver', font: '12px sans-serif' }
                        }],
                        onclick: renderMain
                    }]
                }, true);
            };

            renderMain();
            // Store instance for resizing
            window.chartInstances = window.chartInstances || {};
            window.chartInstances['descomposicion-costos-chart'] = chart;
        }
    }

    // 3. Ingresos vs Egresos
    if (data.ingresos_vs_egresos) {
        createChart('ingresos-vs-egresos-chart', {
            tooltip: { 
                trigger: 'axis',
                formatter: function (params) {
                    let res = params[0].name + '<br/>';
                    params.forEach(item => {
                        res += `${item.marker} ${item.seriesName}: $${item.value}<br/>`;
                    });
                    res += '<small class="text-muted"><i>*Egresos aprox.</i></small>';
                    return res;
                }
            },
            legend: { data: ['Ingresos', 'Egresos Básicos'], bottom: 0 },
            grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
            xAxis: { type: 'category', data: data.ingresos_vs_egresos.categories },
            yAxis: { type: 'value' },
            series: [
                {
                    name: 'Ingresos',
                    type: 'line',
                    data: data.ingresos_vs_egresos.series[0].data,
                    smooth: true,
                    connectNulls: true,
                    itemStyle: { color: '#198754' }
                },
                {
                    name: 'Egresos Básicos',
                    type: 'line',
                    data: data.ingresos_vs_egresos.series[1].data,
                    smooth: true,
                    connectNulls: true,
                    itemStyle: { color: '#dc3545' }
                }
            ]
        });
    }

    // 4. Evolución Costos Fijos
    if (data.evolucion_costos_fijos) {
        createChart('evolucion-costos-fijos-chart', {
            tooltip: { trigger: 'axis', formatter: '{b}: ${c}' },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            xAxis: { type: 'category', data: data.evolucion_costos_fijos.categories },
            yAxis: { type: 'value' },
            series: [{
                name: 'Costos Fijos',
                type: 'line',
                step: 'start',
                connectNulls: true,
                areaStyle: { opacity: 0.1 },
                itemStyle: { color: '#fd7e14' },
                data: data.evolucion_costos_fijos.values
            }]
        });
    }

    // 5. Matriz Rentabilidad (Scatter)
    if (data.bcg_matrix && data.bcg_matrix.productos) {
        const prods = data.bcg_matrix.productos;
        const avgs = data.bcg_matrix.promedios || { volumen_ventas: 0, margen_ganancia: 0 };
        
        // Scatter Data: [X=Ventas, Y=Margen]
        const scatterData = prods.map(p => {
            const isHighMargin = p.margen_porcentual >= avgs.margen_ganancia;
            return {
                name: p.nombre,
                value: [
                    p.facturacion_total,  // X: Ventas
                    p.margen_porcentual   // Y: Margen
                ],
                itemStyle: {
                    color: isHighMargin ? '#198754' : '#dc3545',
                    borderColor: '#fff',
                    borderWidth: 1
                }
            };
        });

        createChart('treemap-rentabilidad-chart', {
            tooltip: {
                formatter: function (params) {
                    if (params.componentType === 'markLine') return params.name;
                    return `<div class="mb-1 fw-bold small">${params.name}</div>
                            <div class="small">Ventas: $${params.value[0].toLocaleString()}</div>
                            <div class="small">Margen: ${params.value[1]}%</div>`;
                }
            },
            grid: { left: '8%', right: '10%', top: '10%', bottom: '10%', containLabel: true },
            xAxis: { 
                type: 'value', 
                name: 'Ventas ($)', 
                nameLocation: 'middle', 
                nameGap: 25,
                splitLine: { show: false },
                axisLabel: { formatter: (val) => `$${val >= 1000 ? (val/1000).toFixed(0)+'k' : val}` }
            },
            yAxis: { 
                type: 'value', 
                name: 'Margen (%)',
                splitLine: { show: false },
                axisLabel: { formatter: '{value}%' }
            },
            series: [{
                type: 'scatter',
                symbolSize: 30, // Tamaño fijo y visible
                data: scatterData,
                itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.2)' },
                markLine: {
                    silent: true,
                    symbol: 'none',
                    label: { position: 'end', formatter: '{b}' },
                    lineStyle: { type: 'dashed', color: '#6c757d', width: 1 },
                    data: [
                        { xAxis: avgs.volumen_ventas, name: 'Prom. Ventas' },
                        { yAxis: avgs.margen_ganancia, name: 'Prom. Margen' }
                    ]
                }
            }]
        });
    }
};