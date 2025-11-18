// /static/js/exportarTrazabilidadPDF.js

document.addEventListener('DOMContentLoaded', () => {
    const exportButton = document.getElementById('export-trazabilidad-pdf');
    if (!exportButton) return;

    exportButton.addEventListener('click', async () => {
        const originalButtonText = exportButton.innerHTML;
        exportButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Generando PDF...`;
        exportButton.disabled = true;

        try {
            const entityType = window.ENTITY_TYPE;
            const entityId = window.ENTITY_ID;
            if (!entityType || !entityId) throw new Error("Tipo/ID de entidad no definidos.");

            // 1. Fetch data and diagram image
            const [companyInfo, traceData, diagramImage] = await Promise.all([
                fetch('/api/trazabilidad/company_info').then(res => res.json()),
                fetchTraceData(entityType, entityId),
                captureDiagramImage() // ¡Función actualizada!
            ]);

            // 2. Generate the PDF manually
            await generatePdfManually(companyInfo, traceData, diagramImage, entityType, entityId);

        } catch (error) {
            console.error('Error al generar el PDF de trazabilidad:', error);
            alert('Ocurrió un error al generar el PDF: ' + error.message);
        } finally {
            // 3. Cleanup
            exportButton.innerHTML = originalButtonText;
            exportButton.disabled = false;
        }
    });
});

// --- DATA FETCHING FUNCTIONS ---

async function captureDiagramImage() {
    console.log("Iniciando captura de diagrama...");

    const elementToCapture = document.getElementById('vis_trazabilidad') || document.getElementById('sankey_chart_trazabilidad');
    if (!elementToCapture) {
        console.error("Error crítico: No se encontró el contenedor del diagrama.");
        return null;
    }

    const accordionCollapse = elementToCapture.closest('.accordion-collapse');
    const tabPane = elementToCapture.closest('.tab-pane');

    const wasTabActive = tabPane ? tabPane.classList.contains('active') : true;
    const wasAccordionShown = accordionCollapse ? accordionCollapse.classList.contains('show') : true;
    const originalActiveTabLink = wasTabActive ? null : document.querySelector('.nav-tabs .nav-link.active, .nav-tabs-custom .nav-link-custom.active');
    
    // Guardar la vista original (zoom y posición) para restaurarla después
    const originalView = window.visNetwork ? { 
        scale: window.visNetwork.getScale(), 
        position: window.visNetwork.getViewPosition() 
    } : null;

    try {
        if (!wasTabActive && tabPane) {
            const tabId = tabPane.id;
            const tabLink = document.querySelector(`[data-bs-toggle="tab"][data-bs-target="#${tabId}"]`);
            if (tabLink) {
                console.log("Activando pestaña de Trazabilidad...");
                new bootstrap.Tab(tabLink).show();
                await new Promise(r => setTimeout(r, 300));
            }
        }

        if (!wasAccordionShown && accordionCollapse) {
            console.log("Expandiendo acordeón del diagrama...");
            const collapse = new bootstrap.Collapse(accordionCollapse, { toggle: false });
            collapse.show();
            await new Promise(resolve => {
                const handler = () => { accordionCollapse.removeEventListener('shown.bs.collapse', handler); resolve(); };
                accordionCollapse.addEventListener('shown.bs.collapse', handler);
                setTimeout(resolve, 500);
            });
        }
        
        elementToCapture.scrollIntoView({ behavior: 'instant', block: 'start' });

        if (window.visNetwork) {
            console.log("Ajustando zoom del diagrama para la captura...");
            const nodeIds = window.visNetwork.body.data.nodes.getIds();

            // ¡COMIENZO DE LA CORRECCIÓN!
            // Solo ajustar el zoom si hay nodos para evitar errores.
            if (nodeIds && nodeIds.length > 0) {
                window.visNetwork.fit({
                    nodes: nodeIds,
                    animation: false
                });

                const boundingBox = window.visNetwork.getBoundingBox(nodeIds);

                // Comprobar que el boundingBox existe y tiene dimensiones válidas para evitar división por cero
                if (boundingBox && (boundingBox.right - boundingBox.left) > 0 && (boundingBox.bottom - boundingBox.top) > 0) {
                    const newScale = Math.min(
                        elementToCapture.clientWidth / (boundingBox.right - boundingBox.left),
                        elementToCapture.clientHeight / (boundingBox.bottom - boundingBox.top)
                    ) * 0.95; // 95% para un pequeño margen

                    window.visNetwork.moveTo({
                        scale: newScale,
                        animation: false
                    });
                }
                // Si no hay bounding box o las dimensiones son cero, no hacemos nada extra,
                // el 'fit' anterior ya habrá centrado la vista.

                await new Promise(r => setTimeout(r, 500)); // Espera para el redibujado final
            } else {
                 console.log("Diagrama vacío, no se requiere ajuste de zoom.");
            }
            // ¡FIN DE LA CORRECCIÓN!
        }

        console.log("Realizando captura con html2canvas...");
        const canvas = await html2canvas(elementToCapture, {
            scale: 3, // Aumentar la escala para mayor nitidez
            useCORS: true,
            logging: false,
            backgroundColor: '#FFFFFF',
        });
        
        return canvas.toDataURL('image/png', 1.0);

    } catch (error) {
        console.error('Error al capturar el diagrama:', error);
        return null;
    } finally {
        // Restaurar la vista original del diagrama
        if (window.visNetwork && originalView) {
            console.log("Restaurando vista original del diagrama.");
            window.visNetwork.moveTo({
                scale: originalView.scale,
                position: originalView.position,
                animation: false
            });
        }
        
        if (!wasAccordionShown && accordionCollapse) {
            console.log("Restaurando acordeón a estado colapsado.");
            new bootstrap.Collapse(accordionCollapse, { toggle: false }).hide();
        }
        if (!wasTabActive && originalActiveTabLink) {
            console.log("Restaurando pestaña original.");
            new bootstrap.Tab(originalActiveTabLink).show();
        }
    }
}


/**
 * Obtiene los datos de trazabilidad completos desde la API.
 */
async function fetchTraceData(entityType, entityId) {
    const response = await fetch(`/api/trazabilidad/${entityType}/${entityId}?nivel=completo`);
    if (!response.ok) throw new Error(`Error en API: ${response.statusText}`);
    const result = await response.json();
    if (!result.success) throw new Error(`El API devolvió un error: ${result.error}`);
    return {
        resumen: result.data.resumen || { origen: [], destino: [] },
        diagrama: result.data.diagrama || { nodes: [], edges: [] },
        ...result.data
    };
}


// --- DATA HELPER FUNCTIONS (Usadas por el generador manual) ---

/**
 * Busca los datos de un nodo específico.
 */
function findNodeData(traceData, entityType, entityId) {
    if (!traceData || !traceData.diagrama || !traceData.diagrama.nodes) return {};
    const nodeId = `${entityType}_${entityId}`;
    const node = traceData.diagrama.nodes.find(n => n.id === nodeId);
    if (!node && traceData.data && traceData.data.id == entityId && traceData.data.tipo == entityType) {
        return traceData.data;
    }
    return node ? node.data : {};
}

/**
 * Formatea un string de tipo_entidad a "Tipo Entidad".
 */
function formatEntityType(type) {
    if (!type) return '';
    return (type.charAt(0).toUpperCase() + type.slice(1)).replace(/_/g, ' ');
}

/**
 * Formatea un valor (moneda, fecha, etc.)
 */
function formatValue(value, format) {
    if (value === null || typeof value === 'undefined' || value === '') {
        return 'N/A';
    }
    try {
        switch (format) {
            case 'currency':
                const number = parseFloat(value);
                if (isNaN(number)) return value;
                return `$${number.toFixed(2).replace(/\d(?=(\d{3})+\.)/g, '$&,')}`;
            case 'date':
                const date = new Date(value);
                if (isNaN(date.getTime())) {
                    return value.split('T')[0];
                }
                return new Date(date.getTime() + date.getTimezoneOffset() * 60000)
                       .toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
            case 'html':
                if (value.includes('<li>')) {
                    return value.match(/<li>(.*?)<\/li>/g)
                                .map(li => '• ' + li.replace(/<\/?li>/g, '').trim())
                                .join('\n');
                }
                return value.replace(/<[^>]+>/g, '');
            default:
                return value.toString();
        }
    } catch (e) {
        return value.toString();
    }
}

/**
 * Obtiene la información visual para una barra de estado.
 */
function getOriginSubtitle(traceData, entityType, entityId) {
    if (!traceData || !traceData.diagrama || !traceData.diagrama.edges) return null;

    const nodeId = `${entityType}_${entityId}`;
    const edges = traceData.diagrama.edges;
    const nodes = traceData.diagrama.nodes;

    // Buscar la arista que apunta a este nodo
    const incomingEdge = edges.find(edge => edge.to === nodeId);

    if (!incomingEdge) {
        // Para Órdenes de Compra y entidades sin origen, es un "Origen primario"
        if (entityType === 'orden_compra') {
            return 'Origen: Primario';
        }
        return null; // No tiene origen visible en el grafo
    }

    const originNodeId = incomingEdge.from;
    const originNode = nodes.find(node => node.id === originNodeId);

    if (!originNode) return null; // No se encontró el nodo de origen

    const originType = originNode.group;
    const originData = originNode.data;
    
    if (originType === 'ingreso_manual') {
        return 'Origen: Ingreso Manual';
    }

    if (originType === 'orden_compra' && originData) {
        const proveedor = originData.proveedores ? originData.proveedores.nombre : 'N/A';
        return `Origen: ${originNode.label} (${proveedor})`;
    }
    
    // Para otros tipos de origen, solo mostramos la etiqueta del nodo
    if (originNode.label) {
        return `Origen: ${originNode.label}`;
    }

    return null;
}

function getStatusInfo(status) {
    if (!status) return { class: 'pending', width: '0%', label: 'N/A' };
    
    const statusMap = {
        'aprobada': { class: 'completed', width: '100%', color: '#28a745' },
        'aprobado': { class: 'completed', width: '100%', color: '#28a745' },
        'completa': { class: 'completed', width: '100%', color: '#28a745' },
        'completada': { class: 'completed', width: '100%', color: '#28a745' },
        'finalizada': { class: 'completed', width: '100%', color: '#28a745' },
        'recibida': { class: 'completed', width: '100%', color: '#28a745' },
        'entregado': { class: 'completed', width: '100%', color: '#28a745' },
        'en stock': { class: 'completed', width: '100%', color: '#28a745' },
        'disponible': { class: 'completed', width: '100%', color: '#28a745' },
        'despachado': { class: 'completed', width: '100%', color: '#28a745' },
        'pendiente': { class: 'pending', width: '25%', color: '#ffc107' },
        'planificada': { class: 'pending', width: '20%', color: '#ffc107' },
        'en cuarentena': { class: 'pending', width: '30%', color: '#ffc107' },
        'en curso': { class: 'in_progress', width: '60%', color: '#17a2b8' },
        'en preparación': { class: 'in_progress', width: '50%', color: '#17a2b8' },
        'recibida parcialmente': { class: 'in_progress', width: '75%', color: '#17a2b8' },
        'cancelada': { class: 'cancelled', width: '100%', color: '#dc3545' },
        'rechazado': { class: 'cancelled', width: '100%', color: '#dc3545' },
        'vencido': { class: 'cancelled', width: '100%', color: '#dc3545' }
    };

    const normalizedStatus = status.toLowerCase().trim();
    const info = statusMap[normalizedStatus] || { class: 'pending', width: '10%', color: '#6c757d' };
    
    return { ...info, label: formatEntityType(status) };
}

// --- DESCRIPCIONES DE SECCIONES ---
const SECTION_DESCRIPTIONS = {
    'main': 'Detalles de la entidad principal que está siendo auditada en este informe.',
    'diagram': 'Visualización gráfica de las relaciones de trazabilidad, mostrando el flujo de entidades de origen a destino.',
    'origen': 'Entidades que preceden a la entidad principal. Muestra de dónde provienen los materiales o qué acciones se tomaron antes.',
    'destino': 'Entidades que suceden a la entidad principal. Muestra a dónde fue el producto o qué acciones se tomaron después.'
};

const CATEGORY_DESCRIPTIONS = {
    'orden_compra': 'Registros de órdenes de compra utilizadas para adquirir insumos de proveedores.',
    'lote_insumo': 'Lotes de materiales o insumos específicos que fueron utilizados o consumidos.',
    'orden_produccion': 'Órdenes de producción que consumieron insumos o generaron productos.',
    'lote_producto': 'Lotes de producto terminado generados o relacionados con esta traza.',
    'pedido': 'Pedidos de clientes que han sido total o parcialmente despachados con las entidades de esta traza.'
};

// --- MAPA DE CAMPOS DE ENTIDAD ---
const ENTITY_FIELDS_MAP = {
    'orden_compra': [ { label: 'Estado', value: data => data.estado, isStatus: true }, { label: 'Proveedor', value: data => data.proveedores?.nombre }, { label: 'CUIT', value: data => data.proveedores?.cuit }, { label: 'Fecha Creación', value: data => data.fecha_creacion, format: 'date' }, { label: 'Monto Total', value: data => data.monto_total, format: 'currency' } ],
    'lote_insumo': [ { label: 'Estado', value: data => data.estado, isStatus: true }, { label: 'Insumo', value: data => data.insumos_catalogo?.nombre }, { label: 'Código Insumo', value: data => data.insumos_catalogo?.codigo }, { label: 'Lote Prov.', value: data => data.numero_lote_proveedor }, { label: 'Cantidad', value: data => `${data.cantidad_inicial || ''} ${data.unidad_medida || ''}`.trim() }, { label: 'Vencimiento', value: data => data.fecha_vencimiento, format: 'date' } ],
    'orden_produccion': [ { label: 'Estado', value: data => data.estado, isStatus: true }, { label: 'Producto', value: data => data.productos?.nombre }, { label: 'Código Prod.', value: data => data.productos?.codigo }, { label: 'Cantidad Planif.', value: data => data.cantidad_planificada }, { label: 'Fecha Meta', value: data => data.fecha_meta, format: 'date' } ],
    'lote_producto': [ { label: 'Estado', value: data => data.estado, isStatus: true }, { label: 'Producto', value: data => data.productos?.nombre }, { label: 'Código Prod.', value: data => data.productos?.codigo }, { label: 'Nro. Lote', value: data => data.numero_lote }, { label: 'Cantidad', value: data => data.cantidad_inicial }, { label: 'Vencimiento', value: data => data.fecha_vencimiento, format: 'date' } ],
    'pedido': [ { label: 'Estado', value: data => data.estado, isStatus: true }, { label: 'Cliente', value: data => data.clientes?.nombre || data.clientes?.razon_social }, { label: 'CUIT Cliente', value: data => data.clientes?.cuit }, { label: 'Fecha Entrega', value: data => data.fecha_entrega, format: 'date' }, { label: 'Monto Total', value: data => data.monto_total, format: 'currency' }, { label: 'Items', value: data => data.items?.map(i => `<li>${i.cantidad} x ${i.productos?.nombre || 'N/A'}</li>`).join('') || 'No hay items.', format: 'html'} ]
};


/**
 * Función principal para generar el PDF manualmente.
 */
async function generatePdfManually(companyInfo, traceData, diagramImage, entityType, entityId) {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF('p', 'mm', 'a4');

    const PDF_GLOBALS = {
        companyInfo: companyInfo,
        currentPage: 1,
        totalPages: 1,
        Y_CURSOR: 0,
        PAGE_W: doc.internal.pageSize.getWidth(),
        PAGE_H: doc.internal.pageSize.getHeight(),
        MARGIN: 15,
        CONTENT_W: doc.internal.pageSize.getWidth() - 30,
        COLOR_PRIMARY: '#0056b3',
        COLOR_TEXT: '#212529',
        COLOR_MUTED: '#555',
        COLOR_BORDER: '#ccc'
    };

    // --- HELPER FUNCTIONS ---

    function addHeader() {
        doc.setFont('Helvetica', 'bold');
        doc.setFontSize(18);
        doc.setTextColor(PDF_GLOBALS.COLOR_PRIMARY);
        doc.text(companyInfo.nombre || 'Mi Empresa', PDF_GLOBALS.MARGIN, PDF_GLOBALS.MARGIN + 5);

        doc.setFont('Helvetica', 'normal');
        doc.setFontSize(9);
        doc.setTextColor(PDF_GLOBALS.COLOR_MUTED);
        doc.text(companyInfo.domicilio || '', PDF_GLOBALS.MARGIN, PDF_GLOBALS.MARGIN + 11);
        doc.text(`CUIT: ${companyInfo.cuit || ''}`, PDF_GLOBALS.MARGIN, PDF_GLOBALS.MARGIN + 15);
        
        const dateText = `Generado: ${new Date().toLocaleDateString('es-ES')}`;
        doc.text(dateText, PDF_GLOBALS.PAGE_W - PDF_GLOBALS.MARGIN, PDF_GLOBALS.MARGIN + 5, { align: 'right' });

        doc.setDrawColor(PDF_GLOBALS.COLOR_BORDER);
        doc.line(PDF_GLOBALS.MARGIN, PDF_GLOBALS.MARGIN + 22, PDF_GLOBALS.PAGE_W - PDF_GLOBALS.MARGIN, PDF_GLOBALS.MARGIN + 22);
        PDF_GLOBALS.Y_CURSOR = PDF_GLOBALS.MARGIN + 30;
    }

    function addFooter() {
        const totalPages = PDF_GLOBALS.totalPages;
        for (let i = 1; i <= totalPages; i++) {
            doc.setPage(i);
            doc.setFontSize(8);
            doc.setTextColor(150);
            doc.text(
                `Página ${i} de ${totalPages}`,
                PDF_GLOBALS.PAGE_W / 2,
                PDF_GLOBALS.PAGE_H - 10,
                { align: 'center' }
            );
            doc.text(
                'Documento Confidencial',
                PDF_GLOBALS.MARGIN,
                PDF_GLOBALS.PAGE_H - 10
            );
        }
    }

    function checkPageBreak(requiredHeight) {
        if (PDF_GLOBALS.Y_CURSOR + requiredHeight > PDF_GLOBALS.PAGE_H - PDF_GLOBALS.MARGIN) {
            doc.addPage();
            PDF_GLOBALS.currentPage++;
            PDF_GLOBALS.totalPages++;
            addHeader();
            return true;
        }
        return false;
    }
    
    function drawSectionTitle(title) {
        if (PDF_GLOBALS.Y_CURSOR > PDF_GLOBALS.MARGIN + 30) {
             PDF_GLOBALS.Y_CURSOR += 5;
        }
        checkPageBreak(15);
        doc.setFont('Helvetica', 'bold');
        doc.setFontSize(16);
        doc.setTextColor(PDF_GLOBALS.COLOR_PRIMARY);
        doc.text(title, PDF_GLOBALS.MARGIN, PDF_GLOBALS.Y_CURSOR);
        PDF_GLOBALS.Y_CURSOR += 8;
    }
    
    function drawDescriptionText(text) {
        if (!text) return;
        doc.setFont('Helvetica', 'normal');
        doc.setFontSize(10);
        doc.setTextColor(PDF_GLOBALS.COLOR_MUTED);
        
        const splitText = doc.splitTextToSize(text, PDF_GLOBALS.CONTENT_W);
        checkPageBreak((splitText.length * 5) + 6);
        
        doc.text(splitText, PDF_GLOBALS.MARGIN, PDF_GLOBALS.Y_CURSOR);
        PDF_GLOBALS.Y_CURSOR += (splitText.length * 5) + 6;
    }

    function drawCategorySubtitle(title) {
        checkPageBreak(12);
        doc.setFont('Helvetica', 'bold');
        doc.setFontSize(13);
        doc.setTextColor(PDF_GLOBALS.COLOR_TEXT);
        doc.text(title, PDF_GLOBALS.MARGIN, PDF_GLOBALS.Y_CURSOR);
        doc.setDrawColor(PDF_GLOBALS.COLOR_BORDER);
        doc.line(PDF_GLOBALS.MARGIN, PDF_GLOBALS.Y_CURSOR + 2, PDF_GLOBALS.PAGE_W - PDF_GLOBALS.MARGIN, PDF_GLOBALS.Y_CURSOR + 2);
        PDF_GLOBALS.Y_CURSOR += 6;
    }

    function drawEntityCard(type, data, traceData) {
        if (!data || Object.keys(data).length === 0) {
            checkPageBreak(10);
            doc.setFont('Helvetica', 'italic');
            doc.setFontSize(10);
            doc.setTextColor(PDF_GLOBALS.COLOR_MUTED);
            doc.text("Datos no disponibles para esta entidad.", PDF_GLOBALS.MARGIN + 5, PDF_GLOBALS.Y_CURSOR);
            PDF_GLOBALS.Y_CURSOR += 10;
            return;
        }

        const fields = ENTITY_FIELDS_MAP[type] || [];
        const entityCode = data.codigo || data.numero_lote || data.id || '';
        const entityIdForSubtitle = data.id_lote || data.id;
        const originSubtitle = getOriginSubtitle(traceData, type, entityIdForSubtitle);
        
        let tempY = 0;
        tempY += 10;

        // Añadir espacio extra si hay subtítulo
        if (originSubtitle) {
            tempY += 6;
        }
        
        const statusField = fields.find(f => f.isStatus);
        if (statusField && statusField.value(data)) {
            tempY += 15;
        }
        
        fields.forEach(field => {
            if (field.isStatus) return;
            const value = formatValue(field.value(data), field.format);
            const splitValue = doc.splitTextToSize(value, PDF_GLOBALS.CONTENT_W - 65);
            tempY += (splitValue.length * 5) + 3;
        });
        const cardContentHeight = tempY + 5;
        
        checkPageBreak(cardContentHeight);
        
        const startY = PDF_GLOBALS.Y_CURSOR;
        
        doc.setFont('Helvetica', 'bold');
        doc.setFontSize(12);
        doc.setTextColor(PDF_GLOBALS.COLOR_PRIMARY);
        doc.text(`${formatEntityType(type)}: ${entityCode}`, PDF_GLOBALS.MARGIN + 5, startY + 8);
        PDF_GLOBALS.Y_CURSOR = startY + 12;
        
        // --- INICIO: DIBUJAR EL SUBTÍTULO DE ORIGEN ---
        if (originSubtitle) {
            doc.setFont('Helvetica', 'normal');
            doc.setFontSize(9);
            doc.setTextColor(PDF_GLOBALS.COLOR_MUTED);
            doc.text(originSubtitle, PDF_GLOBALS.MARGIN + 5, PDF_GLOBALS.Y_CURSOR);
            PDF_GLOBALS.Y_CURSOR += 6;
        }
        // --- FIN: DIBUJAR EL SUBTÍTULO DE ORIGEN ---

        if (statusField) {
            const statusValue = statusField.value(data);
            if (statusValue) {
                const statusInfo = getStatusInfo(statusValue);
                doc.setFont('Helvetica', 'normal');
                doc.setFontSize(9);
                doc.setTextColor(PDF_GLOBALS.COLOR_MUTED);
                doc.text(`Estado: ${statusInfo.label}`, PDF_GLOBALS.MARGIN + 5, PDF_GLOBALS.Y_CURSOR + 2);

                doc.setFillColor('#e9ecef');
                doc.rect(PDF_GLOBALS.MARGIN + 5, PDF_GLOBALS.Y_CURSOR + 5, PDF_GLOBALS.CONTENT_W - 10, 4, 'F');
                const barWidth = (parseFloat(statusInfo.width) / 100) * (PDF_GLOBALS.CONTENT_W - 10);
                doc.setFillColor(statusInfo.color);
                doc.rect(PDF_GLOBALS.MARGIN + 5, PDF_GLOBALS.Y_CURSOR + 5, barWidth, 4, 'F');
                PDF_GLOBALS.Y_CURSOR += 15;
            }
        }

        doc.setFontSize(10);
        fields.forEach(field => {
            if (field.isStatus) return;
            
            const label = field.label + ':';
            const value = formatValue(field.value(data), field.format);
            const splitValue = doc.splitTextToSize(value, PDF_GLOBALS.CONTENT_W - 65);
            
            checkPageBreak((splitValue.length * 5) + 3);

            doc.setFont('Helvetica', 'bold');
            doc.setTextColor(PDF_GLOBALS.COLOR_TEXT);
            doc.text(label, PDF_GLOBALS.MARGIN + 60, PDF_GLOBALS.Y_CURSOR, { align: 'right' });

            doc.setFont('Helvetica', 'normal');
            doc.setTextColor(PDF_GLOBALS.COLOR_MUTED);
            doc.text(splitValue, PDF_GLOBALS.MARGIN + 65, PDF_GLOBALS.Y_CURSOR);
            
            PDF_GLOBALS.Y_CURSOR += (splitValue.length * 5) + 3;
        });

        const cardHeight = PDF_GLOBALS.Y_CURSOR - startY;
        doc.setDrawColor(PDF_GLOBALS.COLOR_BORDER);
        doc.roundedRect(PDF_GLOBALS.MARGIN, startY, PDF_GLOBALS.CONTENT_W, cardHeight + 4, 3, 3, 'S');
        
        PDF_GLOBALS.Y_CURSOR += 10;
    }

    // --- 3. INICIAR LA CONSTRUCCIÓN DEL PDF ---

    addHeader();

    // Título del Reporte
    const mainEntityData = findNodeData(traceData, entityType, entityId);
    const entityCode = mainEntityData?.codigo || mainEntityData?.numero_lote || entityId;
    const reportTitle = `Informe de Trazabilidad`;
    checkPageBreak(20);
    doc.setFont('Helvetica', 'bold');
    doc.setFontSize(18);
    doc.setTextColor(PDF_GLOBALS.COLOR_TEXT);
    doc.text(reportTitle, PDF_GLOBALS.PAGE_W / 2, PDF_GLOBALS.Y_CURSOR, { align: 'center' });
    PDF_GLOBALS.Y_CURSOR += 8;
    doc.setFontSize(12);
    doc.setTextColor(PDF_GLOBALS.COLOR_MUTED);
    doc.text(`${formatEntityType(entityType)}: ${entityCode}`, PDF_GLOBALS.PAGE_W / 2, PDF_GLOBALS.Y_CURSOR, { align: 'center' });
    PDF_GLOBALS.Y_CURSOR += 15;

    // Resumen Ejecutivo
    checkPageBreak(30);
    doc.setFillColor('#f4f7fa');
    doc.setDrawColor(PDF_GLOBALS.COLOR_BORDER);
    doc.roundedRect(PDF_GLOBALS.MARGIN, PDF_GLOBALS.Y_CURSOR, PDF_GLOBALS.CONTENT_W, 25, 3, 3, 'FD');
    doc.setFont('Helvetica', 'bold');
    doc.setFontSize(14);
    doc.setTextColor(PDF_GLOBALS.COLOR_PRIMARY);
    doc.text('Resumen Ejecutivo', PDF_GLOBALS.MARGIN + 5, PDF_GLOBALS.Y_CURSOR + 8);
    doc.setFont('Helvetica', 'normal');
    doc.setFontSize(10);
    doc.setTextColor(PDF_GLOBALS.COLOR_TEXT);
    doc.text(`Entidad Principal: ${entityCode} (ID: ${entityId})`, PDF_GLOBALS.MARGIN + 5, PDF_GLOBALS.Y_CURSOR + 15);
    doc.text(`Entidades de Origen: ${traceData.resumen.origen.length} | Entidades de Destino: ${traceData.resumen.destino.length}`, PDF_GLOBALS.MARGIN + 5, PDF_GLOBALS.Y_CURSOR + 20);
    PDF_GLOBALS.Y_CURSOR += 35;

    // Entidad Principal
    drawSectionTitle('Información de Entidad Principal');
    drawDescriptionText(SECTION_DESCRIPTIONS.main);
    drawEntityCard(entityType, mainEntityData, traceData);
    
    // Diagrama
    drawSectionTitle('Diagrama de Trazabilidad');
    drawDescriptionText(SECTION_DESCRIPTIONS.diagram);
    if (diagramImage) {
        const imgProps = doc.getImageProperties(diagramImage);
        // Para tu pregunta "en grande": calculamos la altura para que ocupe todo el ancho
        const imgHeight = (PDF_GLOBALS.CONTENT_W * imgProps.height) / imgProps.width;
        checkPageBreak(imgHeight + 10);
        doc.addImage(diagramImage, 'PNG', PDF_GLOBALS.MARGIN, PDF_GLOBALS.Y_CURSOR, PDF_GLOBALS.CONTENT_W, imgHeight);
        PDF_GLOBALS.Y_CURSOR += imgHeight + 10;
    } else {
        checkPageBreak(10);
        doc.setFont('Helvetica', 'italic');
        doc.setFontSize(10);
        doc.setTextColor(PDF_GLOBALS.COLOR_MUTED);
        doc.text('Diagrama visual no disponible. (No se pudo capturar)', PDF_GLOBALS.MARGIN, PDF_GLOBALS.Y_CURSOR);
        PDF_GLOBALS.Y_CURSOR += 10;
    }

    // Secciones de Origen y Destino
    const sections = [
        { key: 'origen', title: 'Entidades de Origen (Hacia Atrás)', items: traceData.resumen.origen },
        { key: 'destino', title: 'Entidades de Destino (Hacia Adelante)', items: traceData.resumen.destino }
    ];

    const typeOrder = ['orden_compra', 'lote_insumo', 'orden_produccion', 'lote_producto', 'pedido'];

    for (const section of sections) {
        drawSectionTitle(section.title);
        drawDescriptionText(SECTION_DESCRIPTIONS[section.key]);
        
        if (!section.items || section.items.length === 0) {
            checkPageBreak(10);
            doc.setFont('Helvetica', 'italic');
            doc.setFontSize(10);
            doc.setTextColor(PDF_GLOBALS.COLOR_MUTED);
            doc.text('No se encontraron entidades para esta sección.', PDF_GLOBALS.MARGIN + 5, PDF_GLOBALS.Y_CURSOR);
            PDF_GLOBALS.Y_CURSOR += 10;
            continue;
        }

        const groupedItems = section.items.reduce((acc, item) => {
            (acc[item.tipo] = acc[item.tipo] || []).push(item);
            return acc;
        }, {});
        
        const sortedTypes = Object.keys(groupedItems).sort((a, b) => {
            let indexA = typeOrder.indexOf(a);
            let indexB = typeOrder.indexOf(b);
            return (indexA === -1 ? 99 : indexA) - (indexB === -1 ? 99 : indexB);
        });

        for (const type of sortedTypes) {
            const itemsOfType = groupedItems[type];
            let label = formatEntityType(type) + (itemsOfType.length > 1 ? 's' : '');
            drawCategorySubtitle(label);
            drawDescriptionText(CATEGORY_DESCRIPTIONS[type]);
            
            for (const item of itemsOfType) {
                const nodeData = findNodeData(traceData, item.tipo, item.id);
                drawEntityCard(item.tipo, nodeData, traceData);
            }
        }
    }

    // --- 4. FINALIZAR Y GUARDAR ---
    addFooter();
    doc.save(`Informe_Trazabilidad_${entityType}_${entityId}_${new Date().toISOString().split('T')[0]}.pdf`);
}