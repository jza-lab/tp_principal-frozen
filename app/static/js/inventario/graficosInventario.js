const ctx = document.getElementById('graficoInsumos');

const BAR_THICKNESS = 18;
const PADDING_PER_BAR = 10;
const HEADER_FOOTER_PADDING = 200;
const COLOR_BAJO = 'rgba(255, 99, 132, 0.8)'; // Rojo
const COLOR_OK = 'rgba(54, 162, 235, 0.8)';   // Azul
const COLOR_STOCK0 = 'rgba(255, 0, 0, 0.8)'; // Sin Stock
let estadoVisibilidad = {
    [COLOR_BAJO]: false, // false = Visible
    [COLOR_OK]: false    // false = Visible
};

// Solo si el elemento canvas existe, procedemos
if (ctx) {
    const container = document.getElementById('contenedorGraficoInsumos');

    if (typeof INSUMOS_STOCK_DATA !== 'undefined' && INSUMOS_STOCK_DATA.length > 0) {

        const labels = INSUMOS_STOCK_DATA.map(i => i.nombre);
        const data = INSUMOS_STOCK_DATA.map(i => i.stock_actual);
        const minStocks = INSUMOS_STOCK_DATA.map(i => i.stock_min);


        const requiredHeight = INSUMOS_STOCK_DATA.length * (BAR_THICKNESS + PADDING_PER_BAR) + HEADER_FOOTER_PADDING;

        container.style.height = `${requiredHeight}px`;

        // Estas variables stockBajoData y stockOkData ya NO se usan, pero se dejan por si fueran necesarias.
        const stockBajoData = INSUMOS_STOCK_DATA.map(i =>
            i.estado_stock === 'BAJO' ? i.stock_actual : null
        );
        const stockOkData = INSUMOS_STOCK_DATA.map(i =>
            i.estado_stock === 'OK' ? i.stock_actual : null
        );

        // Función para determinar el color de cada barra
        const getBarColor = (insumo) => {
            // Asignamos COLOR_BAJO (Rojo) si es 'BAJO'
            if (insumo.estado_stock === 'BAJO') {
                return COLOR_BAJO;
            }
            // Asignamos COLOR_OK (Azul) para el resto (OK)
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
                        label: 'Stock Actual', // Etiqueta del dataset, que será ocultada en la leyenda
                        data: data,
                        backgroundColor: backgroundColors,
                        borderColor: borderColors,
                        borderWidth: 1,
                        barThickness: BAR_THICKNESS,
                        barSkipped: false,
                        barPercentage: 0.95,
                        categoryPercentage: 0.95,
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
                        stacked: false
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Insumo'
                        },
                        stacked: false
                    },
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        font: {
                            size: 12
                        },
                        // *** FUNCIÓN ONCLICK CORREGIDA ***
                        onClick: function (e, legendItem, legend) {
                            const chart = legend.chart;
                            const clickedColor = legendItem.fillStyle;
                            const dataset = chart.data.datasets[0];

                            // 1. Alternar el estado de visibilidad
                            estadoVisibilidad[clickedColor] = !estadoVisibilidad[clickedColor];

                            // 2. Modificar la opacidad de la etiqueta en la leyenda
                            legendItem.hidden = estadoVisibilidad[clickedColor];

                            // 3. Crear los nuevos arrays de datos, color de fondo, y color de borde
                            const newBackgroundColors = [];
                            const newBorderColors = [];
                            const newData = [];

                            INSUMOS_STOCK_DATA.forEach((insumo, index) => {
                                const barColor = getBarColor(insumo);
                                const isHidden = estadoVisibilidad[barColor];

                                if (isHidden) {
                                    // Si el estado está oculto (filtrado):
                                    newBackgroundColors.push('rgba(0, 0, 0, 0)'); // Fondo transparente
                                    newBorderColors.push('rgba(0, 0, 0, 0)');     // Borde transparente
                                    newData.push(0);                              // Valor 0 para que colapse y no se vea
                                } else {
                                    // Si el estado está visible:
                                    newBackgroundColors.push(barColor);
                                    newBorderColors.push(insumo.estado_stock === 'BAJO' ? 'rgba(255, 99, 132, 1)' : 'rgba(54, 162, 235, 1)');
                                    newData.push(insumo.stock_actual);
                                }
                            });

                            // 4. Aplicar los nuevos datos y estilos
                            dataset.backgroundColor = newBackgroundColors;
                            dataset.borderColor = newBorderColors;
                            dataset.data = newData;

                            // 5. Forzar la actualización del gráfico
                            chart.update();
                        },
                        // *** FIN DE FUNCIÓN ONCLICK CORREGIDA ***
                        labels: {
                            // ... (el filter y generateLabels se mantienen iguales) ...
                            filter: function (item, chart) {
                                // Oculta la etiqueta del dataset 'Stock Actual'
                                return item.datasetIndex === undefined;
                            },
                            generateLabels: function (chart) {
                                // Asegúrate de usar las constantes directamente (están fuera del scope de chart.js)
                                return [
                                    {
                                        text: 'Stock Bajo (Bajo Mínimo)',
                                        fillStyle: COLOR_BAJO, // Usar las constantes globales aquí
                                        strokeStyle: 'rgba(255, 99, 132, 1)',
                                        lineWidth: 1
                                    },
                                    {
                                        text: 'Stock OK (Sobre Mínimo)',
                                        fillStyle: COLOR_OK, // Usar las constantes globales aquí
                                        strokeStyle: 'rgba(54, 162, 235, 1)',
                                        lineWidth: 1
                                    }
                                ];
                            }
                        }
                    },
                    title: {
                        display: true,
                        text: 'Composicion del stock actual de insumos',
                        font: {
                            size: 14
                        }
                    },
                    subtitle: {
                        display: true,
                        text: [
                            'Este gráfico de barras horizontal muestra la cantidad actual', ' de stock de cada insumo según su estado (Bajo Mínimo, Sobre Mínimo).',
                            'Permitiendo identificar la condición del inventario rápidamente.'
                        ],
                        color: '#666',
                        font: {
                            size: 12
                        },
                        padding: {
                            top: 5,
                            bottom: 20
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
                                // Ajustado el tooltip para incluir Stock 0 como BAJO/CRÍTICO
                                if (insumoData.estado_stock === 'BAJO' || insumoData.stock_actual === 0) {
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
}

// --- GRÁFICO DE DONA (Stock BAJO vs. Stock OK) ---
const ctxDonut = document.getElementById('graficoDonut');
const dataForDonut = typeof INSUMOS_FULL_DATA !== 'undefined' ? INSUMOS_FULL_DATA : [];

if (ctxDonut && dataForDonut.length > 0) {
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
                    subtitle: {
                        display: true,
                        text: ['Este gráfico ciruclar representa la proporción de insumos',
                            ' clasificados por su estado de stock (Crítico, OK o Sin Stock)',
                            ' respecto al total de insumos registrados.'],
                        color: '#666',
                        font: {
                            size: 12
                        },
                        padding: {
                            top: 5,
                            bottom: 20
                        }
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