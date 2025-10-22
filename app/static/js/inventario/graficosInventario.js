const ctx = document.getElementById('graficoInsumos');
const container = ctx.parentNode;

if (typeof INSUMOS_STOCK_DATA !== 'undefined' && INSUMOS_STOCK_DATA.length > 0) {

    const labels = INSUMOS_STOCK_DATA.map(i => i.nombre);
    const data = INSUMOS_STOCK_DATA.map(i => i.stock_actual);
    const minStocks = INSUMOS_STOCK_DATA.map(i => i.stock_min);

    let BAR_THICKNESS = 18; 
    let PADDING_PER_BAR = 10; 
    let HEADER_FOOTER_PADDING = 100;
    const requiredHeight = INSUMOS_STOCK_DATA.length * (BAR_THICKNESS + PADDING_PER_BAR) + HEADER_FOOTER_PADDING;

    container.style.height = `${requiredHeight}px`;

    const stockBajoData = INSUMOS_STOCK_DATA.map(i => 
        i.estado_stock === 'BAJO' ? i.stock_actual : null
    );
    const stockOkData = INSUMOS_STOCK_DATA.map(i => 
        i.estado_stock === 'OK' ? i.stock_actual : null
    );

    // Definición de colores
    const COLOR_BAJO = 'rgba(255, 99, 132, 0.8)'; // Rojo
    const COLOR_OK = 'rgba(54, 162, 235, 0.8)';   // Azul

    const getBarColor = (insumo) => {

        if (insumo.estado_stock === 'BAJO') {
            return COLOR_BAJO;
        }
        return COLOR_OK;
    };

    const backgroundColors = INSUMOS_STOCK_DATA.map(getBarColor);
    const borderColors = INSUMOS_STOCK_DATA.map(i => i.estado_stock === 'BAJO' ? 'rgba(255, 99, 132, 1)' : 'rgba(54, 162, 235, 1)');
    const maxStock = Math.max(...data); 
    const suggestedMax = Math.max(maxStock * 1.2, 20);

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Stock Crítico (Bajo Mínimo)',
                    data: stockBajoData, // Usa solo los datos de stock bajo
                    backgroundColor: COLOR_BAJO,
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1,
                    barThickness: BAR_THICKNESS,
                    barSkipped: false,
                    barPercentage: 0.95,
                    categoryPercentage: 0.95,
                    stack: 'stock'
                },
                {
                    label: 'Stock OK (Sobre Mínimo)',
                    data: stockOkData, // Usa solo los datos de stock OK
                    backgroundColor: COLOR_OK,
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1,
                    barThickness: BAR_THICKNESS,
                    barSkipped: false,
                    barPercentage: 0.95,
                    categoryPercentage: 0.95,
                    stack: 'stock'
                }
            ]
        },
        options: {
            indexAxis: 'y', // Barras horizontales
            elements: {
                bar: {
                    borderWidth: 2,
                }
            },
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    beginAtZero: true,
                    suggestedMax: suggestedMax, 
                    title: {
                        display: true,
                        text: 'Cantidad en Stock'
                    },
                    stacked: true
                },
                y: {
                    title: {
                        display: true,
                        text: 'Insumo'
                    },
                    stacked: true
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    font: {
                        size:12
                    }
                },
                title: {
                    display: true,
                    text: 'Composicion del stock actual de insumos',
                    font: {
                        size: 14
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const index = context.dataIndex;
                            const insumoData = INSUMOS_STOCK_DATA[index];
                            let label = `Stock Actual: ${context.formattedValue} ${insumoData.unidad_medida || ''}`;
                            if (insumoData.stock_min > 0) {
                                label += ` (Mínimo: ${insumoData.stock_min})`;
                            }
                            if (insumoData.estado_stock === 'BAJO') {
                                label += ' - ¡STOCK BAJO!';
                            }
                            return label;
                        }
                    }
                }
            }
        },
    });


} else {
    // Caso de no haber datos para el gráfico
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Stock Actual',
                data: data,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 1,
                barThickness: BAR_THICKNESS,
                barSkipped: false,
                barPercentage: 0.95,
                categoryPercentage: 0.95
            }]
        },
        options: {
            indexAxis: 'y', // Barras horizontales
            elements: {
                bar: {
                    borderWidth: 2,
                }
            },
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'No hay datos de insumos para el gráfico (Stock 0 o no críticos)'
                },
                legend: {
                    display: false
                }
            }
        }
    });
}