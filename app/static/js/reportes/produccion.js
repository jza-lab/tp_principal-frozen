document.addEventListener('DOMContentLoaded', function () {
    const bluePalette = ['#003f5c', '#374c80', '#7a5195', '#bc5090', '#ffa600', '#007bff', '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e'];
    let charts = {};
    let isTab2Loaded = false; // Flag to track if Tab 2 data has been loaded

    const reportContainer = document.getElementById('report-container');
    const noDataMessage = document.getElementById('no-data-message');
    const downloadButton = document.getElementById('download-pdf');

    // --- Tab Handling ---
    const tabEl = document.querySelector('a[data-bs-toggle="tab"][data-bs-target="#materia-prima"], button[data-bs-toggle="tab"][data-bs-target="#materia-prima"]');
    
    // Listener for Tab Switching to Lazy Load Data
    if(tabEl) {
        tabEl.addEventListener('shown.bs.tab', function (event) {
            if (!isTab2Loaded) {
                loadTab2Data();
                isTab2Loaded = true;
            }
        });
    }

    // Global resize listener for all charts
    $('a[data-bs-toggle="tab"], button[data-bs-toggle="tab"]').on('shown.bs.tab', function (e) {
        Object.values(charts).forEach(chartObj => {
            if (chartObj.chart) {
                chartObj.chart.resize();
            }
        });
    });

    window.addEventListener('resize', function() {
        Object.values(charts).forEach(chartObj => {
            if (chartObj.chart) {
                chartObj.chart.resize();
            }
        });
    });

    function updateDescription(elementId, text) {
        const el = document.getElementById(elementId);
        if (el) {
            el.innerHTML = text;
        }
    }

    // --- Data Loading Functions ---

    function loadTab1Data() {
        const apiEndpoints = [
            { key: 'ordenes', url: '/reportes/api/produccion/ordenes_por_estado' },
            { key: 'composicion', url: '/reportes/api/produccion/composicion_produccion' },
            { key: 'tiempoCiclo', url: '/reportes/api/produccion/tiempo_ciclo_promedio' },
            { key: 'produccionTiempo', url: '/reportes/api/produccion/produccion_por_tiempo' }
        ];

        Promise.all(apiEndpoints.map(ep => fetch(ep.url).then(res => res.json())))
            .then(results => {
                const dataMap = results.reduce((map, result, index) => {
                    map[apiEndpoints[index].key] = result.data || {};
                    return map;
                }, {});

                // Handle "No Data" Message (Driven by Tab 1 main data)
                const hasData = Object.values(dataMap).some(data => Object.keys(data).length > 0);

                if(reportContainer) reportContainer.style.display = 'block';
                if(noDataMessage) noDataMessage.style.display = 'none';
                if(downloadButton) downloadButton.disabled = false;

                // If absolutely empty, maybe show message, but user asked to avoid crashes, so we prefer showing empty containers over hiding UI.
                if (!hasData) {
                     // Optional: show specific message per card instead of global hide
                }

                renderOrdenesChart(dataMap.ordenes);
                renderComposicionChart(dataMap.composicion);
                renderTiempoCiclo(dataMap.tiempoCiclo);
                renderProduccionTiempoChart(dataMap.produccionTiempo);

            }).catch(error => {
                console.error("Error fetching Tab 1 data:", error);
            });
    }

    function loadTab2Data() {
        // These are independent requests
        loadTopInsumosChart();
        loadEficienciaConsumoChart();
        loadCostosProduccionChart(); 
    }

    // --- Initial Load ---
    loadTab1Data();


    // --- Chart Renderers (Unchanged Logic) ---

    function renderOrdenesChart(data) {
        const container = document.getElementById('ordenes-por-estado-chart');
        if (!container) return;
        if (!data || Object.keys(data).length === 0) {
            updateDescription('ordenes-por-estado-description', 'No hay datos de órdenes para mostrar.');
            return;
        }
        const chart = echarts.init(container);
        charts['ordenes'] = {chart: chart, title: 'Órdenes por Estado'};
        const chartData = Object.entries(data).map(([name, value]) => ({ name, value }));
        const totalOrders = chartData.reduce((sum, item) => sum + item.value, 0);
        const mostFrequent = chartData.reduce((max, item) => item.value > max.value ? item : max, chartData[0]);
        const percentage = ((mostFrequent.value / totalOrders) * 100).toFixed(1);
        const description = `Actualmente, el estado más común es <strong>${mostFrequent.name}</strong>, con ${mostFrequent.value} de ${totalOrders} órdenes (${percentage}% del total).`;
        updateDescription('ordenes-por-estado-description', description);
        charts['ordenes'].description = description.replace(/<strong>/g, '').replace(/<\/strong>/g, '');
        const option = {
            tooltip: { trigger: 'item' },
            legend: { bottom: 10, left: 'center', type: 'scroll' },
            series: [{ name: 'Órdenes', type: 'pie', radius: ['50%', '70%'], center: ['50%', '40%'], avoidLabelOverlap: false, label: { show: false }, emphasis: { label: { show: true, fontSize: '20', fontWeight: 'bold', formatter: '{b}\n{c}' } }, labelLine: { show: false }, data: chartData }],
            color: bluePalette
        };
        chart.setOption(option);
    }

    function renderComposicionChart(data) {
        const container = document.getElementById('composicion-produccion-chart');
        if (!container) return;
        if (!data || Object.keys(data).length === 0) {
            updateDescription('composicion-produccion-description', 'No hay datos de producción para mostrar.');
            return;
        }
        const chart = echarts.init(container);
        charts['composicion'] = {chart: chart, title: 'Composición de la Producción'};
        const chartData = Object.entries(data).map(([name, value]) => ({ name, value }));
        const totalQuantity = chartData.reduce((sum, item) => sum + item.value, 0);
        const topProduct = chartData.reduce((max, item) => item.value > max.value ? item : max, chartData[0]);
        const description = `Se planifica producir un total de <strong>${totalQuantity.toLocaleString('es-AR')} unidades</strong>. El producto con mayor demanda es <strong>${topProduct.name}</strong>.`;
        updateDescription('composicion-produccion-description', description);
        charts['composicion'].description = description.replace(/<strong>/g, '').replace(/<\/strong>/g, '');
        const option = {
            tooltip: { trigger: 'item' },
            legend: { bottom: 10, left: 'center', type: 'scroll' },
            series: [{ name: 'Cantidad', type: 'pie', radius: '50%', center: ['50%', '40%'], data: chartData, emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } } }],
            color: bluePalette.slice(2)
        };
        chart.setOption(option);
    }

    function renderTiempoCiclo(data) {
        if (!data || Object.keys(data).length === 0) {
            updateDescription('tiempo-ciclo-description', 'No hay suficientes órdenes completadas para calcular un promedio.');
            return;
        }
        const { dias, horas, minutos } = data;
        document.getElementById('tiempo-ciclo-promedio').textContent = `${dias}d ${horas}h ${minutos}m`;
        const description = `Este es el tiempo promedio que transcurre desde que una orden de producción inicia hasta que se marca como completada.`;
        updateDescription('tiempo-ciclo-description', description);
    }

    function renderProduccionTiempoChart(data) {
        const container = document.getElementById('produccion-por-tiempo-chart');
        if (!container) return;
        if (!data || Object.keys(data).length === 0) {
            updateDescription('produccion-por-tiempo-description', 'No hay datos de producción histórica para mostrar.');
            return;
        }
        const chart = echarts.init(container);
        charts['produccionTiempo'] = {chart: chart, title: 'Producción a lo largo del tiempo'};
        const timePeriods = Object.keys(data).length;
        const totalCompleted = Object.values(data).reduce((sum, val) => sum + val, 0);
        const average = (totalCompleted / timePeriods).toFixed(1);
        const description = `Se han completado un total de <strong>${totalCompleted}</strong> órdenes en los últimos <strong>${timePeriods}</strong> periodos, con un promedio de <strong>${average}</strong> órdenes por semana.`;
        updateDescription('produccion-por-tiempo-description', description);
        charts['produccionTiempo'].description = description.replace(/<strong>/g, '').replace(/<\/strong>/g, '');
        const option = {
            tooltip: { trigger: 'axis' },
            grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
            xAxis: { type: 'category', data: Object.keys(data) },
            yAxis: { type: 'value' },
            series: [{ data: Object.values(data), type: 'line', smooth: true, areaStyle: {} }],
            color: bluePalette[4]
        };
        chart.setOption(option);
    }

    // --- Costos Chart Logic ---
    const costosPeriodoSelect = document.getElementById('costos-periodo-select');
    if (costosPeriodoSelect) {
        costosPeriodoSelect.addEventListener('change', (event) => {
            loadCostosProduccionChart(event.target.value);
        });
    }

    function loadCostosProduccionChart(periodo = 'semanal') {
        const container = document.getElementById('costos-produccion-chart');
        if (!container) return;

        const chart = echarts.getInstanceByDom(container) || echarts.init(container);
        charts['costosProduccion'] = {chart: chart, title: 'Costos de Producción: Plan vs Real'};
        chart.showLoading();

        fetch(`/reportes/api/produccion/costos_plan_vs_real?periodo=${periodo}`)
            .then(res => res.json())
            .then(result => {
                chart.hideLoading();
                const data = result.data;
                
                if (!result.success || !data || !data.labels || data.labels.length === 0) {
                    updateDescription('costos-produccion-description', 'No hay datos de costos disponibles para el periodo seleccionado.');
                    chart.clear();
                    return;
                }

                // Calcular total desperdicio
                const totalReal = data.real.reduce((a, b) => a + b, 0);
                const totalPlan = data.planificado.reduce((a, b) => a + b, 0);
                const desperdicioTotal = totalReal - totalPlan;
                const pctDesperdicio = totalPlan > 0 ? ((desperdicioTotal / totalPlan) * 100).toFixed(1) : 0;

                const description = `El costo real acumulado es de <strong>$${totalReal.toLocaleString('es-AR')}</strong>, con un sobrecosto por desperdicios de <strong>$${desperdicioTotal.toLocaleString('es-AR')}</strong> (${pctDesperdicio}%).`;
                updateDescription('costos-produccion-description', description);
                charts['costosProduccion'].description = description.replace(/<strong>/g, '').replace(/<\/strong>/g, '');

                const option = {
                    tooltip: {
                        trigger: 'axis',
                        axisPointer: { type: 'shadow' },
                        formatter: function(params) {
                            let tooltip = `<strong>${params[0].axisValue}</strong><br/>`;
                            params.forEach(param => {
                                tooltip += `${param.marker} ${param.seriesName}: $${param.value.toLocaleString('es-AR')}<br/>`;
                            });
                            if (params.length >= 2) {
                                const diff = params[1].value - params[0].value;
                                if (diff > 0) {
                                    tooltip += `<span style="color: #e74a3b; font-weight: bold;">Sobrecosto: $${diff.toLocaleString('es-AR')}</span>`;
                                }
                            }
                            return tooltip;
                        }
                    },
                    legend: { data: ['Costo Planificado', 'Costo Real'], bottom: 0 },
                    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
                    xAxis: { type: 'category', data: data.labels },
                    yAxis: { type: 'value', axisLabel: { formatter: '${value}' } },
                    series: [
                        {
                            name: 'Costo Planificado',
                            type: 'bar',
                            data: data.planificado,
                            itemStyle: { color: '#858796' },
                            barGap: '-100%'
                        },
                        {
                            name: 'Costo Real',
                            type: 'bar',
                            data: data.real,
                            itemStyle: { 
                                color: '#4e73df',
                                opacity: 0.7
                            }
                        }
                    ]
                };
                chart.setOption(option, true);
            })
            .catch(err => {
                chart.hideLoading();
                console.error(err);
                updateDescription('costos-produccion-description', 'Error al cargar los datos de costos.');
            });
    }

    const topNSelect = document.getElementById('top-n-select');
    if (topNSelect) {
        topNSelect.addEventListener('change', (event) => {
            loadTopInsumosChart(event.target.value);
        });
    }

    function loadTopInsumosChart(topN = 5) {
        const container = document.getElementById('top-insumos-chart');
        if (!container) return;
        
        const chart = echarts.getInstanceByDom(container) || echarts.init(container);
        charts['topInsumos'] = {chart: chart, title: `Top ${topN} Insumos Utilizados`};

        fetch(`/reportes/api/produccion/top_insumos?top_n=${topN}`)
            .then(response => response.json())
            .then(result => {
                if (result.success && Object.keys(result.data).length > 0) {
                    const data = Object.entries(result.data).map(([name, value]) => ({ name, value }));
                    // Ordenar descendente
                    data.sort((a, b) => b.value - a.value);
                    
                    const topInsumo = data[0];
                    const description = `El insumo más utilizado es <strong>${topInsumo.name}</strong>, con un consumo total de <strong>${topInsumo.value.toLocaleString('es-AR')} unidades</strong>.`;
                    updateDescription('top-insumos-description', description);
                    charts['topInsumos'].description = description.replace(/<strong>/g, '').replace(/<\/strong>/g, '');

                    const option = {
                        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                        grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
                        xAxis: { type: 'value', boundaryGap: [0, 0.01] },
                        yAxis: { type: 'category', data: data.map(item => item.name).reverse() },
                        series: [{ name: 'Cantidad Utilizada', type: 'bar', data: data.map(item => item.value).reverse() }],
                        color: bluePalette[1]
                    };
                    chart.setOption(option, true);
                } else {
                    updateDescription('top-insumos-description', 'No hay datos de consumo de insumos para mostrar.');
                }
            });
    }

    // --- Eficiencia de Consumo Chart Logic ---
    const productoFilterSelect = document.getElementById('producto-filter-select');
    if (productoFilterSelect) {
        productoFilterSelect.addEventListener('change', (event) => {
            loadEficienciaConsumoChart(15, event.target.value);
        });
    }

    function loadEficienciaConsumoChart(topN = 15, producto = '') {
        const container = document.getElementById('eficiencia-consumo-chart');
        const narrativeContainer = document.getElementById('eficiencia-consumo-narrative');
        if (!container) return;

        const chart = echarts.getInstanceByDom(container) || echarts.init(container);
        charts['eficienciaConsumo'] = {chart: chart, title: 'Eficiencia de Consumo (Plan vs Real)'};
        
        chart.showLoading();

        // Construir URL con params
        let url = `/reportes/api/produccion/eficiencia_consumo?top_n=${topN}`;
        if (producto) {
            url += `&producto=${encodeURIComponent(producto)}`;
        }

        fetch(url)
            .then(response => response.json())
            .then(result => {
                chart.hideLoading();
                if (result.success && result.data.chart && result.data.chart.length > 0) {
                    const data = result.data.chart;
                    const narrative = result.data.narrative;
                    const products = result.data.products;

                    // Poblar el dropdown de productos solo si está vacío (primera carga)
                    // O mantenerlo si ya tiene datos. 
                    if (productoFilterSelect && productoFilterSelect.options.length <= 1) {
                         products.forEach(prod => {
                             const option = document.createElement('option');
                             option.value = prod;
                             option.textContent = prod;
                             productoFilterSelect.appendChild(option);
                         });
                    }

                    // Actualizar narrativa
                    if (narrativeContainer) {
                        narrativeContainer.innerHTML = narrative;
                    }

                    // Preparar datos para ECharts
                    // Eje Y: Insumos (usar nombre 'Producto - Insumo' si no hay filtro de producto para claridad)
                    const categories = data.map(item => producto ? item.insumo : `${item.insumo} (${item.producto})`);
                    const plannedData = data.map(item => item.planificado);
                    const realData = data.map(item => item.real);
                    
                    // Colores para puntos reales: Rojo si Real > Planificado, Verde si Real <= Planificado
                    const realPointColors = data.map(item => item.real > item.planificado ? '#e74a3b' : '#1cc88a');

                    const option = {
                        tooltip: {
                            trigger: 'axis',
                            axisPointer: { type: 'shadow' },
                            formatter: function (params) {
                                const index = params[0].dataIndex;
                                const item = data[index];
                                const diff = item.real - item.planificado;
                                const diffSign = diff > 0 ? '+' : '';
                                const diffColor = diff > 0 ? 'red' : 'green';
                                
                                return `
                                    <strong>${item.insumo}</strong><br/>
                                    Producto: ${item.producto}<br/>
                                    Planificado: ${item.planificado.toLocaleString('es-AR')}<br/>
                                    Real: ${item.real.toLocaleString('es-AR')}<br/>
                                    Desviación: <span style="color:${diffColor}">${diffSign}${item.desviacion}%</span>
                                `;
                            }
                        },
                        legend: { data: ['Planificado', 'Real'] },
                        grid: { left: '3%', right: '4%', bottom: '8%', containLabel: true }, // Aumentar bottom para etiquetas X
                        xAxis: { 
                            type: 'value', 
                            name: 'Cantidad',
                            nameLocation: 'middle',
                            nameGap: 25,
                            scale: true // Para que el zoom funcione mejor
                        },
                        yAxis: { 
                            type: 'category', 
                            data: categories,
                            name: 'Insumo',
                            nameLocation: 'end'
                        },
                        dataZoom: [
                            { type: 'inside', xAxisIndex: 0 },
                            { type: 'slider', xAxisIndex: 0 }
                        ],
                        series: [
                            {
                                name: 'Línea Conectora',
                                type: 'custom',
                                renderItem: function (params, api) {
                                    const yValue = api.value(1); // índice de categoría
                                    const start = api.coord([plannedData[params.dataIndex], yValue]);
                                    const end = api.coord([realData[params.dataIndex], yValue]);
                                    const style = api.style({
                                        stroke: '#555',
                                        lineWidth: 2
                                    });
                                    return {
                                        type: 'line',
                                        shape: { x1: start[0], y1: start[1], x2: end[0], y2: end[1] },
                                        style: style
                                    };
                                },
                                data: data.map((item, idx) => [item.planificado, idx]) // Dummy data to trigger render
                            },
                            {
                                name: 'Planificado',
                                type: 'scatter',
                                itemStyle: { color: '#858796' }, // Gris
                                symbolSize: 10,
                                label: {
                                    show: false, // Ocultar etiqueta en planificado para no saturar
                                },
                                data: plannedData
                            },
                            {
                                name: 'Real',
                                type: 'scatter',
                                symbolSize: 12,
                                itemStyle: {
                                    color: function(params) {
                                        return realPointColors[params.dataIndex];
                                    }
                                },
                                label: {
                                    show: true,
                                    position: 'right',
                                    formatter: function(params) {
                                        // Mostrar porcentaje solo si es relevante (> 0.1% o < -0.1%)
                                        const val = data[params.dataIndex].desviacion;
                                        if (Math.abs(val) < 0.1) return '';
                                        return `${val}%`;
                                    },
                                    color: '#000',
                                    fontWeight: 'bold'
                                },
                                data: realData
                            }
                        ]
                    };
                    chart.setOption(option, true);

                } else {
                    chart.hideLoading();
                    updateDescription('eficiencia-consumo-narrative', 'No hay datos suficientes para mostrar el análisis de eficiencia.');
                    // Limpiar gráfico
                    chart.clear();
                }
            })
            .catch(err => {
                chart.hideLoading();
                console.error(err);
                updateDescription('eficiencia-consumo-narrative', 'Error al cargar los datos.');
            });
    }

    // PDF Generation Update
    if(downloadButton){
        const newDownloadButton = downloadButton.cloneNode(true);
        downloadButton.parentNode.replaceChild(newDownloadButton, downloadButton);

        newDownloadButton.addEventListener('click', async function (e) {
            e.preventDefault();
            e.stopImmediatePropagation();
            
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generando...';
            
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF('p', 'mm', 'a4');
            const pdfWidth = pdf.internal.pageSize.getWidth();
            const pdfHeight = pdf.internal.pageSize.getHeight();
            const margin = 15;
            let yPos = 0;
            let page = 1;

            async function getImageBase64(url) {
                const response = await fetch(url);
                const blob = await response.blob();
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
            }

            try {
                const logoBase64 = await getImageBase64('/static/img/icon.png');

                function addHeader() {
                    if (logoBase64) {
                        pdf.addImage(logoBase64, 'PNG', margin, 10, 10, 10);
                    }
                    pdf.setFontSize(18);
                    pdf.setFont('helvetica', 'bold');
                    pdf.text('FrozenProd Inc.', margin + 12, 18);
                    pdf.setFontSize(14);
                    pdf.setFont('helvetica', 'normal');
                    pdf.text('Reporte de Producción', pdfWidth - margin, 18, { align: 'right' });
                    pdf.setDrawColor(0);
                    pdf.line(margin, 25, pdfWidth - margin, 25);
                    yPos = 35;
                }

                function addFooter() {
                    const pageStr = `Página ${page}`;
                    pdf.setFontSize(9);
                    pdf.text(pageStr, pdfWidth / 2, pdfHeight - 10, { align: 'center' });
                }

                addHeader();
                addFooter();

                // Orden de exportación incluyendo los nuevos gráficos
                const chartKeys = ['ordenes', 'composicion', 'produccionTiempo', 'topInsumos', 'eficienciaConsumo', 'costosProduccion'];

                for (const key of chartKeys) {
                    const chartObj = charts[key];
                    if (chartObj && chartObj.chart) {
                        
                        // Verificar si el título existe
                        const title = chartObj.title || 'Gráfico';
                        
                        const chartHeight = 80;
                        const contentHeight = chartHeight + 30;

                        if (yPos + contentHeight > pdfHeight - margin) {
                            pdf.addPage();
                            page++;
                            addHeader();
                            addFooter();
                            yPos = 35;
                        }

                        pdf.setFontSize(14);
                        pdf.setFont('helvetica', 'bold');
                        pdf.text(title, margin, yPos);
                        
                        pdf.setFontSize(10);
                        pdf.setFont('helvetica', 'normal');
                        
                        // Descripción
                        let desc = chartObj.description || '';
                        if (key === 'eficienciaConsumo') {
                            const narDiv = document.getElementById('eficiencia-consumo-narrative');
                            if(narDiv) desc = narDiv.innerText;
                        }
                        if (key === 'costosProduccion') {
                            const narDiv = document.getElementById('costos-produccion-description');
                            if(narDiv) desc = narDiv.innerText;
                        }

                        const splitDescription = pdf.splitTextToSize(desc, pdfWidth - (margin * 2));
                        pdf.text(splitDescription, margin, yPos + 7);
                        
                        // Captura de imagen
                        let imgData = '';
                        try {
                             imgData = chartObj.chart.getDataURL({
                                pixelRatio: 2,
                                backgroundColor: '#fff',
                                excludeComponents: ['toolbox']
                            });
                        } catch(e) {
                            console.warn(`No se pudo capturar gráfico ${key}:`, e);
                            continue; 
                        }
                        
                        if(imgData) {
                            const imgProps = pdf.getImageProperties(imgData);
                            const aspectRatio = imgProps.height / imgProps.width;
                            const finalWidth = pdfWidth - (margin * 2);
                            const finalHeight = finalWidth * aspectRatio;
                            
                            // Ajustar altura si es muy grande
                            const effectiveHeight = Math.min(finalHeight, 100); 

                            pdf.addImage(imgData, 'PNG', margin, yPos + 20, finalWidth, effectiveHeight);
                            yPos += effectiveHeight + 30;
                        }
                    }
                }
                
                pdf.save('reporte_produccion_frozenprod.pdf');

            } catch (error) {
                console.error("Error al generar el PDF:", error);
                alert("Hubo un error al generar el PDF. Asegúrese de visualizar ambas pestañas antes de generar.");
            } finally {
                this.disabled = false;
                this.innerHTML = '<i class="fas fa-download fa-sm text-white-50"></i> Generar Reporte';
            }
        });
    }
});
