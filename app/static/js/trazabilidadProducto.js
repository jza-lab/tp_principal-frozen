document.addEventListener('DOMContentLoaded', function () {
    const trazabilidadTab = document.getElementById('trazabilidad-tab');
    if (!trazabilidadTab) return;

    let isDataLoaded = false;

    trazabilidadTab.addEventListener('shown.bs.tab', function () {
        if (!isDataLoaded) {
            loadTrazabilidadData();
            isDataLoaded = true;
        }
    });

    function loadTrazabilidadData() {
        const loteId = window.LOTE_ID;
        if (!loteId) {
            console.error("LOTE_ID not defined.");
            return;
        }
        const apiUrl = `/api/trazabilidad/lote_producto/${loteId}`;

        renderSpinner('resumen-trazabilidad');
        
        fetch(apiUrl)
            .then(response => response.json())
            .then(data => {
                if(data.success) {
                    renderResumen(data.data.resumen);
                    drawVisNetwork(data.data.diagrama);
                } else {
                    throw new Error(data.error);
                }
            })
            .catch(error => {
                console.error('Error loading traceability data:', error);
                document.getElementById('resumen-trazabilidad').innerHTML = `<div class="alert alert-danger">Error al cargar datos.</div>`;
            });
    }

    function renderSpinner(elementId) {
        const element = document.getElementById(elementId);
        if(element) element.innerHTML = `<div class="text-center p-3"><div class="spinner-border text-secondary" role="status"></div></div>`;
    }

    function renderResumen(resumen) {
        const container = document.getElementById('resumen-trazabilidad');
        if (!resumen || !resumen.origen) {
            container.innerHTML = '<p>No se encontró resumen.</p>';
            return;
        }
        const origen = resumen.origen;
        container.innerHTML = `
            <h6>Origen (Hacia Atrás)</h6>
            <ul class="list-group list-group-flush">
                <li class="list-group-item">
                    <strong>Creado por (OP):</strong> 
                    <a href="/orden-produccion/detalle/${origen.op_id}">${origen.op_codigo}</a>
                </li>
            </ul>`;
    }

    function drawVisNetwork(diagrama) {
        const container = document.getElementById('vis_trazabilidad');
        if (!diagrama || !diagrama.nodes || diagrama.nodes.length === 0) {
            container.innerHTML = '<div class="alert alert-info text-center p-4">No se encontraron datos para el diagrama de red.</div>';
            return;
        }

        const nodes = new vis.DataSet(diagrama.nodes);
        const edges = new vis.DataSet(diagrama.edges);

        const data = { nodes: nodes, edges: edges };
        const options = {
            layout: { hierarchical: { enabled: true, direction: 'LR', sortMethod: 'directed' }},
            edges: { arrows: 'to', font: { align: 'middle' }},
            interaction: { hover: true },
            physics: { enabled: false }
        };
        
        container.innerHTML = '';
        const network = new vis.Network(container, data, options);

        network.on("click", function (params) {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const node = nodes.get(nodeId);
                if (node.url) {
                    window.location.href = node.url;
                }
            }
        });
    }

    const btnCrearAlerta = document.getElementById('btn-crear-alerta');
    if(btnCrearAlerta) {
        btnCrearAlerta.addEventListener('click', function() {
            this.disabled = true;
            this.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creando...`;

            const postData = {
                tipo_entidad: 'lote_producto',
                id_entidad: window.LOTE_ID
            };

            fetch('/admin/riesgos/crear-alerta', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(postData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success && data.redirect_url) {
                    window.location.href = data.redirect_url;
                } else {
                    alert('Error al crear la alerta: ' + (data.error || 'Error desconocido'));
                    this.disabled = false;
                    this.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> Crear Alerta de Riesgo`;
                }
            })
            .catch(error => {
                console.error('Error en fetch:', error);
                alert('Error de red al crear la alerta.');
                this.disabled = false;
                this.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> Crear Alerta de Riesgo`;
            });
        });
    }
});
