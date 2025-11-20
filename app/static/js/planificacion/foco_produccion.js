document.addEventListener('DOMContentLoaded', function () {
    
    // ===== ELEMENTOS DEL DOM =====
    const focoContainer = document.getElementById('foco-container');
    const ordenId = focoContainer.dataset.opId;
    
    // Display elements
    const timerDisplay = document.getElementById('timer');
    const cantidadProducidaDisplay = document.getElementById('cantidad-producida');
    const cantidadDesperdicioDisplay = document.getElementById('cantidad-desperdicio');
    const ritmoActualDisplay = document.getElementById('ritmo-actual');
    const progressBar = document.getElementById('progress-bar');
    const porcentajeProgreso = document.getElementById('porcentaje-progreso');
    const oeeValue = document.getElementById('oee-value');
    const timerStatus = document.getElementById('timer-status');
    const statusBadge = document.getElementById('status-badge');
    const activityLog = document.getElementById('activity-log');
    const tiempoRestanteTurnoDisplay = document.getElementById('tiempo-restante-turno');
    
    // Overlay y modales
    const pauseOverlay = document.getElementById('pause-overlay');
    const motivoPausaActual = document.getElementById('motivo-pausa-actual');
    const tiempoPausaDisplay = document.getElementById('tiempo-pausa');
    
    // Botones
    const btnPausarReanudar = document.getElementById('btn-pausar-reanudar');
    const btnReportarAvance = document.getElementById('btn-reportar-avance');
    const btnConfirmarPausa = document.getElementById('btn-confirmar-pausa');
    const btnConfirmarReporte = document.getElementById('btn-confirmar-reporte');
    const btnReanudarOverlay = document.getElementById('btn-reanudar');
    
    // Formularios
    const cantidadMalaInput = document.getElementById('cantidad-mala');
    const motivoDesperdicioContainer = document.getElementById('motivo-desperdicio-container');
    const motivoDesperdicioSelect = document.getElementById('motivo-desperdicio');
    const motivoDesperdicioLabel = document.querySelector('label[for="motivo-desperdicio"]');
    const motivoParoSelect = document.getElementById('motivo-paro');
    const cantidadRestanteInfo = document.getElementById('cantidad-restante-info');

    
    // ===== ESTADO DE LA APLICACIÓN =====
    let estado = {
        // Cronómetro
        timerInterval: null,
        segundosTranscurridos: 0,
        segundosPausa: 0,
        pausaInterval: null,
        isPaused: false,
        
        // Producción
        cantidadProducida: parseFloat(cantidadProducidaDisplay.textContent) || 0,
        cantidadDesperdicio: ORDEN_TOTAL_DESPERDICIO || 0,
        cantidadPlanificada: ORDEN_CANTIDAD_PLANIFICADA,
        ritmoObjetivo: ORDEN_RITMO_OBJETIVO,
        
        // OEE
        disponibilidad: 100,
        rendimiento: 100,
        calidad: 100,
        oee: 100,
        
        // Historial
        inicioProduccion: ORDEN_FECHA_INICIO ? new Date(ORDEN_FECHA_INICIO) : new Date(),
        tiempoTotalPausas: 0
    };

    // Calcular segundos iniciales si la producción ya empezó
    if (ORDEN_FECHA_INICIO) {
        const ahora = new Date();
        const inicio = new Date(ORDEN_FECHA_INICIO);
        estado.segundosTranscurridos = Math.floor((ahora - inicio) / 1000);
    }

    // ===== FUNCIONES DE FORMATO =====
    function formatTime(seconds) {
        const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
        const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
        const s = (seconds % 60).toString().padStart(2, '0');
        return `${h}:${m}:${s}`;
    }

    function formatNumber(num, decimals = 1) {
        return Number(num).toFixed(decimals);
    }

    function actualizarTiempoRestanteTurno() {
        if (!TURNO_ACTUAL || !TURNO_ACTUAL.hora_fin) {
            tiempoRestanteTurnoDisplay.textContent = 'N/D';
            return;
        }
    
        const ahora = new Date();
        const finTurno = new Date();
        
        const parts = TURNO_ACTUAL.hora_fin.split(':');
        const horas = parseInt(parts[0], 10);
        const minutos = parseInt(parts[1], 10);
        const segundos = parseInt(parts[2] || 0, 10);

        if (isNaN(horas) || isNaN(minutos) || isNaN(segundos)) {
            tiempoRestanteTurnoDisplay.textContent = 'Error';
            console.error('Error al parsear la hora de fin de turno:', TURNO_ACTUAL.hora_fin);
            return;
        }
        
        finTurno.setHours(horas, minutos, segundos, 0);
    
        // Si la hora de fin ya pasó (ej. turno de mañana y es de tarde), no mostrar nada
        if (ahora > finTurno) {
            tiempoRestanteTurnoDisplay.textContent = 'Finalizado';
            return;
        }
    
        const diffMillis = finTurno - ahora;
        const diffHoras = Math.floor(diffMillis / 1000 / 3600);
        const diffMinutos = Math.floor((diffMillis / 1000 / 60) % 60);
    
        tiempoRestanteTurnoDisplay.textContent = `${diffHoras}h ${diffMinutos}min`;
    }

    // ===== CRONÓMETRO PRINCIPAL =====
    function startTimer() {
        if (estado.timerInterval) return;
        
        estado.timerInterval = setInterval(() => {
            estado.segundosTranscurridos++;
            timerDisplay.textContent = formatTime(estado.segundosTranscurridos);
            
            // Actualizar ritmo cada segundo
            actualizarRitmo();
            
            // Actualizar OEE cada 10 segundos
            if (estado.segundosTranscurridos % 10 === 0) {
                calcularOEE();
            }

            // Actualizar tiempo restante del turno cada 60 segundos
            if (estado.segundosTranscurridos % 60 === 0) {
                actualizarTiempoRestanteTurno();
            }
        }, 1000);
        
        timerStatus.textContent = 'Cronómetro activo';
        addActivityLog('Cronómetro iniciado', 'success');
    }

    function stopTimer() {
        if (estado.timerInterval) {
            clearInterval(estado.timerInterval);
            estado.timerInterval = null;
        }
        timerStatus.textContent = 'Cronómetro detenido';
    }

    // ===== CRONÓMETRO DE PAUSA =====
    function startPauseTimer() {
        if (estado.pausaInterval) return;
        
        estado.pausaInterval = setInterval(() => {
            estado.segundosPausa++;
            tiempoPausaDisplay.textContent = formatTime(estado.segundosPausa);
        }, 1000);
    }

    function stopPauseTimer() {
        if (estado.pausaInterval) {
            clearInterval(estado.pausaInterval);
            estado.pausaInterval = null;
        }
        estado.tiempoTotalPausas += estado.segundosPausa;
        estado.segundosPausa = 0;
    }

    // ===== GESTIÓN DE PAUSA/REANUDACIÓN =====
    function pausarProduccion(motivo = 'No especificado') {
        stopTimer();
        estado.isPaused = true;
        
        // Mostrar overlay
        pauseOverlay.style.display = 'flex';
        motivoPausaActual.textContent = motivo;
        startPauseTimer();
        
        // Cambiar botón
        btnPausarReanudar.innerHTML = '<i class="bi bi-play-fill"></i><span>Reanudar Trabajo</span>';
        btnPausarReanudar.classList.remove('btn-pausar');
        btnPausarReanudar.classList.add('btn-reanudar');
        
        // Deshabilitar reportar
        btnReportarAvance.disabled = true;
        btnReportarAvance.style.opacity = '0.5';
        btnReportarAvance.style.cursor = 'not-allowed';
        
        // Actualizar badge
        statusBadge.innerHTML = '<i class="bi bi-pause-circle-fill"></i> EN PAUSA';
        statusBadge.classList.remove('badge-active');
        statusBadge.classList.add('badge-paused');
        
        addActivityLog(`Producción pausada: ${motivo}`, 'warning');
    }

    function reanudarProduccion() {
        startTimer();
        estado.isPaused = false;
        
        // Ocultar overlay
        pauseOverlay.style.display = 'none';
        stopPauseTimer();
        
        // Restaurar botón
        btnPausarReanudar.innerHTML = '<i class="bi bi-pause-fill"></i><span>Pausar Trabajo</span>';
        btnPausarReanudar.classList.remove('btn-reanudar');
        btnPausarReanudar.classList.add('btn-pausar');
        
        // Habilitar reportar
        btnReportarAvance.disabled = false;
        btnReportarAvance.style.opacity = '1';
        btnReportarAvance.style.cursor = 'pointer';
        
        // Actualizar badge
        statusBadge.innerHTML = '<i class="bi bi-play-circle-fill"></i> EN PRODUCCIÓN';
        statusBadge.classList.remove('badge-paused');
        statusBadge.classList.add('badge-active');
        
        addActivityLog('Producción reanudada', 'success');
        calcularOEE(); // Recalcular OEE después de pausa
    }

    // ===== EVENT LISTENERS: PAUSAR/REANUDAR =====
    btnPausarReanudar.addEventListener('click', () => {
        if (!estado.isPaused) {
            // Mostrar modal para seleccionar motivo
            bootstrap.Modal.getOrCreateInstance(document.getElementById('modalPausarProduccion')).show();
        } else {
            // Reanudar directamente
            reanudarAPI();
        }
    });

    btnReanudarOverlay.addEventListener('click', () => {
        reanudarAPI();
    });

    btnConfirmarPausa.addEventListener('click', async (e) => {
        e.preventDefault();
        
        const motivoId = document.getElementById('motivo-paro').value;
        const motivoTexto = document.getElementById('motivo-paro').selectedOptions[0]?.text || 'No especificado';
        
        if (!motivoId) {
            showNotification('⚠️ Debe seleccionar un motivo de pausa', 'warning');
            return;
        }

        // --- LÓGICA DE BIFURCACIÓN ---
        if (motivoTexto.toLowerCase().includes('cambio de turno')) {
            // Delegar al nuevo módulo de traspaso
            bootstrap.Modal.getInstance(document.getElementById('modalPausarProduccion')).hide();
            if (window.abrirModalTraspaso) {
                window.abrirModalTraspaso();
            } else {
                showNotification('Error: Módulo de traspaso no cargado.', 'error');
            }
        } else {
            // Proceder con la pausa normal
            try {
                const responsePausa = await fetch(`/produccion/kanban/api/op/${ordenId}/pausar`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ motivo_id: motivoId })
                });

                const dataPausa = await responsePausa.json();
                
                if (responsePausa.ok && dataPausa.success) {
                    pausarProduccion(motivoTexto);
                    bootstrap.Modal.getInstance(document.getElementById('modalPausarProduccion')).hide();
                    showNotification('⏸️ Producción pausada correctamente', 'warning');
                } else {
                    showNotification(`❌ Error al pausar: ${dataPausa.error || 'Error desconocido'}`, 'error');
                }
            } catch (error) {
                showNotification('❌ Error de red al pausar la orden', 'error');
            }
        }
    });

    async function reanudarAPI() {
        try {
            const response = await fetch(`/produccion/kanban/api/op/${ordenId}/reanudar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();
            
            if (response.ok && data.success) {
                reanudarProduccion();
                showNotification('▶️ Producción reanudada correctamente', 'success');
            } else {
                showNotification('❌ Error al reanudar: ' + (data.error || 'Error desconocido'), 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            showNotification('❌ Error de red al reanudar la orden', 'error');
        }
    }

    // ===== REPORTAR AVANCE =====
    function actualizarRestanteModal() {
        const buenaReportada = parseFloat(document.getElementById('cantidad-buena').value) || 0;
        const malaReportada = parseFloat(cantidadMalaInput.value) || 0;
        const restante = estado.cantidadPlanificada - (estado.cantidadProducida + estado.cantidadDesperdicio + buenaReportada + malaReportada);
        cantidadRestanteInfo.textContent = `Restante: ${formatNumber(Math.max(0, restante), 2)} kg`;
    }

    btnReportarAvance.addEventListener('click', () => {
        actualizarRestanteModal(); // Calcular al abrir
    });

    document.getElementById('cantidad-buena').addEventListener('input', actualizarRestanteModal);
    cantidadMalaInput.addEventListener('input', () => {
        actualizarRestanteModal();
        const cantidadMala = parseFloat(cantidadMalaInput.value) || 0;
        const esRequerido = cantidadMala > 0;

        // 1. Controlar visibilidad del contenedor
        motivoDesperdicioContainer.style.display = esRequerido ? 'block' : 'none';
        
        // 2. Asignar/quitar el atributo 'required'
        motivoDesperdicioSelect.required = esRequerido;
        
        // 3. Añadir/quitar el asterisco rojo dinámicamente
        const asterisco = ' <span class="text-danger">*</span>';
        if (esRequerido && !motivoDesperdicioLabel.innerHTML.includes('*')) {
            motivoDesperdicioLabel.innerHTML += asterisco;
        } else if (!esRequerido) {
            motivoDesperdicioLabel.innerHTML = 'Motivo del Desperdicio';
        }

        // 4. Resetear el valor si se oculta para evitar enviar datos inválidos
        if (!esRequerido) {
            motivoDesperdicioSelect.value = '';
        }
    });

    async function enviarReporteAPI(payload) {
        try {
            const response = await fetch(`/produccion/kanban/api/op/${ordenId}/reportar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                body: JSON.stringify(payload)
            });
    
            const data = await response.json();
    
            if (response.ok && data.success) {
                showNotification(`✅ ${data.message}`, 'info');
    
                actualizarProduccion(payload.cantidad_buena, payload.cantidad_desperdicio);
    
                const form = document.getElementById('form-reportar');
                const modalInstance = bootstrap.Modal.getInstance(document.getElementById('modalReportarAvance'));
                
                if (modalInstance) {
                    modalInstance.hide();
                }
                form.reset();
    
                // Manejar acciones devueltas por el backend
                if (data.data?.op_hija_creada) {
                    // --- NUEVA LÓGICA CON MODAL ---
                    const modalElem = document.getElementById('modalConfirmacionHija');
                    const modalBody = document.getElementById('modalConfirmacionHijaBody');
                    const btnOk = document.getElementById('btnConfirmacionHijaOk');
                    
                    modalBody.textContent = data.message;

                    // Asegurar limpieza de botones previos
                    const btnCancel = modalElem.querySelector('.btn-secondary');
                    if (btnCancel) btnCancel.style.display = 'none';
                    btnOk.textContent = 'Aceptar';
                    
                    const modalInstance = new bootstrap.Modal(modalElem);
                    
                    btnOk.onclick = () => {
                        modalInstance.hide();
                        window.location.href = '/produccion/kanban/';
                    };
                    
                    modalInstance.show();
                    stopTimer();

                } else if (data.data?.accion === 'confirmar_ampliacion') {
                    // --- CASO: HAY STOCK Y SE REQUIERE CONFIRMACIÓN ---
                    const modalElem = document.getElementById('modalConfirmacionHija'); // Reusamos el modal genérico
                    const modalBody = document.getElementById('modalConfirmacionHijaBody');
                    const btnOk = document.getElementById('btnConfirmacionHijaOk');
                    
                    // Personalizamos el modal para confirmación (Aceptar/Cancelar)
                    modalBody.textContent = data.message;
                    btnOk.textContent = 'Sí, ampliar orden';
                    
                    // Clonar el botón para eliminar event listeners previos y limpiar comportamiento
                    const newBtnOk = btnOk.cloneNode(true);
                    btnOk.parentNode.replaceChild(newBtnOk, btnOk);
                    
                    // Añadir botón de cancelar si no existe
                    let btnCancel = modalElem.querySelector('.btn-secondary');
                    if (!btnCancel) {
                        btnCancel = document.createElement('button');
                        btnCancel.type = 'button';
                        btnCancel.className = 'btn btn-secondary me-2';
                        btnCancel.textContent = 'Cancelar';
                        // Insertar antes del botón OK
                        newBtnOk.parentNode.insertBefore(btnCancel, newBtnOk);
                    }
                    // Mostrar el botón cancelar (por si estaba oculto o reusado)
                    btnCancel.style.display = 'inline-block';
                    btnCancel.onclick = () => {
                         bootstrap.Modal.getInstance(modalElem).hide();
                    };

                    const modalInstance = new bootstrap.Modal(modalElem);
                    
                    newBtnOk.onclick = async () => {
                        modalInstance.hide();
                        try {
                            const respConfirm = await fetch(`/produccion/kanban/api/op/${ordenId}/confirmar-ampliacion`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ desperdicio_a_cubrir: data.data.desperdicio_a_cubrir })
                            });
                            const dataConfirm = await respConfirm.json();
                            
                            if (dataConfirm.success) {
                                showNotification(dataConfirm.message, 'success');
                                // Actualizar la meta visualmente
                                estado.cantidadPlanificada = dataConfirm.data.nueva_cantidad_planificada;
                                document.querySelector('.objetivo-cantidad').innerHTML = `${formatNumber(estado.cantidadPlanificada, 2)} <span class="objetivo-unidad">kg</span>`;
                                addActivityLog(`OP ampliada por desperdicio. Nueva meta: ${estado.cantidadPlanificada} kg.`, 'success');
                                // Recalcular progreso con la nueva meta
                                actualizarProduccion(0, 0);
                            } else {
                                showNotification(`Error: ${dataConfirm.error}`, 'error');
                            }
                        } catch (err) {
                            showNotification('Error de red al confirmar ampliación.', 'error');
                        }
                    };
                    
                    modalInstance.show();

                } else if (data.data?.accion === 'ampliar_op') {
                    // --- LÓGICA EXISTENTE ---
                    estado.cantidadPlanificada = data.data.nueva_cantidad_planificada;
                    document.querySelector('.objetivo-cantidad').innerHTML = `${formatNumber(estado.cantidadPlanificada, 2)} <span class="objetivo-unidad">kg</span>`;
                    addActivityLog(`OP ampliada. Nueva meta: ${estado.cantidadPlanificada} kg.`, 'info');

                } else if ((estado.cantidadProducida + estado.cantidadDesperdicio) >= estado.cantidadPlanificada) {
                    addActivityLog('Orden completada, pasando a C. Calidad', 'success');
                    stopTimer();
                    setTimeout(() => window.location.href = '/produccion/kanban/', 2500);
                } else {
                    addActivityLog(`Reportado: +${formatNumber(payload.cantidad_buena, 2)}kg OK, +${formatNumber(payload.cantidad_desperdicio, 2)}kg Desp.`, 'info');
                }
            } else {
                showNotification(`❌ Error: ${data.error || 'Error desconocido'}`, 'error');
            }
        } catch (error) {
            showNotification('❌ Error de red al reportar avance.', 'error');
        }
    }

    btnConfirmarReporte.addEventListener('click', (e) => {
        e.preventDefault();
        
        const cantidadBuena = parseFloat(document.getElementById('cantidad-buena').value) || 0;
        const cantidadMala = parseFloat(document.getElementById('cantidad-mala').value) || 0;
        const motivoDesperdicio = document.getElementById('motivo-desperdicio').value;
    
        // Validaciones básicas de entrada
        if (cantidadBuena < 0 || cantidadMala < 0) {
            showNotification('⚠️ Las cantidades no pueden ser negativas.', 'warning');
            return;
        }
        if (cantidadBuena === 0 && cantidadMala === 0) {
            showNotification('⚠️ Debe reportar una cantidad (producida o desperdicio).', 'warning');
            return;
        }
        if (cantidadMala > 0 && !motivoDesperdicio) {
            showNotification('⚠️ Debe seleccionar un motivo para el desperdicio.', 'warning');
            return;
        }
    
        const payload = {
            cantidad_buena: cantidadBuena,
            cantidad_desperdicio: cantidadMala,
            motivo_desperdicio_id: motivoDesperdicio,
        };

        enviarReporteAPI(payload);
    });

    // ===== ACTUALIZAR PRODUCCIÓN =====
    function actualizarProduccion(cantidadBuena, cantidadMala) {
        estado.cantidadProducida += cantidadBuena;
        estado.cantidadDesperdicio += cantidadMala;
        
        // Actualizar displays
        cantidadProducidaDisplay.innerHTML = `${formatNumber(estado.cantidadProducida)} <span class="progreso-unit">kg</span>`;
        cantidadDesperdicioDisplay.innerHTML = `${formatNumber(estado.cantidadDesperdicio)} <span class="progreso-unit">kg</span>`;
        
        // Actualizar progreso
        // Modificado: Solo la cantidad producida (OK) afecta la barra de progreso visual, según requerimiento
        const progreso = (estado.cantidadProducida / estado.cantidadPlanificada) * 100;
        progressBar.style.width = `${Math.min(progreso, 100)}%`;
        porcentajeProgreso.textContent = `${formatNumber(progreso, 0)}%`;
        
        // Recalcular OEE
        calcularOEE();
    }

    // ===== CALCULAR RITMO ACTUAL =====
    function actualizarRitmo() {
        if (estado.segundosTranscurridos <= 0) { // Mayor seguridad con <=
            ritmoActualDisplay.innerHTML = `0 <span class="progreso-unit">kg/h</span>`;
            return;
        }
        
        const horasTranscurridas = estado.segundosTranscurridos / 3600;
        const ritmoActual = estado.cantidadProducida / horasTranscurridas;
        
        // Asegurarse de que el ritmo no sea NaN si horasTranscurridas es 0
        ritmoActualDisplay.innerHTML = `${formatNumber(ritmoActual || 0)} <span class="progreso-unit">kg/h</span>`;
        
        // Colorear según rendimiento
        const card = ritmoActualDisplay.closest('.progreso-card');
        if (ritmoActual >= estado.ritmoObjetivo) {
            card.style.borderLeft = '4px solid #10b981';
        } else if (ritmoActual >= estado.ritmoObjetivo * 0.8) {
            card.style.borderLeft = '4px solid #f59e0b';
        } else {
            card.style.borderLeft = '4px solid #ef4444';
        }
    }

    // ===== CALCULAR OEE =====
    function calcularOEE() {
        // 1. DISPONIBILIDAD = Tiempo producción / Tiempo disponible
        const tiempoDisponible = estado.segundosTranscurridos + estado.tiempoTotalPausas;
        estado.disponibilidad = tiempoDisponible > 0 
            ? (estado.segundosTranscurridos / tiempoDisponible) * 100 
            : 100;
        
        // 2. RENDIMIENTO = Producción real / Producción teórica
        const horasTranscurridas = estado.segundosTranscurridos / 3600;
        const produccionTeorica = estado.ritmoObjetivo * horasTranscurridas;
        estado.rendimiento = produccionTeorica > 0 
            ? (estado.cantidadProducida / produccionTeorica) * 100 
            : 100;
        
        // Limitar rendimiento a 100% máximo
        estado.rendimiento = Math.min(estado.rendimiento, 100);
        
        // 3. CALIDAD = Cantidad buena / Cantidad total
        const cantidadTotal = estado.cantidadProducida + estado.cantidadDesperdicio;
        estado.calidad = cantidadTotal > 0 
            ? (estado.cantidadProducida / cantidadTotal) * 100 
            : 100;
        
        // 4. OEE = Disponibilidad × Rendimiento × Calidad
        estado.oee = (estado.disponibilidad * estado.rendimiento * estado.calidad) / 10000;
        
        // Actualizar UI
        actualizarOEEDisplay();
    }

    function actualizarOEEDisplay() {
        // OEE principal
        oeeValue.innerHTML = `${formatNumber(estado.oee, 0)}<span class="oee-percent">%</span>`;
        
        // Componentes OEE
        const componentes = [
            { selector: '.oee-component:nth-child(1)', valor: estado.disponibilidad, color: '#10b981' },
            { selector: '.oee-component:nth-child(2)', valor: estado.rendimiento, color: '#3b82f6' },
            { selector: '.oee-component:nth-child(3)', valor: estado.calidad, color: '#8b5cf6' }
        ];
        
        componentes.forEach(comp => {
            const element = document.querySelector(comp.selector);
            if (element) {
                const fill = element.querySelector('.oee-comp-fill');
                const value = element.querySelector('.oee-comp-value');
                fill.style.width = `${Math.min(comp.valor, 100)}%`;
                fill.style.background = comp.color;
                value.textContent = `${formatNumber(comp.valor, 0)}%`;
            }
        });
        
        // Colorear OEE según valor
        if (estado.oee >= 85) {
            oeeValue.style.color = '#065f46'; // Verde oscuro
        } else if (estado.oee >= 60) {
            oeeValue.style.color = '#92400e'; // Amarillo oscuro
        } else {
            oeeValue.style.color = '#991b1b'; // Rojo oscuro
        }
    }

    // ===== LOG DE ACTIVIDAD =====
    function addActivityLog(mensaje, tipo = 'info') {
        const now = new Date();
        const hora = now.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
        
        const iconos = {
            success: '<i class="bi bi-check-circle-fill text-success"></i>',
            warning: '<i class="bi bi-exclamation-triangle-fill text-warning"></i>',
            error: '<i class="bi bi-x-circle-fill text-danger"></i>',
            info: '<i class="bi bi-info-circle-fill text-primary"></i>'
        };
        
        const item = document.createElement('div');
        item.className = 'activity-item';
        item.innerHTML = `
            <div class="activity-time">${hora}</div>
            <div class="activity-desc">
                ${iconos[tipo] || iconos.info}
                ${mensaje}
            </div>
        `;
        
        activityLog.insertBefore(item, activityLog.firstChild);
        
        // Mantener solo los últimos 10
        while (activityLog.children.length > 10) {
            activityLog.removeChild(activityLog.lastChild);
        }
    }

    // ===== NOTIFICACIONES TOAST =====
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6'
        };
        
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${colors[type] || colors.info};
            color: white;
            padding: 16px 24px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            z-index: 10000;
            font-weight: 600;
            font-size: 15px;
            animation: slideIn 0.3s ease;
            min-width: 300px;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 4000);
    }

    // ===== ANIMACIONES CSS =====
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);

    // ===== INICIALIZACIÓN =====
    async function inicializarVista() {
        // Inicializar displays a 0 para evitar NaN visualmente
        timerDisplay.textContent = formatTime(0);
        ritmoActualDisplay.innerHTML = `0 <span class="progreso-unit">kg/h</span>`;

        console.log("Diagnóstico de Motivos de Pausa:", MOTIVOS_PARO);
        popularSelects();
    
        try {
            // Primero, iniciar el cronómetro en el backend.
            await fetch(`/produccion/kanban/api/op/${ordenId}/cronometro/iniciar`, { method: 'POST' });

            const response = await fetch(`/produccion/kanban/api/op/${ordenId}/estado`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
    
            if (data.success) {
                const estadoServidor = data.data;
                
                // Actualizar estado local con datos del servidor
                estado.segundosTranscurridos = estadoServidor.tiempo_trabajado || 0;
                estado.cantidadProducida = parseFloat(estadoServidor.cantidad_producida) || 0;
                
                // Actualizar la UI inmediatamente con los datos del servidor
                timerDisplay.textContent = formatTime(estado.segundosTranscurridos);
                actualizarProduccion(0, 0); // Refresca la UI sin sumar nada
                actualizarRitmo(); // Calcular ritmo inicial
    
                if (estadoServidor.estado_actual === 'PAUSADA') {
                    const ultimoMotivo = "Pausa activa"; // Esto podría mejorarse obteniendo el motivo real
                    pausarProduccion(ultimoMotivo); 
                } else {
                    startTimer();
                }
    
            } else {
                showNotification('⚠️ No se pudo cargar el estado actual. Se iniciará de cero.', 'warning');
                startTimer();
            }
        } catch (error) {
            console.error('Error al inicializar el estado:', error);
            showNotification('❌ Error de red al cargar estado. Se iniciará de cero.', 'error');
            startTimer();
        }
    
        calcularOEE();
        console.log('✅ Sistema MES de producción inicializado correctamente');
        actualizarTiempoRestanteTurno(); // Llamada inicial
    }
    
    function popularSelects() {
        // Popular motivos de paro
        if (typeof MOTIVOS_PARO !== 'undefined' && MOTIVOS_PARO.length > 0) {
            motivoParoSelect.innerHTML = '<option value="" disabled selected>-- Elegir un motivo --</option>';
            MOTIVOS_PARO.forEach(motivo => {
                const option = document.createElement('option');
                option.value = motivo.id;
                option.textContent = motivo.descripcion;
                motivoParoSelect.appendChild(option);
            });
        }

        // Popular motivos de desperdicio (si es necesario)
        if (typeof MOTIVOS_DESPERDICIO !== 'undefined' && MOTIVOS_DESPERDICIO.length > 0) {
            motivoDesperdicioSelect.innerHTML = '<option value="" disabled selected>-- Elegir un motivo --</option>';
            MOTIVOS_DESPERDICIO.forEach(motivo => {
                const option = document.createElement('option');
                option.value = motivo.id;
                option.textContent = motivo.descripcion;
                motivoDesperdicioSelect.appendChild(option);
            });
        }
    }

    inicializarVista();
});