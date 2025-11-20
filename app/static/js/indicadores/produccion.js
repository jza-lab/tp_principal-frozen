// app/static/js/indicadores/produccion.js

/**
 * Renderiza el contenido de la pestaña de Producción.
 * Esta función es llamada desde indicadores_dashboard.js
 * @param {Object} data - Datos devueltos por la API de indicadores/produccion
 * @param {HTMLElement} container - Contenedor donde se inyectará el HTML
 */
window.renderProduccionTab = function(data, container) {
    // Defensive checks
    const topInsumos = data.top_insumos || { insight: 'N/A', tooltip: '', labels: [], data: [] };
    const velocidad = data.velocidad_produccion || { insight: 'N/A', tooltip: '', valor: 0 };
    const oeeData = data.oee || { disponibilidad: 0, rendimiento: 0, calidad: 0, valor: 0 };
    const cumplimiento = data.cumplimiento_plan || { valor: 0, completadas_a_tiempo: 0 };
    const panorama = data.panorama_estados || { insight: 'N/A', tooltip: '', states_data: [], lines_data: [] };
    const ranking = data.ranking_desperdicios || { insight: 'N/A', tooltip: '', categories: [], values: [] };
    const evolucion = data.evolucion_desperdicios || { insight: 'N/A', tooltip: '', categories: [], values: [] };

    // --- 1. Fila Superior: Visualización OEE y KPIs ---
    let content = `
    <div class="row g-3 mb-4">
        <!-- Left Column: OEE Gauge -->
        <div class="col-lg-5">
            <div class="card shadow-sm border-0 h-100">
                <div class="card-body position-relative p-2">
                    <h6 class="text-center text-muted fw-bold text-uppercase mt-2 mb-0">OEE Global</h6>
                    <div id="oee-gauge-chart" style="height: 250px;"></div>
                    <div class="text-center position-absolute w-100" style="bottom: 15px;">
                        <span class="badge bg-light text-dark border" data-bs-toggle="tooltip" title="Calculado como Disponibilidad × Rendimiento × Calidad">
                            <i class="bi bi-info-circle me-1"></i> Eficiencia General de los Equipos
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Right Column: 4 KPIs -->
        <div class="col-lg-7">
            <div class="row g-3 h-100 align-content-center">
                ${window.renderKpiCard('Disponibilidad', `${(oeeData.disponibilidad * 100).toFixed(1)}%`, 'Tiempo Operativo vs Planificado', 'bi-clock-history', 
                    '<b>Fórmula:</b> (Tiempo Operativo / Tiempo Planificado) <br>Mide las pérdidas por paradas no planificadas o averías.')}
                
                ${window.renderKpiCard('Rendimiento', `${(oeeData.rendimiento * 100).toFixed(1)}%`, 'Velocidad Real vs Teórica', 'bi-speedometer', 
                    '<b>Fórmula:</b> (Tiempo Ganado / Tiempo Operativo) <br>Mide si la máquina está produciendo a su velocidad máxima teórica.')}
                
                ${window.renderKpiCard('Calidad', `${(oeeData.calidad * 100).toFixed(1)}%`, 'Piezas Buenas vs Totales', 'bi-check-circle', 
                    '<b>Fórmula:</b> (Piezas Buenas / Piezas Totales) <br>Porcentaje de producción que cumple con los estándares de calidad (sin defectos).')}
                
                ${window.renderKpiCard('Cumplimiento Plan', `${cumplimiento.valor.toFixed(1)}%`, `${cumplimiento.completadas_a_tiempo} órdenes a tiempo`, 'bi-calendar-check', 
                    'Porcentaje de Órdenes de Producción que se completaron antes o en la fecha meta prometida.')}
            </div>
        </div>
    </div>
    
    <div class="d-flex align-items-center mb-4">
        <hr class="flex-grow-1">
        <span class="px-3 text-muted small text-uppercase fw-bold">Análisis Gráfico Detallado</span>
        <hr class="flex-grow-1">
    </div>

    <!-- 2. Fila Inferior: Gráficos Avanzados (Smart Cards) -->
    <div class="row g-3 mb-4 align-items-stretch">
        <!-- Gráfico 1: Panorama Estados (Dividido: Estados + Líneas) -->
        <div class="col-lg-6 col-xl-6">
            ${(function() {
                // Comprobar si existen datos para líneas
                const hasLinesData = panorama.lines_data && panorama.lines_data.length > 0 && panorama.lines_data.some(d => d.value > 0);
                
                if (hasLinesData) {
                    return window.createSplitSmartCardHTML(
                        'chart-panorama-states',
                        'chart-panorama-lines',
                        'Panorama General',
                        'Distribución actual de órdenes en producción y uso de líneas.',
                        panorama.insight, 
                        panorama.tooltip
                    );
                } else {
                    // Si no hay datos de líneas, mostrar solo Estados en tarjeta simple
                    return window.createSmartCardHTML(
                        'chart-panorama-states',
                        'Panorama General',
                        'Distribución actual de órdenes en producción.',
                        panorama.insight, 
                        panorama.tooltip
                    );
                }
            })()}
        </div>

        <!-- Gráfico 2: Top Insumos (NUEVO) -->
        <div class="col-lg-6 col-xl-6">
             <!-- Custom Smart Card con Selector -->
            <div class="card shadow-sm border-0 h-100 smart-card-container">
                <div class="card-header bg-white d-flex justify-content-between align-items-center py-3 border-0 pb-0">
                    <div class="d-flex align-items-center gap-2">
                        <h6 class="fw-bold text-dark mb-0" style="font-size: 1rem;">Top Insumos Utilizados</h6>
                        <select class="form-select form-select-sm py-0 px-2" style="width: auto; height: 24px; font-size: 0.75rem;" onchange="window.updateCategoryParam('produccion', 'top_n', this.value)">
                            <option value="5" ${data.meta?.top_n == 5 ? 'selected' : ''}>Top 5</option>
                            <option value="10" ${!data.meta?.top_n || data.meta?.top_n == 10 ? 'selected' : ''}>Top 10</option>
                            <option value="20" ${data.meta?.top_n == 20 ? 'selected' : ''}>Top 20</option>
                        </select>
                    </div>
                    <i class="bi bi-question-circle-fill text-muted opacity-50" 
                       data-bs-toggle="tooltip" 
                       data-bs-placement="left" 
                       title="${topInsumos.tooltip}" 
                       style="cursor: help; font-size: 0.9rem;"></i>
                </div>
                <div class="card-body p-3 d-flex flex-column h-100 pt-0">
                    <p class="text-muted small mb-3 mt-2" style="font-size: 0.8rem;">Insumos con mayor cantidad reservada para producción.</p>
                    
                    <div class="flex-grow-1 position-relative" style="min-height: 250px;">
                        <div id="chart-top-insumos" style="width: 100%; height: 100%; position: absolute; top: 0; left: 0;"></div>
                    </div>

                    <div class="alert alert-light border-start border-4 border-primary bg-light shadow-sm mb-0 mt-3 py-2 px-3">
                        <div class="d-flex align-items-center">
                            <i class="bi bi-lightbulb-fill text-primary me-2"></i>
                            <span class="text-dark small fw-medium dynamic-insight">${topInsumos.insight}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Gráfico 3: Ranking Desperdicios -->
        <div class="col-lg-6 col-xl-6">
            ${window.createSmartCardHTML(
                'chart-ranking-desperdicios', 
                'Ranking Desperdicios', 
                'Principales motivos de pérdida de material.',
                ranking.insight, 
                ranking.tooltip
            )}
        </div>

        <!-- Gráfico 4: Evolución Desperdicios -->
        <div class="col-lg-6 col-xl-6">
            ${window.createSmartCardHTML(
                'chart-evolucion-desperdicios', 
                'Evolución Desperdicios', 
                'Tendencia histórica de incidentes reportados.',
                evolucion.insight, 
                evolucion.tooltip
            )}
        </div>

        <!-- Gráfico 5: Velocidad Producción (ACTUALIZADO) -->
        <div class="col-lg-6 col-xl-6">
            ${window.createSmartCardHTML(
                'chart-velocidad', 
                'Tiempo Promedio de Ciclo', 
                'Tiempo promedio desde inicio real hasta finalización de orden.',
                velocidad.insight, 
                velocidad.tooltip
            )}
        </div>
    </div>`;
    
    container.innerHTML = content;

    // --- RENDERING CHARTS ---

    // --- CHART 0: OEE GAUGE ---
    const oeeVal = oeeData.valor.toFixed(1);
    const colorPalo = [[0.65, '#dc3545'], [0.85, '#ffc107'], [1, '#198754']];

    window.createChart('oee-gauge-chart', {
        series: [{
            type: 'gauge',
            startAngle: 180,
            endAngle: 0,
            min: 0,
            max: 100,
            splitNumber: 5,
            radius: '90%',
            itemStyle: { color: '#58D9F9' },
            progress: { show: true, width: 18 },
            pointer: { icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z', length: '12%', width: 10, offsetCenter: [0, '-60%'], itemStyle: { color: 'auto' } },
            axisLine: { lineStyle: { width: 18, color: colorPalo } },
            axisTick: { distance: -18, length: 8, lineStyle: { color: '#fff', width: 2 } },
            splitLine: { distance: -18, length: 30, lineStyle: { color: '#fff', width: 3 } },
            axisLabel: { color: 'auto', distance: 20, fontSize: 12 },
            detail: { valueAnimation: true, formatter: '{value}%', color: 'auto', fontSize: 30, offsetCenter: [0, '20%'] },
            data: [{ value: oeeVal }]
        }]
    });

    // --- CHART 1A: PANORAMA ESTADOS ---
    window.createChart('chart-panorama-states', {
        tooltip: { trigger: 'item' },
        legend: { bottom: 0, left: 'center', itemWidth: 8, itemHeight: 8, textStyle: {fontSize: 10}, type: 'scroll' },
        series: [{
            name: 'Estados',
            type: 'pie',
            radius: ['40%', '60%'],
            center: ['50%', '40%'],
            avoidLabelOverlap: false,
            itemStyle: { borderRadius: 5, borderColor: '#fff', borderWidth: 2 },
            label: { show: false, position: 'center' },
            emphasis: { label: { show: true, fontSize: '10', fontWeight: 'bold' } },
            labelLine: { show: false },
            data: panorama.states_data
        }]
    });

    // --- CHART 1B: PANORAMA LÍNEAS ---
    // Solo intentar renderizar si el contenedor existe (es decir, si se usó createSplitSmartCardHTML)
    if (document.getElementById('chart-panorama-lines')) {
        window.createChart('chart-panorama-lines', {
            tooltip: { trigger: 'item' },
            legend: { bottom: 0, left: 'center', itemWidth: 8, itemHeight: 8, textStyle: {fontSize: 10} },
            series: [{
                name: 'Línea',
                type: 'pie',
                radius: ['40%', '60%'],
                center: ['50%', '40%'],
                itemStyle: { borderRadius: 5, borderColor: '#fff', borderWidth: 2 },
                label: { show: false },
                data: panorama.lines_data
            }]
        });
    }

    // --- CHART 2: TOP INSUMOS (NUEVO) ---
    window.createChart('chart-top-insumos', {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: '3%', right: '10%', bottom: '3%', top: '5%', containLabel: true },
        xAxis: { type: 'value', boundaryGap: [0, 0.01] },
        yAxis: { 
            type: 'category', 
            data: topInsumos.labels.slice().reverse(),
            axisLabel: { interval: 0, width: 80, overflow: 'truncate' }
        },
        series: [{
            name: 'Cantidad',
            type: 'bar',
            data: topInsumos.data.slice().reverse(),
            itemStyle: { color: '#36b9cc', borderRadius: [0, 4, 4, 0] },
            label: { show: true, position: 'right' }
        }]
    });

    // --- CHART 3: RANKING DESPERDICIOS ---
    const desperdiciosType = ranking.chart_type || 'bar';
    let desperdiciosOption = {};

    if (desperdiciosType === 'pie') {
         const pieData = ranking.categories.map((cat, idx) => ({
             name: cat,
             value: ranking.values[idx]
         }));

         desperdiciosOption = {
            tooltip: { trigger: 'item' },
            legend: { bottom: 0, left: 'center', itemWidth: 8, itemHeight: 8, textStyle: {fontSize: 10} },
            series: [{
                name: 'Motivos',
                type: 'pie',
                radius: '60%',
                center: ['50%', '45%'],
                data: pieData,
                itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 1 },
                emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } }
            }]
         };
    } else {
        desperdiciosOption = {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            grid: { left: '3%', right: '10%', bottom: '3%', top: '5%', containLabel: true },
            xAxis: { type: 'value', show: false }, 
            yAxis: { 
                type: 'category', 
                data: ranking.categories,
                axisTick: { show: false },
                axisLine: { show: false },
                axisLabel: { width: 100, overflow: 'truncate' } 
            },
            series: [{
                name: 'Frecuencia',
                type: 'bar',
                data: ranking.values,
                itemStyle: { color: '#dc3545', borderRadius: [0, 4, 4, 0] },
                label: { show: true, position: 'right' }
            }]
        };
    }
    window.createChart('chart-ranking-desperdicios', desperdiciosOption);


    // --- CHART 4: EVOLUCIÓN DESPERDICIOS ---
    window.createChart('chart-evolucion-desperdicios', {
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
        xAxis: { type: 'category', boundaryGap: false, data: evolucion.categories },
        yAxis: { type: 'value' },
        series: [{
            name: 'Incidentes',
            type: 'line',
            smooth: true,
            data: evolucion.values,
            areaStyle: { opacity: 0.1, color: '#fd7e14' },
            itemStyle: { color: '#fd7e14' },
            lineStyle: { width: 3 }
        }]
    });

    // --- CHART 5: VELOCIDAD PRODUCCIÓN (GAUGE SIMPLE) - Usando datos nuevos ---
    const velocidadVal = velocidad.valor;
    // Escala dinámica: si el valor es mayor a 24h, ajustamos el máximo
    const gaugeMax = Math.max(Math.ceil(velocidadVal * 1.25), 24);
    
    window.createChart('chart-velocidad', {
        series: [{
            type: 'gauge',
            startAngle: 180,
            endAngle: 0,
            min: 0,
            max: gaugeMax,
            splitNumber: 6,
            radius: '100%',
            center: ['50%', '70%'],
            itemStyle: { color: '#0d6efd' },
            progress: { show: true, width: 15 },
            pointer: { show: false },
            axisLine: { lineStyle: { width: 15 } },
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { show: false },
            title: { show: true, offsetCenter: [0, '-20%'], fontSize: 12, color: '#888' },
            detail: { 
                valueAnimation: true, 
                formatter: '{value} h', 
                offsetCenter: [0, '0%'], 
                fontSize: 24,
                fontWeight: 'bold',
                color: '#333'
            },
            data: [{ value: velocidadVal, name: 'Ciclo Promedio' }]
        }]
    });
}
