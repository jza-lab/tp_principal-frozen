const ctx = document.getElementById('graficoInsumos');
const container = ctx.parentNode;

const BAR_THICKNESS = 18;
const PADDING_PER_BAR = 10;
const HEADER_FOOTER_PADDING = 100;
const COLOR_BAJO = 'rgba(255, 99, 132, 0.8)'; // Rojo
const COLOR_OK = 'rgba(54, 162, 235, 0.8)';   // Azul
const COLOR_STOCK0 = 'rgba(255, 0, 0, 0.8)'; // Sin Stock

if (typeof INSUMOS_STOCK_DATA !== 'undefined' && INSUMOS_STOCK_DATA.length > 0) {

    const labels = INSUMOS_STOCK_DATA.map(i => i.nombre);
    const data = INSUMOS_STOCK_DATA.map(i => i.stock_actual);
    const minStocks = INSUMOS_STOCK_DATA.map(i => i.stock_min);

    const requiredHeight = INSUMOS_STOCK_DATA.length * (BAR_THICKNESS + PADDING_PER_BAR) + HEADER_FOOTER_PADDING;

    container.style.height = `${requiredHeight}px`;

    const stockBajoData = INSUMOS_STOCK_DATA.map(i =>
        i.estado_stock === 'BAJO' ? i.stock_actual : null
    );
    const stockOkData = INSUMOS_STOCK_DATA.map(i =>
        i.estado_stock === 'OK' ? i.stock_actual : null
    );

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
                    label: 'Stock Bajo (Bajo Mínimo)',
                    data: stockBajoData,
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
                    data: stockOkData,
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
            indexAxis: 'y',
            elements: {
                bar: {
                    borderWidth: 2,
                }
            },
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                x: {
                    duration: 1000,
                    easing: 'easeInOutQuart'
                },
                y: {
                    duration: 500
                }
            },
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
                },
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    font: {
                        size: 12
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


}

// --- GRÁFICO DE DONA (Stock BAJO vs. Stock OK) ---
const ctxDonut = document.getElementById('graficoDonut');
const dataForDonut = typeof INSUMOS_FULL_DATA !== 'undefined' ? INSUMOS_FULL_DATA : [];

if (dataForDonut.length > 0) {
    const countBajo = dataForDonut.filter(i =>
        i.stock_actual > 0 && i.estado_stock === 'BAJO'
    ).length;

    const countOk = dataForDonut.filter(i =>
        i.stock_actual > 0 && i.estado_stock === 'OK'
    ).length;
    const countStock0 = dataForDonut.filter(i =>
        i.stock_actual === 0
    ).length;

    const totalCount = countBajo + countOk + countStock0;

    if (totalCount > 0) {
        const donutData = [countBajo, countOk, countStock0];
        const donutLabels = ['Stock Crítico (Bajo Mínimo)', 'Stock OK (Sobre Mínimo)', 'Sin Stock'];

        const donutColors = [COLOR_BAJO, COLOR_OK, COLOR_STOCK0];

        new Chart(ctxDonut, {
            type: 'doughnut',
            data: {
                labels: donutLabels,
                datasets: [{
                    data: donutData,
                    backgroundColor: donutColors,
                    hoverOffset: 10,
                    borderColor: '#fff',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Distribución de Insumos por Estado de Stock',
                        font: { size: 14, weight: 'bold' }
                    },
                    legend: {
                        display: true,
                        position: 'bottom',
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = (total > 0 ? (value / total) * 100 : 0).toFixed(1) + '%';
                                return `${context.label}: ${value} insumos (${percentage})`;
                            }
                        }
                    }
                }
            }
        });
    }
}