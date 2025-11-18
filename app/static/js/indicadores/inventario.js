const inventarioColors = ['#73C0DE', '#3BA272', '#FC8452', '#9A60B4'];

updateAntiguedadInsumosChart = () => {
    const chartDom = document.getElementById('antiguedad-insumos-chart');
    if (!chartDom) return;
    
    const chart = echarts.getInstanceByDom(chartDom) || echarts.init(chartDom);
    const downloadBtn = document.getElementById('download-antiguedad-insumos');

    chart.showLoading();
    fetch(`/reportes/api/inventario/antiguedad_stock?tipo=insumo`)
        .then(response => response.json())
        .then(data => {
            chart.hideLoading();
            if (data.error || data.data.reduce((a, b) => a + b, 0) === 0) {
                chart.setOption({ title: { text: 'No se encontraron datos', left: 'center', top: 'center' }, series: [] }, true);
                document.getElementById('antiguedad-insumos-descripcion').textContent = 'No hay datos de stock de insumos.';
                return;
            }

            const option = {
                tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                xAxis: { type: 'category', data: data.labels },
                yAxis: { type: 'value', name: 'Valor ($)' },
                series: [{
                    name: 'Valor de Stock', type: 'bar', data: data.data,
                    itemStyle: { color: (params) => inventarioColors[params.dataIndex] }
                }],
                grid: { containLabel: true }
            };
            chart.setOption(option, true);

            const descripcionEl = document.getElementById('antiguedad-insumos-descripcion');
            const totalValor = data.data.reduce((a, b) => a + b, 0);
            const valorMas90 = data.data[3] || 0;
            if (valorMas90 > 0) {
                 const porcentaje = ((valorMas90 / totalValor) * 100).toFixed(2);
                 descripcionEl.textContent = `Atención: El ${porcentaje}% ($${valorMas90.toFixed(2)}) del valor del stock de insumos tiene más de 90 días.`;
            } else {
                 descripcionEl.textContent = `El valor total del stock de insumos es de $${totalValor.toFixed(2)}. No hay stock obsoleto.`;
            }
        });
        
    if (downloadBtn && !downloadBtn.hasAttribute('data-initialized')) {
        downloadBtn.addEventListener('click', () => {
            const url = chart.getConnectedDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
            const a = document.createElement('a');
            a.href = url;
            a.download = 'antiguedad_stock_insumos.png';
            a.click();
        });
        downloadBtn.setAttribute('data-initialized', 'true');
    }
};

updateAntiguedadProductosChart = () => {
    const chartDom = document.getElementById('antiguedad-productos-chart');
    if(!chartDom) return;
    
    const chart = echarts.getInstanceByDom(chartDom) || echarts.init(chartDom);
    const downloadBtn = document.getElementById('download-antiguedad-productos');
    
    chart.showLoading();
    fetch(`/reportes/api/inventario/antiguedad_stock?tipo=producto`)
        .then(response => response.json())
        .then(data => {
            chart.hideLoading();
            if (data.error || data.data.reduce((a, b) => a + b, 0) === 0) {
                chart.setOption({ title: { text: 'No se encontraron datos', left: 'center', top: 'center' }, series: [] }, true);
                document.getElementById('antiguedad-productos-descripcion').textContent = 'No hay datos de stock de productos.';
                return;
            }

            const option = {
                tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                xAxis: { type: 'category', data: data.labels },
                yAxis: { type: 'value', name: 'Valor ($)' },
                series: [{
                    name: 'Valor de Stock', type: 'bar', data: data.data,
                     itemStyle: { color: (params) => inventarioColors[params.dataIndex] }
                }],
                grid: { containLabel: true }
            };
            chart.setOption(option, true);

             const descripcionEl = document.getElementById('antiguedad-productos-descripcion');
            const totalValor = data.data.reduce((a, b) => a + b, 0);
            const valorMas90 = data.data[3] || 0;
            if (valorMas90 > 0) {
                 const porcentaje = ((valorMas90 / totalValor) * 100).toFixed(2);
                 descripcionEl.textContent = `Alerta: El ${porcentaje}% ($${valorMas90.toFixed(2)}) del valor del stock de productos tiene más de 90 días.`;
            } else {
                 descripcionEl.textContent = `El valor total del stock de productos es de $${totalValor.toFixed(2)}.`;
            }
        });
        
    if (downloadBtn && !downloadBtn.hasAttribute('data-initialized')) {
         downloadBtn.addEventListener('click', () => {
            const url = chart.getConnectedDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
            const a = document.createElement('a');
            a.href = url;
            a.download = 'antiguedad_stock_productos.png';
            a.click();
        });
        downloadBtn.setAttribute('data-initialized', 'true');
    }
};