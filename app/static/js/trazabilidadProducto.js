document.addEventListener('DOMContentLoaded', function () {
    const TIPO_ENTIDAD = 'lote_producto';
    const ID_ENTIDAD = window.LOTE_PRODUCTO_ID;
    const visContainer = document.getElementById('vis_trazabilidad');
    const accordionButton = document.querySelector('button[data-bs-target="#collapseDiagrama"]');
    let network = null;
    let chartLoaded = false;

    function initVisNetwork(data) {
        const nodes = new vis.DataSet(data.nodes);
        const edges = new vis.DataSet(data.edges);
        const options = {
            layout: {
                hierarchical: {
                    direction: "LR", // Left to Right
                    sortMethod: "directed",
                    levelSeparation: 300,
                    nodeSpacing: 200
                }
            },
            edges: {
                arrows: 'to',
                font: {
                    align: 'middle'
                },
                smooth: {
                    type: 'cubicBezier'
                }
            },
            nodes: {
                shape: 'box',
                margin: 10,
                font: {
                    size: 14,
                    color: '#ffffff'
                },
                borderWidth: 2
            },
            groups: {
                lote_insumo: {
                    color: {
                        background: '#56B4E9',
                        border: '#4691B9'
                    }
                },
                orden_compra: {
                    color: {
                        background: '#F0E442',
                        border: '#D4C83A'
                    },
                    font: {
                        color: '#333333'
                    }
                },
                orden_produccion: {
                    color: {
                        background: '#E69F00',
                        border: '#B87F00'
                    }
                },
                lote_producto: {
                    color: {
                        background: '#009E73',
                        border: '#007E5C'
                    }
                },
                pedido: {
                    color: {
                        background: '#CC79A7',
                        border: '#A36085'
                    }
                },
                ingreso_manual: {
                    color: {
                        background: '#999999',
                        border: '#7A7A7A'
                    }
                }
            },
            physics: false
        };
        network = new vis.Network(visContainer, {
            nodes: nodes,
            edges: edges
        }, options);

        network.on("click", function (params) {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const node = nodes.get(nodeId);
                if (node.url) {
                    window.location.href = node.url;
                }
            }
        });
         // Ocultar el spinner y mostrar el contenedor
        const spinner = visContainer.querySelector('.spinner-border');
        if (spinner) {
            spinner.parentElement.style.display = 'none';
        }
    }

    function loadChart() {
        if (chartLoaded) return;
        
        fetch(`/api/trazabilidad/${TIPO_ENTIDAD}/${ID_ENTIDAD}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('La respuesta de la red no fue exitosa.');
                }
                return response.json();
            })
            .then(result => {
                if (result.success && result.data.diagrama) {
                    initVisNetwork(result.data.diagrama);
                    chartLoaded = true;
                } else {
                    visContainer.innerHTML = '<div class="alert alert-warning">No se pudo cargar el diagrama de trazabilidad.</div>';
                }
            })
            .catch(error => {
                console.error('Error al cargar datos de trazabilidad:', error);
                visContainer.innerHTML = '<div class="alert alert-danger">Error al cargar el diagrama.</div>';
            });
    }
    
    // Cargar el gráfico solo cuando se abre el acordeón
    const collapseElement = document.getElementById('collapseDiagrama');
    collapseElement.addEventListener('shown.bs.tab', loadChart);
    // Para la primera vez que se hace clic
    accordionButton.addEventListener('click', loadChart, { once: true });
});