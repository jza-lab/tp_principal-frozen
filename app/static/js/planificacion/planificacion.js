/**
 * Mueve una OP a un nuevo estado (usada por Kanban).
 * @param {string} opId ID de la OP a mover.
 * @param {string} nuevoEstado Estado destino.
 * @returns {Promise<boolean>} True si tuvo éxito, False si falló.
 */
async function moverOp(opId, nuevoEstado) {
    try {
        const response = await fetch(`/tabla-produccion/api/mover-op/${opId}`, {
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

/**
 * Muestra un spinner en un botón y lo deshabilita.
 */
function showLoadingSpinner(button, text = 'Procesando...') {
    if (!button) return;
    button.disabled = true;
    button.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ${text}`;
}

/**
 * Oculta el spinner de un botón, lo habilita y restaura su texto.
 */
function hideLoadingSpinner(button, originalText) {
    if (!button) return;
    button.disabled = false;
    button.innerHTML = originalText;
}


/**
 * Envía la confirmación final para una OP multi-día.
 */
async function confirmarAsignacionLote(opIdConfirmar, asignacionesConfirmar, estadoActual = 'PENDIENTE') {
    try {
        const endpointUrl = '/planificacion/api/confirmar-aprobacion'; 
        const body = {
            op_id: opIdConfirmar, 
            asignaciones: asignacionesConfirmar
        };
        
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

        const confirmResponse = await fetch(endpointUrl, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': csrfToken 
            },
            body: JSON.stringify(body)
        });

        const confirmResult = await confirmResponse.json();
        if (confirmResult.success) {
            showFeedbackModal('Confirmado', confirmResult.message || "Lote planificado.", 'success');
            setTimeout(() => window.location.reload(), 1500);
        } else {
            showFeedbackModal('Error al Confirmar', confirmResult.error || confirmResult.message, 'error');
        }
    } catch (confirmError) {
        console.error("Error red al confirmar:", confirmError);
        showFeedbackModal('Error de Conexión', 'No se pudo confirmar la planificación.', 'error');
    }
}


// --- LÓGICAS AL CARGAR LA PÁGINA (ÚNICO DOMCONTENTLOADED) ---
document.addEventListener('DOMContentLoaded', function () {

    try {
        // --- LÓGICA DE DRAG-AND-DROP (KANBAN) ---
        const columns = document.querySelectorAll('.kanban-column');
        const planificador = document.getElementById('planificador-pendientes');

        if (planificador) {
            // Solo ejecutar la lógica del Kanban si el planificador existe
            console.log(`Kanban: Encontradas ${columns.length} columnas.`);
            
            columns.forEach((column, index) => {
                const cardContainer = column.querySelector('.kanban-cards');
                if (cardContainer) {
                    try { 
                        new Sortable(cardContainer, {
                            group: 'kanban', 
                            animation: 150, 
                            ghostClass: 'bg-primary-soft',
                            onMove: function (evt) { 
                                const fromState = evt.from.closest('.kanban-column').dataset.estado;
                                const toState = evt.to.closest('.kanban-column').dataset.estado;
                                const fromTitle = evt.from.closest('.kanban-column').querySelector('.kanban-title-text').textContent.trim();
                                const toTitle = evt.to.closest('.kanban-column').querySelector('.kanban-title-text').textContent.trim();
                                const operarioTransitions = {
                                    'LISTA PARA PRODUCIR': ['EN_LINEA_1', 'EN_LINEA_2'],
                                    'EN_LINEA_1': ['EN_EMPAQUETADO'],
                                    'EN_LINEA_2': ['EN_EMPAQUETADO'],
                                };
                                const supervisorCalidadTransitions = {
                                    'EN_EMPAQUETADO': ['CONTROL_DE_CALIDAD'],
                                    'CONTROL_DE_CALIDAD': ['COMPLETADA']
                                };
                                const supervisorTransitions = {
                                    'EN ESPERA': [],
                                    'LISTA PARA PRODUCIR': ['EN_LINEA_1', 'EN_LINEA_2'],
                                    'EN_LINEA_1': ['EN_EMPAQUETADO'],
                                    'EN_LINEA_2': ['EN_EMPAQUETADO'],
                                    'EN_EMPAQUETADO': ['CONTROL_DE_CALIDAD'],
                                    'CONTROL_DE_CALIDAD': ['COMPLETADA'],
                                    'COMPLETADA': []
                                };
                                let allowedTransitions;
                                if (typeof IS_OPERARIO !== 'undefined' && IS_OPERARIO) {
                                    allowedTransitions = operarioTransitions;
                                } else if (typeof IS_SUPERVISOR_CALIDAD !== 'undefined' && IS_SUPERVISOR_CALIDAD) {
                                    allowedTransitions = supervisorCalidadTransitions;
                                } else {
                                    allowedTransitions = supervisorTransitions;
                                }
                                if (!allowedTransitions[fromState] || !allowedTransitions[fromState].includes(toState)) { 
                                    showFeedbackModal('Movimiento No Permitido', `Su rol no le permite mover órdenes desde <strong>"${fromTitle}"</strong> hacia <strong>"${toTitle}"</strong>.`, 'warning');
                                    return false; 
                                }
                                if (fromState === 'LISTA PARA PRODUCIR' && (toState === 'EN_LINEA_1' || toState === 'EN_LINEA_2')) {
                                     const lineaAsignada = evt.dragged.dataset.lineaAsignada;
                                     const lineaDestino = toState === 'EN_LINEA_1' ? '1' : '2';
                                     if (!lineaAsignada) { 
                                         showFeedbackModal('Línea No Asignada', 'Esta OP no puede moverse a una línea de producción porque <strong>aún no tiene una línea asignada</strong>.\nPlanifíquela primero desde el "Plan Maestro".', 'error');
                                         return false; 
                                     }
                                     if (lineaAsignada !== lineaDestino) { 
                                         showFeedbackModal('Línea Incorrecta', `Esta OP está asignada a la <strong>Línea ${lineaAsignada}</strong> y no puede moverse a <strong>${toTitle}</strong>.`, 'warning');
                                         return false; 
                                     }
                                }
                                return true; 
                            },
                            onEnd: async function (evt) {
                                 if (evt.from === evt.to && evt.oldDraggableIndex === evt.newDraggableIndex) { return; }
                                 const item = evt.item; const toColumn = evt.to.closest('.kanban-column');
                                 if (!toColumn || !toColumn.dataset || !toColumn.dataset.estado) { return; }
                                 const opId = item.dataset.opId; const nuevoEstado = toColumn.dataset.estado;
                                 const success = await moverOp(opId, nuevoEstado);
                                 if (success) { window.location.reload(); } 
                            } 
                        });
                    } catch (error) {
                         console.error(`Kanban: Error al inicializar SortableJS en columna ${index+1}:`, error); 
                    }
                } else {
                     console.warn(`Kanban: No se encontró '.kanban-cards' en columna ${index+1}.`);
                }
            }); // Fin columns.forEach

            // --- INICIALIZAR POPOVERS ---
            const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
            const popoverList = [...popoverTriggerList].map(popoverTriggerEl => {
                return new bootstrap.Popover(popoverTriggerEl, {
                     sanitize: false
                });
            });
            // --------------------------
        
        } // --- Fin del if(planificador) ---


        // --- LÓGICA PARA FORZAR LA AUTO-PLANIFICACIÓN ---
        // (Movida aquí adentro)
        const btnForzarPlanificacion = document.getElementById('btn-forzar-auto-planificacion');
        if (btnForzarPlanificacion) {
            btnForzarPlanificacion.addEventListener('click', function () {
                
                // 1. Mostrar modal de confirmación
                showFeedbackModal(
                    'Confirmar Ejecución',
                    'Esto intentará planificar automáticamente todas las OPs pendientes. ¿Desea continuar?',
                    'confirm',
                    async () => { // 2. Callback de confirmación
                        const originalButtonText = btnForzarPlanificacion.innerHTML;
                        showLoadingSpinner(btnForzarPlanificacion, 'Planificando...');

                        try {
                            const response = await fetch('/planificacion/forzar_auto_planificacion', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                    // No CSRF token needed if blueprint is exempt
                                }
                            });

                            const result = await response.json();
                            hideLoadingSpinner(btnForzarPlanificacion, originalButtonText);

                            if (result.success) {
                                const resumen = result.data;
                                // 3. Formatear el resumen
                                let resumenHtml = `
                                    <p>La planificación automática ha finalizado.</p>
                                    <ul class="list-group">
                                        <li class="list-group-item d-flex justify-content-between align-items-center list-group-item-success">
                                            OPs Planificadas
                                            <span class="badge bg-success rounded-pill">${resumen.total_planificadas}</span>
                                        </li>
                                        <li class="list-group-item d-flex justify-content-between align-items-center list-group-item-info">
                                            OCs Generadas
                                            <span class="badge bg-info rounded-pill">${resumen.total_oc_generadas}</span>
                                        </li>
                                        <li class="list-group-item d-flex justify-content-between align-items-center list-group-item-danger">
                                            Errores
                                            <span class="badge bg-danger rounded-pill">${resumen.total_errores}</span>
                                        </li>
                                    </ul>
                                `;

                                if (resumen.total_errores > 0) {
                                    resumenHtml += '<h6 class="mt-3">Detalle de Errores:</h6><ul class="list-unstyled">';
                                    resumen.errores.forEach(err => {
                                        resumenHtml += `<li class="small text-danger"><i class="bi bi-x-circle me-1"></i>${err}</li>`;
                                    });
                                    resumenHtml += '</ul>';
                                }
                                
                                // 4. Mostrar resumen
                                 showFeedbackModal(
                                    'Planificación Finalizada',
                                    resumenHtml,
                                    'success'
                                );

                                 // Sobrescribir "Cerrar" para que recargue
                                 const feedbackModal = document.getElementById('feedbackModal');
                                 const closeBtn = feedbackModal.querySelector('#feedbackModalCancelBtn');
                                 if(closeBtn) {
                                     closeBtn.textContent = 'Aceptar y Recargar';
                                     closeBtn.onclick = () => window.location.reload();
                                 }

                            } else {
                                showFeedbackModal('Error en la Planificación', result.error || 'Ocurrió un error.', 'error');
                            }
                        } catch (error) {
                            hideLoadingSpinner(btnForzarPlanificacion, originalButtonText);
                            showFeedbackModal('Error de Conexión', 'No se pudo conectar con el servidor.', 'error');
                            console.error('Error al forzar la planificación automática:', error);
                        }
                    } // Fin callback
                ); // Fin showFeedbackModal
            });
        }
        // --- FIN LÓGICA FORZAR ---

    } catch (e) {
        // --- ¡¡FIN DE LA CORRECCIÓN!! ---
        // El 'catch' ahora cierra el 'try' de la línea 193
        console.error("Error crítico en la inicialización del tablero:", e);
    }
}); // Fin del DOMContentLoaded


// =======================================================
// --- LISTENER GLOBAL PARA BOTONES (INCLUYE MODALES) ---
// =======================================================
// (Este bloque está en el ámbito global, lo cual es correcto)
document.addEventListener('click', async function(e) {

    // --- BOTÓN CONSOLIDAR Y APROBAR (MODAL PLAN MAESTRO) ---
    const botonConsolidarAprobar = e.target.closest('.btn-consolidar-y-aprobar');
    if (botonConsolidarAprobar) {
        const modal = botonConsolidarAprobar.closest('.modal');
        if (!modal) { console.error("Modal no encontrada."); return; }

        const modalInstance = bootstrap.Modal.getInstance(modal);
        const closeButton = modal.querySelector('.btn-close');
        const cancelButton = modal.querySelector('.btn-secondary[data-bs-dismiss="modal"]');

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

        const toggleModalLock = (lock) => {
            if (lock) {
                botonConsolidarAprobar.disabled = true;
                botonConsolidarAprobar.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Verificando Capacidad...`;
                if (closeButton) closeButton.disabled = true;
                if (cancelButton) cancelButton.disabled = true;
                if (modalInstance) {
                    modalInstance._config.backdrop = 'static'; 
                    modalInstance._config.keyboard = false;   
                }
            } else {
                botonConsolidarAprobar.disabled = false;
                botonConsolidarAprobar.innerHTML = '<i class="bi bi-check-lg"></i> Consolidar y Aprobar Lote';
                if (closeButton) closeButton.disabled = false;
                if (cancelButton) cancelButton.disabled = false;
                if (modalInstance) {
                    modalInstance._config.backdrop = true; 
                    modalInstance._config.keyboard = true; 
                }
            }
        };
        
        toggleModalLock(true);

        try {
            const response = await fetch('/planificacion/api/consolidar-y-aprobar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ op_ids: opIds, asignaciones: asignaciones }) 
            });
            const result = await response.json();

            if (result.success) { 
                showFeedbackModal('Éxito', result.message || "Lote planificado con éxito.", 'success');
                setTimeout(() => window.location.reload(), 1500);
            }
            else if (result.error === 'SOBRECARGA_CAPACIDAD') { 
                showFeedbackModal('Sobrecarga Detectada', result.message + "\n\nElija otra fecha o línea.", 'warning');
                toggleModalLock(false); 
            }
            else if (result.error === 'MULTI_DIA_CONFIRM' || result.error === 'LATE_CONFIRM') { 
                toggleModalLock(false); 
                const modalTitle = (result.error === 'LATE_CONFIRM') ? '⚠️ Planificación Tarde' : 'Confirmación Multi-Día';
                showFeedbackModal(
                    modalTitle,
                    result.message,
                    'confirm',
                    () => { 
                        confirmarAsignacionLote(result.op_id_confirmar, result.asignaciones_confirmar, result.estado_actual);
                    } 
                );
            } else { 
                showFeedbackModal('Error', result.error || result.message || 'Error desconocido.', 'error');
                toggleModalLock(false); 
            }
        } catch (error) { 
            console.error("Error de red:", error);
            showFeedbackModal('Error de Conexión', 'No se pudo contactar al servidor.', 'error');
            toggleModalLock(false); 
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
                showFeedbackModal('Error al Calcular', result.error, 'error');
            }
        } catch (error) {
            console.error("Error al calcular sugerencia:", error);
            celdaSugerencia.innerHTML = 'Error de conexión.';
            celdaSugerencia.className = 'resultado-sugerencia mt-1 alert alert-danger';
            botonCalcular.disabled = false;
            botonCalcular.innerHTML = '<i class="bi bi-calculator-fill"></i> Calcular Ref.';
            showFeedbackModal('Error de Conexión', 'No se pudo calcular la sugerencia.', 'error');
        }
    } // Fin if (botonCalcular)


    // --- BOTÓN DE REPLANIFICAR (abre modal #replanModal) ---
    const replanBtn = e.target.closest('.btn-open-replan-modal');
    if (replanBtn) {

        e.stopPropagation(); // Evita que el clic cierre el popover (trigger='click')

        // 1. Encontrar el elemento flotante del popover
        const popoverElement = replanBtn.closest('.popover');
        if (popoverElement) {
            // 2. Obtener la instancia del Popover
            const popoverInstance = bootstrap.Popover.getInstance(popoverElement.previousElementSibling); // El activador está justo antes
            // O de forma más segura si el activador no es el hermano:
            // const popoverInstance = bootstrap.Popover.getInstance(document.querySelector(`[aria-describedby="${popoverElement.id}"]`));
            
            // Dado que el 'closest' en el original usa el activador: 
            const trigger = document.querySelector(`[aria-describedby="${popoverElement.id}"]`);
            if (trigger) {
                const popoverInstance = bootstrap.Popover.getInstance(trigger);
                if (popoverInstance) {
                    popoverInstance.hide(); // Cierra el popover
                }
            }
        }

        // Cerrar el popover activo
        const popoverEl = bootstrap.Popover.getInstance(replanBtn.closest('[data-bs-toggle="popover"]'));
        if (popoverEl) popoverEl.hide();

        // Tomar datos de la OP desde data-attributes
        const opId = replanBtn.dataset.opId;
        const codigo = replanBtn.dataset.opCodigo || '';
        const producto = replanBtn.dataset.opProducto || '';
        const cantidad = replanBtn.dataset.opCantidad || '';
        const linea = replanBtn.dataset.opLinea || '';
        const fechaInicio = replanBtn.dataset.opFechaInicio || '';
        const supervisor = replanBtn.dataset.opSupervisor || '';
        const operario = replanBtn.dataset.opOperario || '';

        // Cargar los datos en el modal
        document.getElementById('replan_op_id').value = opId;
        document.getElementById('replan_op_codigo').textContent = codigo;
        document.getElementById('replan_producto_nombre').textContent = producto;
        document.getElementById('replan_cantidad').textContent = cantidad;
        document.getElementById('replan_select_linea').value = linea || '1';
        document.getElementById('replan_input_fecha_inicio').value = fechaInicio || '';
        document.getElementById('replan_select_supervisor').value = supervisor || '';
        document.getElementById('replan_select_operario').value = operario || '';

        // Mostrar el modal
        const replanModal = new bootstrap.Modal(document.getElementById('replanModal'));
        replanModal.show();
    }
    // --- FIN LÓGICA RE-PLANIFICAR ---

    
    // --- ¡¡INICIO DE LA CORRECCIÓN!! ---
    // --- BOTÓN CONFIRMAR RE-PLANIFICACIÓN ---
    const btnConfirmReplan = e.target.closest('#btn-confirm-replan');
    if(btnConfirmReplan) {
        
        const replanModalElement = document.getElementById('replanModal');
        const opId = document.getElementById('replan_op_id').value;
        const linea = document.getElementById('replan_select_linea').value;
        const fechaInicio = document.getElementById('replan_input_fecha_inicio').value;
        const supervisor = document.getElementById('replan_select_supervisor').value;
        const operario = document.getElementById('replan_select_operario').value;

        if (!linea || !fechaInicio) {
            showFeedbackModal('Datos Faltantes', 'Debes seleccionar una línea y una fecha de inicio.', 'warning');
            return;
        }

        const asignaciones = {
            linea_asignada: parseInt(linea),
            fecha_inicio: fechaInicio,
            supervisor_id: supervisor ? parseInt(supervisor) : null,
            operario_id: operario ? parseInt(operario) : null
        };
        
        const originalButtonText = btnConfirmReplan.innerHTML;
        showLoadingSpinner(btnConfirmReplan, 'Re-planificando...');

        try {
            // ¡REUTILIZAMOS la lógica y la URL del Plan Maestro!
            
            // --- ¡CORRECCIÓN DE RUTA! ---
            // Usar las variables globales que definimos en el HTML
            const response = await fetch(window.API_CONSOLIDAR_URL, { 
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': window.CSRF_TOKEN
                },
                body: JSON.stringify({
                    op_ids: [parseInt(opId)], 
                    asignaciones: asignaciones
                })
            });

            const result = await response.json();
            const replanModal = bootstrap.Modal.getInstance(replanModalElement);
            if(replanModal) replanModal.hide();
            
            // Reutilizamos el 'feedbackModal'
            if (response.status === 409 && result.error === 'SOBRECARGA_CAPACIDAD') {
                showFeedbackModal('Sobrecarga Detectada', result.title || 'Sobrecarga', result.message);
            } else if (response.status === 200 && (result.error === 'MULTI_DIA_CONFIRM' || result.error === 'LATE_CONFIRM')) {
                const modalTitle = (result.error === 'LATE_CONFIRM') ? '⚠️ Planificación Tarde' : 'Confirmación Multi-Día';
                showFeedbackModal(modalTitle, result.message, 'confirm', () => {
                    // Reutiliza la lógica de confirmación
                    confirmarAsignacionLote(result.op_id_confirmar, result.asignaciones_confirmar, result.estado_actual);
                });
            } else if (response.status === 200 && result.success) {
                showFeedbackModal('¡Re-planificado!', 'La OP ha sido re-planificada exitosamente.', 'success');
                setTimeout(() => window.location.reload(), 1500); // Recargar para ver cambios
            } else {
                showFeedbackModal('Error', result.error || 'No se pudo re-planificar la OP.', 'error');
            }

        } catch (error) {
            const replanModal = bootstrap.Modal.getInstance(replanModalElement);
            if(replanModal) replanModal.hide();
            showFeedbackModal('Error de Red', `Error: ${error.message}`, 'error');
        } finally {
            hideLoadingSpinner(btnConfirmReplan, originalButtonText);
        }
    }
    // --- FIN DE LA CORRECCIÓN ---

}); // Fin addEventListener 'click' en 'document'