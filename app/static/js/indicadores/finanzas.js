const finanzasColors = ['#FAC858', '#EE6666', '#73C0DE', '#3BA272', '#FC8452'];

updateRentabilidadChart = () => {
    const chartDom = document.getElementById('rentabilidad-productos-chart');
    if (!chartDom) return;
    
    const chart = echarts.getInstanceByDom(chartDom) || echarts.init(chartDom);
    const downloadBtn = document.getElementById('download-rentabilidad-productos');
    const topNSelector = document.getElementById('top-n-selector');

    const fechaInicio = document.getElementById('fecha_inicio').value;
    const fechaFin = document.getElementById('fecha_fin').value;
    const topN = topNSelector.value;

    chart.showLoading();
    fetch(`/reportes/api/finanzas/rentabilidad_productos?fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}&top_n=${topN}`)
        .then(response => response.json())
        .then(data => {
            chart.hideLoading();
            if (data.error || data.labels.length === 0) {
                chart.setOption({ title: { text: 'No se encontraron datos', left: 'center', top: 'center' }, series: [] }, true);
                document.getElementById('rentabilidad-productos-descripcion').textContent = 'No hay datos de rentabilidad para mostrar.';
                return;
            }

            const option = {
                tooltip: { trigger: 'axis' },
                legend: { data: ['Ingresos', 'Costos', 'Rentabilidad Neta'] },
                xAxis: { type: 'category', data: data.labels, axisLabel: { interval: 0, rotate: 30 } },
                yAxis: { type: 'value', name: '$' },
                series: [
                    { name: 'Ingresos', type: 'bar', data: data.ingresos, itemStyle: { color: finanzasColors[2] } },
                    { name: 'Costos', type: 'bar', data: data.costos, itemStyle: { color: finanzasColors[1] } },
                    { name: 'Rentabilidad Neta', type: 'line', yAxisIndex: 0, data: data.rentabilidad_neta, smooth: true, itemStyle: { color: finanzasColors[3] } }
                ],
                grid: { containLabel: true }
            };
            chart.setOption(option, true);
            
            const descripcionEl = document.getElementById('rentabilidad-productos-descripcion');
            const masRentable = data.labels.reduce((prev, current, i) => (data.rentabilidad_neta[i] > data.rentabilidad_neta[data.labels.indexOf(prev)] ? current : prev));
            descripcionEl.textContent = `El producto más rentable del top es "${masRentable}".`;
        });

    if (topNSelector && !topNSelector.hasAttribute('data-initialized-finanzas')) {
        topNSelector.addEventListener('change', updateRentabilidadChart);
        topNSelector.setAttribute('data-initialized-finanzas', 'true');
    }
    if (downloadBtn && !downloadBtn.hasAttribute('data-initialized')) {
        downloadBtn.addEventListener('click', () => {
             const url = chart.getConnectedDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
             const a = document.createElement('a');
             a.href = url;
             a.download = 'rentabilidad_por_producto.png';
             a.click();
        });
        downloadBtn.setAttribute('data-initialized', 'true');
    }
};

updateCostoGananciaChart = () => {
    const chartDom = document.getElementById('costo-ganancia-chart');
    if(!chartDom) return;
    
    const chart = echarts.getInstanceByDom(chartDom) || echarts.init(chartDom);
    const periodoSelector = document.getElementById('periodo-costo-ganancia-selector');
    const downloadBtn = document.getElementById('download-costo-ganancia');
    
    const fechaInicio = document.getElementById('fecha_inicio').value;
    const fechaFin = document.getElementById('fecha_fin').value;
    const periodo = periodoSelector.value;
    
    chart.showLoading();
    fetch(`/reportes/api/finanzas/costo_vs_ganancia?fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}&periodo=${periodo}`)
        .then(response => response.json())
        .then(data => {
            chart.hideLoading();
            if (data.error || data.labels.length === 0) {
                chart.setOption({ title: { text: 'No se encontraron datos', left: 'center', top: 'center' }, series: [] }, true);
                document.getElementById('costo-ganancia-descripcion').textContent = "No hay datos suficientes para calcular el beneficio.";
                return;
            }

            const option = {
                tooltip: { trigger: 'axis' },
                legend: { data: ['Ingresos', 'Costos'] },
                xAxis: { type: 'category', data: data.labels },
                yAxis: { type: 'value', name: '$' },
                series: [
                    { name: 'Ingresos', type: 'line', data: data.ingresos, smooth: true, itemStyle: { color: finanzasColors[3] } },
                    { name: 'Costos', type: 'line', data: data.costos, smooth: true, itemStyle: { color: finanzasColors[1] } }
                ],
                grid: { containLabel: true }
            };
            chart.setOption(option, true);

            const descripcionEl = document.getElementById('costo-ganancia-descripcion');
            const totalIngresos = data.ingresos.reduce((a,b) => a+b, 0);
            const totalCostos = data.costos.reduce((a,b) => a+b, 0);
            const beneficioNeto = totalIngresos - totalCostos;
            descripcionEl.textContent = `Beneficio neto total del período: $${beneficioNeto.toFixed(2)}.`;
        });
    
    if (periodoSelector && !periodoSelector.hasAttribute('data-initialized')) {
        periodoSelector.addEventListener('change', updateCostoGananciaChart);
        periodoSelector.setAttribute('data-initialized', 'true');
    }
    if (downloadBtn && !downloadBtn.hasAttribute('data-initialized')) {
        downloadBtn.addEventListener('click', () => {
            const url = chart.getConnectedDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
            const a = document.createElement('a');
            a.href = url;
            a.download = 'costo_vs_ganancia.png';
            a.click();
        });
        downloadBtn.setAttribute('data-initialized', 'true');
    }
};

updateDescomposicionCostosChart = () => {
    const chartDom = document.getElementById('descomposicion-costos-chart');
    if(!chartDom) return;
    
    const chart = echarts.getInstanceByDom(chartDom) || echarts.init(chartDom);
    const downloadBtn = document.getElementById('download-descomposicion-costos');
    
    const fechaInicio = document.getElementById('fecha_inicio').value;
    const fechaFin = document.getElementById('fecha_fin').value;

    chart.showLoading();
    fetch(`/reportes/api/finanzas/descomposicion_costos?fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}`)
        .then(response => response.json())
        .then(data => {
            chart.hideLoading();
            if (data.error || data.data.reduce((a, b) => a + b, 0) === 0) {
                chart.setOption({ title: { text: 'No se encontraron datos', left: 'center', top: 'center' }, series: [] }, true);
                document.getElementById('descomposicion-costos-descripcion').textContent = 'No hay datos de costos para el período.';
                return;
            }
            
            const chartData = data.labels.map((label, i) => ({ name: label, value: data.data[i] }));

            const option = {
                tooltip: { trigger: 'item', formatter: '{b}: ${c} ({d}%)' },
                legend: { top: 'bottom' },
                series: [{
                    name: 'Descomposición de Costos', type: 'pie', radius: ['40%', '70%'], avoidLabelOverlap: false,
                    label: { show: false, position: 'center' },
                    emphasis: { label: { show: true, fontSize: '20', fontWeight: 'bold' } },
                    labelLine: { show: false },
                    data: chartData,
                    color: finanzasColors
                }],
            };
            chart.setOption(option, true);
            
            const descripcionEl = document.getElementById('descomposicion-costos-descripcion');
            const totalCostos = chartData.reduce((sum, item) => sum + item.value, 0);
            const costoPrincipal = chartData.reduce((max, item) => item.value > max.value ? item : max, chartData[0]);
            const porcentaje = ((costoPrincipal.value / totalCostos) * 100).toFixed(2);
            descripcionEl.textContent = `El principal costo operativo es "${costoPrincipal.name}", representando el ${porcentaje}% del total.`;
        });
        
    if (downloadBtn && !downloadBtn.hasAttribute('data-initialized')) {
        downloadBtn.addEventListener('click', () => {
             const url = chart.getConnectedDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
             const a = document.createElement('a');
             a.href = url;
             a.download = 'descomposicion_costos.png';
             a.click();
        });
        downloadBtn.setAttribute('data-initialized', 'true');
    }
};
