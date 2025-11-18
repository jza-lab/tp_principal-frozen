const ventasColors = ['#5470C6', '#91CC75', '#EE6666', '#73C0DE', '#3BA272', '#FC8452', '#9A60B4', '#EA7CCC'];

updateTopProductosChart = () => {
    const chartDom = document.getElementById('top-productos-chart');
    if (!chartDom) return;

    const chart = echarts.getInstanceByDom(chartDom) || echarts.init(chartDom);
    const topNSelector = document.getElementById('top-n-selector');
    const downloadBtn = document.getElementById('download-top-productos');

    const topN = topNSelector.value;
    const fechaInicio = document.getElementById('fecha_inicio').value;
    const fechaFin = document.getElementById('fecha_fin').value;
    
    chart.showLoading();
    fetch(`/reportes/api/ventas/top_productos?top_n=${topN}&fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}`)
        .then(response => response.json())
        .then(data => {
            chart.hideLoading();
            if (data.error || data.labels.length === 0) {
                chart.setOption({ title: { text: 'No se encontraron datos', left: 'center', top: 'center' }, series: [] }, true);
                document.getElementById('top-productos-descripcion').textContent = 'No se encontraron datos de ventas para este período.';
                return;
            }

            const option = {
                tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                xAxis: { type: 'category', data: data.labels, axisLabel: { interval: 0, rotate: 30 } },
                yAxis: { type: 'value', name: 'Cantidad Vendida' },
                series: [{ name: 'Cantidad Vendida', type: 'bar', data: data.data, itemStyle: { color: ventasColors[0] } }],
                grid: { containLabel: true },
                dataZoom: [{ type: 'inside' }, { type: 'slider' }]
            };
            chart.setOption(option, true);
            
            const descripcionEl = document.getElementById('top-productos-descripcion');
            const productoMasVendido = data.labels[0];
            const cantidadMasVendida = data.data[0];
            descripcionEl.textContent = `El producto estrella en este período es "${productoMasVendido}" con ${cantidadMasVendida} unidades vendidas.`;
        });

    if (topNSelector && !topNSelector.hasAttribute('data-initialized')) {
        topNSelector.addEventListener('change', updateTopProductosChart);
        topNSelector.setAttribute('data-initialized', 'true');
    }
    if (downloadBtn && !downloadBtn.hasAttribute('data-initialized')) {
        downloadBtn.addEventListener('click', () => {
             const url = chart.getConnectedDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
             const a = document.createElement('a');
             a.href = url;
             a.download = 'top_productos_vendidos.png';
             a.click();
        });
        downloadBtn.setAttribute('data-initialized', 'true');
    }
};

updateFacturacionChart = () => {
    const chartDom = document.getElementById('facturacion-chart');
    if(!chartDom) return;

    const chart = echarts.getInstanceByDom(chartDom) || echarts.init(chartDom);
    const periodoSelector = document.getElementById('periodo-facturacion-selector');
    const downloadBtn = document.getElementById('download-facturacion');

    const periodo = periodoSelector.value;
    const fechaInicio = document.getElementById('fecha_inicio').value;
    const fechaFin = document.getElementById('fecha_fin').value;

    chart.showLoading();
    fetch(`/reportes/api/ventas/facturacion?periodo=${periodo}&fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}`)
        .then(response => response.json())
        .then(data => {
            chart.hideLoading();
            if (data.error || data.labels.length === 0) {
                chart.setOption({ title: { text: 'No se encontraron datos', left: 'center', top: 'center' }, series: [] }, true);
                document.getElementById('facturacion-descripcion').textContent = 'No hay datos de facturación para el período seleccionado.';
                return;
            }

            const option = {
                tooltip: { trigger: 'axis' },
                xAxis: { type: 'category', data: data.labels },
                yAxis: { type: 'value', name: 'Facturación ($)' },
                series: [{
                    name: 'Facturación', type: 'line', data: data.data, smooth: true, itemStyle: { color: ventasColors[1] },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: echarts.color.lift(ventasColors[1], 0.5) }, { offset: 1, color: echarts.color.lift(ventasColors[1], 0.1) }])
                    }
                }],
                 grid: { containLabel: true }
            };
            chart.setOption(option, true);

            const descripcionEl = document.getElementById('facturacion-descripcion');
            if(data.data.length > 1) {
                const totalFacturado = data.data.reduce((a, b) => a + b, 0);
                const promedio = totalFacturado / data.data.length;
                const ultimoValor = data.data[data.data.length - 1];
                const tendencia = ultimoValor > promedio ? "por encima" : "por debajo";
                descripcionEl.textContent = `La facturación total del período fue de $${totalFacturado.toFixed(2)}. El último período registrado está ${tendencia} del promedio ($${promedio.toFixed(2)}).`;
            } else if(data.data.length === 1) {
                 descripcionEl.textContent = `Se registró una facturación total de $${data.data[0].toFixed(2)}.`;
            }
        });

    if (periodoSelector && !periodoSelector.hasAttribute('data-initialized')) {
        periodoSelector.addEventListener('change', updateFacturacionChart);
        periodoSelector.setAttribute('data-initialized', 'true');
    }
    if (downloadBtn && !downloadBtn.hasAttribute('data-initialized')) {
        downloadBtn.addEventListener('click', () => {
             const url = chart.getConnectedDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
             const a = document.createElement('a');
             a.href = url;
             a.download = 'evolucion_facturacion.png';
             a.click();
        });
        downloadBtn.setAttribute('data-initialized', 'true');
    }
};