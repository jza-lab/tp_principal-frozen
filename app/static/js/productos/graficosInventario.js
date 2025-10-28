// --- LÓGICA DE GRÁFICO CIRCULAR PARA PRODUCTOS ---

const ctxProducto = document.getElementById('graficoProducto');
const datosGraficoProductos = typeof DATOS_GRAFICO_PRODUCTOS !== 'undefined' ? DATOS_GRAFICO_PRODUCTOS : [];

if (ctxProducto && datosGraficoProductos.length > 0) {
    const labels = datosGraficoProductos.map(p => p.nombre);
    const data = datosGraficoProductos.map(p => p.cantidad);

    // Función para generar colores vibrantes y aleatorios
    const generateColors = (count) => {
        const colors = [];
        for (let i = 0; i < count; i++) {
            const hue = (i * 137.508) % 360; // Usa el ángulo dorado para espaciar colores
            colors.push(`hsl(${hue}, 70%, 50%)`);
        }
        return colors;
    };

    new Chart(ctxProducto, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: generateColors(data.length),
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
                    text: 'Composición del Inventario de Productos',
                    font: { size: 14, weight: 'bold' }
                },
                subtitle: {
                    display: true,
                    text: ['Este gráfico ciruclar representa la composición',
                        ' del stock actual del inventario de productos'],
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
                    labels: {
                        boxWidth: 12,
                        padding: 15,
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const value = context.parsed;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = (total > 0 ? (value / total) * 100 : 0).toFixed(1) + '%';
                            return `${context.label}: ${value} unidades (${percentage})`;
                        }
                    }
                }
            }
        }
    });
}