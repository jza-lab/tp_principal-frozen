window.addEventListener('pageshow', function(event) {
    // event.persisted es true si la página se restauró desde el BFCache
    if (event.persisted) {
        console.log('Página cargada desde BFCache. Forzando recarga para obtener datos frescos.');
        // Forzar una recarga completa desde el servidor
        window.location.reload();
    }
});

// --- ¡NUEVO! Variable para el modal de carga ---
let globalLoadingModal = null;

let popoverList = [];

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
        showNotificationModal(title, message); // Fallback a alert simple
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
    cancelBtn.style.display = 'inline-block';
    cancelBtn.disabled = false;


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


// --- ¡NUEVAS FUNCIONES HELPER (MODAL DE CARGA) ---
/**
 * Muestra el modal de "Procesando" global.
 */
function showGlobalLoading() {
    if (globalLoadingModal) {
        globalLoadingModal.show();
    } else {
        console.warn('Modal de carga #globalLoadingModal no encontrado o no inicializado.');
    }
}

/**
 * Oculta el modal de "Procesando" global.
 */
function hideGlobalLoading() {
    if (globalLoadingModal) {
        globalLoadingModal.hide();
    }
}
// --- FIN NUEVAS FUNCIONES ---


// --- ¡FUNCIÓN MODIFICADA! ---
/**
 * Envía la confirmación final para una OP multi-día.
 */
async function confirmarAsignacionLote(opIdConfirmar, asignacionesConfirmar, estadoActual = 'PENDIENTE') {
    
    // 1. MOSTRAR MODAL DE CARGA INMEDIATAMENTE
    showGlobalLoading();

    try {
        const endpointUrl = '/planificacion/api/confirmar-aprobacion'; 
        const body = {
            op_id: opIdConfirmar, 
            asignaciones: asignacionesConfirmar
        };
        
        const csrfToken = window.CSRF_TOKEN || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

        const confirmResponse = await fetch(endpointUrl, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': csrfToken 
            },
            body: JSON.stringify(body)
        });

        const confirmResult = await confirmResponse.json();

        // 2. OCULTAR MODAL DE CARGA (antes de mostrar el resultado)
        hideGlobalLoading();

        // 3. Mostrar modal de resultado
        if (confirmResult.success) {
            // --- ¡CAMBIO! Título y mensaje mejorados ---
            showFeedbackModal('¡Éxito!', confirmResult.message || "La operación se ha guardado correctamente.", 'success');
            setTimeout(() => window.location.reload(), 1500);
        } else {
            showFeedbackModal('Error al Confirmar', confirmResult.error || confirmResult.message, 'error');
        }
    } catch (confirmError) {
        // 4. OCULTAR MODAL DE CARGA (en caso de error)
        hideGlobalLoading();
        console.error("Error red al confirmar:", confirmError);
        showFeedbackModal('Error de Conexión', 'No se pudo confirmar la planificación.', 'error');
    }
}


// --- LÓGICAS AL CARGAR LA PÁGINA (ÚNICO DOMCONTENTLOADED) ---
document.addEventListener('DOMContentLoaded', function () {

    // --- ¡NUEVO! Inicializar el modal de carga ---
    const loadingModalEl = document.getElementById('globalLoadingModal');
    if (loadingModalEl) {
        globalLoadingModal = new bootstrap.Modal(loadingModalEl);
    }
    // --- FIN INICIALIZACIÓN ---

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
            
            // ¡MODIFICADO! Asegúrate de que 'popoverList' NO tenga 'const' o 'let'
            // para que llene la variable global.
            popoverList = [...popoverTriggerList].map(popoverTriggerEl => {
                return new bootstrap.Popover(popoverTriggerEl, {
                     sanitize: false,
                     trigger: 'click' // <-- ¡MODIFICADO! Vuelve a 'click'
                });
            });
            // --------------------------

            // --- ¡NUEVA SOLUCIÓN PARA SCROLL! ---
            // Añadir un listener al scroll de la ventana
            window.addEventListener('scroll', () => {
                // Iterar sobre todas las instancias de popover que creamos
                popoverList.forEach(popover => {
                    popover.hide(); // Ocultar cada popover
                });
            }, true); // 'true' captura el evento más rápido (fase de captura)
            // --- FIN NUEVA SOLUCIÓN ---
        
        } // --- Fin del if(planificador) ---


        // --- LÓGICA PARA FORZAR LA AUTO-PLANIFICACIÓN ---
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
                                    'Content-Type': 'application/json',
                                    'X-CSRF-TOKEN': window.CSRF_TOKEN
                                }
                            });

                            const result = await response.json();
                            hideLoadingSpinner(btnForzarPlanificacion, originalButtonText);

                            if (result.success) {
                                const resumen = result.data;
                                // 3. Formatear el resumen
                                let resumenHtml = `
                                    <p>La planificación automática ha finalizado.</p>
                                    <div class="list-group">
                                        <div class="list-group-item d-flex justify-content-between align-items-center list-group-item-success">
                                            OPs Planificadas
                                            <span class="badge bg-success rounded-pill">${resumen.total_planificadas}</span>
                                        </div>
                                        <div class="list-group-item d-flex justify-content-between align-items-center list-group-item-info">
                                            OCs Generadas
                                            <span class="badge bg-info rounded-pill">${resumen.total_oc_generadas}</span>
                                        </div>
                                        <div class="list-group-item d-flex justify-content-between align-items-center list-group-item-danger">
                                            Errores
                                            <span class="badge bg-danger rounded-pill">${resumen.total_errores}</span>
                                        </div>
                                    </div>
                                `;

                                if (resumen.total_errores > 0 && resumen.errores) {
                                    resumenHtml += '<h6 class="mt-3">Detalle de Errores:</h6><ul class="list-unstyled" style="font-size: 0.85rem; max-height: 150px; overflow-y: auto;">';
                                    resumen.errores.forEach(err => {
                                        resumenHtml += `<li class="text-danger mb-1"><i class="bi bi-x-circle me-1"></i>${err}</li>`;
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
        console.error("Error crítico en la inicialización del tablero:", e);
    }

    // ========================================================
    // === ¡AÑADE ESTE NUEVO BLOQUE DE CÓDIGO! ===
    // ========================================================
    const btnForzarVerificacion = document.getElementById('btn-forzar-verificacion-capacidad');
    if (btnForzarVerificacion) {
        btnForzarVerificacion.addEventListener('click', function() {
            
            showFeedbackModal(
                'Confirmar Verificación',
                '¿Desea revisar el plan de la semana ahora?\n\nEsto buscará conflictos en los próximos 7 días, como Órdenes de Producción que ya no caben en su día asignado.\n\nEs útil si acabas de bloquear una línea y quieres ver los problemas al instante.\n\n¿Desea continuar?',
                'confirm',
                async () => { // Callback de confirmación
                    // 1. Mostrar spinner global
                    showGlobalLoading(); 
                    
                    try {
                        // 2. Llamar a la API (esta vez SIN API Key, usa la cookie JWT)
                        const response = await fetch('/planificacion/api/ejecutar-adaptacion', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRF-TOKEN': window.CSRF_TOKEN 
                            }
                        });

                        const result = await response.json();
                        hideGlobalLoading(); // 3. Ocultar spinner

                        if (result.success) {
                            const data = result.data;
                            let msg = `Verificación completada.\n\nSe generaron <b>${data.issues_generados}</b> nuevos issues/notificaciones.\nSe encontraron <b>${data.errores}</b> errores.`;
                            
                            // 4. Mostrar éxito y preparar recarga
                            showFeedbackModal('Verificación Exitosa', msg, 'success');
                            
                            // Sobrescribir "Cerrar" para que recargue la página
                            const feedbackModal = document.getElementById('feedbackModal');
                            const closeBtn = feedbackModal.querySelector('#feedbackModalCancelBtn');
                            if(closeBtn) {
                                closeBtn.textContent = 'Aceptar y Recargar';
                                closeBtn.onclick = () => window.location.reload();
                            }
                        
                        } else {
                            // 5. Mostrar error
                            showFeedbackModal('Error en la Verificación', result.error || 'Ocurrió un error desconocido.', 'error');
                        }
                    } catch (error) {
                        hideGlobalLoading();
                        showFeedbackModal('Error de Conexión', 'No se pudo conectar con el servidor.', 'error');
                        console.error('Error al forzar la verificación adaptativa:', error);
                    }
                } // Fin callback
            ); // Fin showFeedbackModal
        });
    }
    // ========================================================
}); // Fin del DOMContentLoaded


// =======================================================
// --- LISTENER GLOBAL PARA BOTONES (MODALES) ---
// =======================================================
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
                botonConsolidarAprobar.innerHTML = '<i class="bi bi-check-lg"></i> Planificar ordenes consolidadas';
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
            const apiUrl = window.API_CONSOLIDAR_URL || '/planificacion/api/consolidar-y-aprobar';
            
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': window.CSRF_TOKEN
                },
                body: JSON.stringify({ op_ids: opIds, asignaciones: asignaciones }) 
            });
            const result = await response.json();
            
            // --- ¡LÓGICA CORREGIDA! (Misma que en Re-Planificar) ---
            
            if (response.status === 409 && result.error === 'SOBRECARGA_CAPACIDAD') { 
                showFeedbackModal(result.title || 'Sobrecarga Detectada', result.message + "\n\nElija otra fecha o línea.", 'warning');
                toggleModalLock(false); 
            
            } else if (response.status === 200 && (result.success || result.error === 'MULTI_DIA_CONFIRM' || result.error === 'LATE_CONFIRM')) {
                // Simulación OK. Ocultar modal de planificación
                if (modalInstance) modalInstance.hide();
                toggleModalLock(false); 
                
                const op_id_confirmar = result.op_id_confirmar;
                const asignaciones_confirmar = result.asignaciones_confirmar;
                const estado_actual = result.estado_actual;
                
                if (result.error === 'MULTI_DIA_CONFIRM' || result.error === 'LATE_CONFIRM') {
                    // Pedir confirmación al usuario
                    const modalTitle = result.title || ((result.error === 'LATE_CONFIRM') ? '⚠️ Confirmar Retraso' : 'Confirmación Multi-Día');
                    showFeedbackModal(
                        modalTitle,
                        result.message,
                        'confirm',
                        () => { 
                            confirmarAsignacionLote(op_id_confirmar, asignaciones_confirmar, estado_actual);
                        } 
                    );
                } else {
                    // Éxito simple, guardar directamente
                    confirmarAsignacionLote(op_id_confirmar, asignaciones_confirmar, estado_actual);
                }
                
            } else { 
                // Error desconocido
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
        // (Esta lógica es del DOMContentLoaded, no debería estar aquí, pero la dejamos por si acaso)
        // ... (código idéntico al del DOMContentLoaded) ...
    } // Fin if (botonCalcular)


    // --- BOTÓN DE REPLANIFICAR (abre modal #replanModal) ---
    // --- (¡BLOQUE MODIFICADO!) ---
    const replanBtn = e.target.closest('.btn-open-replan-modal');
    if (replanBtn) {
        e.stopPropagation(); 

        // Ocultar cualquier popover abierto
        const popoverElement = replanBtn.closest('.popover');
        if (popoverElement) {
            const trigger = document.querySelector(`[aria-describedby="${popoverElement.id}"]`);
            if (trigger) {
                const popoverInstance = bootstrap.Popover.getInstance(trigger);
                if (popoverInstance) {
                    popoverInstance.hide(); 
                }
            }
        }
        const popoverEl = bootstrap.Popover.getInstance(replanBtn.closest('[data-bs-toggle="popover"]'));
        if (popoverEl) popoverEl.hide();

        
        // --- INICIO: LEER *TODOS* LOS DATA ATTRIBUTES ---
        // Datos estándar de la OP
        const opId = replanBtn.dataset.opId;
        const codigo = replanBtn.dataset.opCodigo || '';
        const producto = replanBtn.dataset.opProducto || '';
        const cantidad = replanBtn.dataset.opCantidad || '';
        const linea = replanBtn.dataset.opLinea || '';
        const fechaInicio = replanBtn.dataset.opFechaInicio || ''; // Fecha original o JIT (depende del botón)
        const supervisor = replanBtn.dataset.opSupervisor || '';
        const operario = replanBtn.dataset.opOperario || '';

        // Nuevos atributos de sugerencia (leídos desde el botón)
        const tProdDias = parseInt(replanBtn.dataset.sugTProdDias || '0', 10);
        const tProcDias = parseInt(replanBtn.dataset.sugTProcDias || '0', 10);
        const stockOk = parseInt(replanBtn.dataset.sugStockOk || '0', 10) === 1;
        const fechaJit = replanBtn.dataset.sugFechaJit || '';
        const plazoTotal = tProdDias + tProcDias;
        // --- FIN: LEER DATA ATTRIBUTES ---


        // --- INICIO: POBLAR CAMPOS ESTÁNDAR ---
        document.getElementById('replan_op_id').value = opId;
        document.getElementById('replan_op_codigo').textContent = codigo;
        document.getElementById('replan_producto_nombre').textContent = producto;
        document.getElementById('replan_cantidad').textContent = cantidad;
        document.getElementById('replan_select_linea').value = linea || '1'; // Campo oculto
        document.getElementById('replan_select_supervisor').value = supervisor || ''; // Campo oculto
        document.getElementById('replan_select_operario').value = operario || ''; // Campo oculto
        // --- FIN: POBLAR CAMPOS ESTÁNDAR ---

        
        // --- INICIO: POBLAR NUEVA SECCIÓN DE SUGERENCIA ---
        const sugerenciaContainer = document.getElementById('replan_sugerencia_container');
        const sugerenciaBox = document.getElementById('replan_sugerencia_box');
        const fechaJitEl = document.getElementById('replan_sug_fecha_jit');
        const plazoTotalEl = document.getElementById('replan_sug_plazo_total');
        const tProdEl = document.getElementById('replan_sug_t_prod').querySelector('b');
        const tProcEl = document.getElementById('replan_sug_t_proc').querySelector('b');
        const stockStatusEl = document.getElementById('replan_sug_stock_status');

        if (plazoTotal > 0 || fechaJit) {
            fechaJitEl.textContent = fechaJit || 'N/D';
            plazoTotalEl.textContent = plazoTotal;
            tProdEl.textContent = tProdDias;
            tProcEl.textContent = tProcDias;

            if (stockOk) {
                stockStatusEl.textContent = 'Stock OK';
                sugerenciaBox.classList.remove('alert-warning');
                sugerenciaBox.classList.add('alert-success');
            } else {
                stockStatusEl.textContent = 'Stock Faltante';
                sugerenciaBox.classList.remove('alert-success');
                sugerenciaBox.classList.add('alert-warning');
            }
            sugerenciaContainer.style.display = 'block'; // Mostrar el contenedor
        } else {
            sugerenciaContainer.style.display = 'none'; // Ocultar si no hay datos
        }
        // --- FIN: POBLAR SECCIÓN SUGERENCIA ---


        // --- INICIO: POBLAR FECHA DE INICIO (CON LÓGICA JIT) ---
        const fechaInicioInput = document.getElementById('replan_input_fecha_inicio');
        // Usar la fecha JIT sugerida SI ESTÁ DISPONIBLE,
        // si no, usar la fecha de inicio actual de la OP
        if (fechaJit) {
            fechaInicioInput.value = fechaJit;
        } else if (fechaInicio) {
            // Asegurarse de que la fecha original tenga el formato YYYY-MM-DD
            fechaInicioInput.value = fechaInicio.split('T')[0].split(' ')[0];
        } else {
            fechaInicioInput.value = ''; // Dejar vacío si no hay nada
        }
        // --- FIN: POBLAR FECHA ---

        const replanModal = new bootstrap.Modal(document.getElementById('replanModal'));
        replanModal.show();
    }
    // --- FIN LÓGICA RE-PLANIFICAR ---

    
    // --- BOTÓN CONFIRMAR RE-PLANIFICACIÓN (¡CORREGIDO!) ---
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
            // 1. Llamar a la API de simulación
            const apiUrl = window.API_CONSOLIDAR_URL || '/planificacion/api/consolidar-y-aprobar';
            
            const response = await fetch(apiUrl, { 
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
            
            // --- INICIO DE LA LÓGICA CORREGIDA ---

            if (response.status === 409 && result.error === 'SOBRECARGA_CAPACIDAD') {
                // Caso 1: Sobrecarga. El servidor rechaza.
                showFeedbackModal(result.title || 'Sobrecarga Detectada', result.message, 'warning');
            
            } else if (response.status === 200 && (result.success || result.error === 'MULTI_DIA_CONFIRM' || result.error === 'LATE_CONFIRM' || result.error === 'MIN_QUANTITY_CONFIRM')) {
                // Caso 2: Simulación OK (Simple, Multi-día, o Tarde).
                // El servidor aprueba la simulación, ahora debemos ejecutar la confirmación.

                const op_id_confirmar = result.op_id_confirmar;
                const asignaciones_confirmar = result.asignaciones_confirmar;
                const estado_actual = result.estado_actual;

                if (result.error === 'MULTI_DIA_CONFIRM' || result.error === 'LATE_CONFIRM') {
                    // 2a: Es multi-día o tarde -> Pedir confirmación al usuario
                    const modalTitle = result.title || ((result.error === 'LATE_CONFIRM') ? '⚠️ Confirmar Retraso' : 'Confirmación Multi-Día');
                    
                    showFeedbackModal(modalTitle, result.message, 'confirm', () => {
                        // El usuario hizo clic en "Confirmar", ahora llamamos a la función de guardado
                        confirmarAsignacionLote(op_id_confirmar, asignaciones_confirmar, estado_actual);
                    });
                } else {
                    // 2b: Es un éxito simple (result.success == true)
                    // No necesitamos preguntar al usuario, solo guardar.
                    // Llamamos a la función de guardado directamente.
                    confirmarAsignacionLote(op_id_confirmar, asignaciones_confirmar, estado_actual);
                }

            } else {
                // Caso 3: Error desconocido
                showFeedbackModal('Error', result.error || 'No se pudo re-planificar la OP.', 'error');
            }
            // --- FIN DE LA LÓGICA CORREGIDA ---

        } catch (error) {
            const replanModal = bootstrap.Modal.getInstance(replanModalElement);
            if(replanModal) replanModal.hide();
            showFeedbackModal('Error de Red', `Error: ${error.message}`, 'error');
        } finally {
            hideLoadingSpinner(btnConfirmReplan, originalButtonText);
        }
    }
    // --- FIN DE LA CORRECION ---

    // --- ¡NUEVO! BOTÓN MARCAR ISSUE COMO VISTO (EN OFFVCANVAS) ---
    const btnMarcarVisto = e.target.closest('.btn-marcar-visto, .btn-aceptar-issue');
    if (btnMarcarVisto) {
        const issueId = btnMarcarVisto.dataset.issueId;
        const originalButtonText = btnMarcarVisto.innerHTML;
        showLoadingSpinner(btnMarcarVisto, '...'); // Usar '...' para un spinner pequeño

        try {
            // Asumimos que la ruta es esta (debes crearla en planificacion_routes.py)
            const response = await fetch(`/planificacion/api/resolver-issue/${issueId}`, {
                method: 'POST', // Usamos POST para acciones que cambian estado
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': window.CSRF_TOKEN
                }
            });

            const result = await response.json();
            
            if (result.success) {
                // --- INICIO DE LA CORRECCIÓN ---
                // Buscar el contenedor padre, ya sea en la lista o en la tabla
                const elementoAHide = btnMarcarVisto.closest('.list-group-item, tr'); 
                
                if (elementoAHide) {
                    // Ocultar el elemento (más rápido que recargar)
                    elementoAHide.style.opacity = '0';
                    setTimeout(() => {
                        elementoAHide.style.display = 'none';
                    }, 300); // Esperar a que termine la animación de fade-out
                } else {
                    // Fallback si no encuentra nada (raro), simplemente recarga
                    window.location.reload();
                }
                // --- FIN DE LA CORRECCIÓN ---

            } else {
                showFeedbackModal('Error', result.error || 'No se pudo archivar el aviso.', 'error');
                hideLoadingSpinner(btnMarcarVisto, originalButtonText);
            }
        } catch (error) {
            console.error('Error al marcar issue como visto:', error);
            showFeedbackModal('Error de Red', 'No se pudo conectar con el servidor.', 'error');
            hideLoadingSpinner(btnMarcarVisto, originalButtonText);
        }
    }
    // --- FIN DEL NUEVO BLOQUE ---

}); // Fin addEventListener 'click' en 'document'

// --- ¡NUEVO LISTENER GLOBAL PARA CERRAR POPOVERS AL HACER CLICK AFUERA! ---
document.addEventListener('click', function (e) {
    // Si la lista de popovers está vacía, no hacer nada
    if (popoverList.length === 0) return;

    // Comprobar si el click fue EN un trigger de popover
    // (un trigger es la card en la que hiciste clic)
    const clickedOnTrigger = e.target.closest('[data-bs-toggle="popover"]');
    
    // Si se hizo click en un trigger, la lógica 'click' de Bootstrap se encarga.
    // (Esto permite que el trigger abra/cierre el popover)
    if (clickedOnTrigger) {
        return;
    }

    // Comprobar si el click fue DENTRO de un popover
    // (ej. en el botón "Re-planificar" de adentro del popover)
    const clickedInPopover = e.target.closest('.popover');

    // Si se hizo click dentro de un popover, no lo cerramos.
    if (clickedInPopover) {
        return;
    }

    // Si el click fue AFUERA de un trigger Y AFUERA de un popover,
    // cerramos todos los popovers que estén abiertos.
    popoverList.forEach(popover => {
        popover.hide();
    });
});