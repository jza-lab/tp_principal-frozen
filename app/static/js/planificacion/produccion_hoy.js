document.addEventListener('DOMContentLoaded', function () {
    
    // INICIALIZACIÓN DE MODALES
    const modalIniciarOp = new bootstrap.Modal(document.getElementById('modalIniciarOp'));
    const modalReportarAvance = new bootstrap.Modal(document.getElementById('modalReportarAvance'));
    const modalPausarOrden = new bootstrap.Modal(document.getElementById('modalPausarOrden'));

    // FORMULARIOS
    const formIniciarOp = document.getElementById('formIniciarOp');
    const formReportarAvance = document.getElementById('formReportarAvance');
    const formPausarOrden = document.getElementById('formPausarOrden');

    // 1. INICIAR ORDEN DE PRODUCCIÓN
    document.querySelectorAll('.btn-iniciar-op').forEach(button => {
        button.addEventListener('click', function () {
            const opId = this.dataset.opId;
            const opSugerenciaLinea = this.dataset.opSugerenciaLinea;
            const card = this.closest('.kanban-card');
            const opCodigo = card.querySelector('.card-text code').textContent.trim();

            // Configurar modal
            document.getElementById('modal-op-id').value = opId;
            document.getElementById('modal-op-codigo').textContent = opCodigo;
            
            const selectLinea = document.getElementById('modal-linea-produccion');
            const sugerenciaText = document.getElementById('modal-linea-sugerida-text');

            // Mostrar línea sugerida si existe
            if (opSugerenciaLinea) {
                selectLinea.value = opSugerenciaLinea;
                sugerenciaText.innerHTML = `<i class="bi bi-info-circle me-1"></i>La línea sugerida por el sistema es: <strong>Línea ${opSugerenciaLinea}</strong>`;
                sugerenciaText.style.display = 'block';
            } else {
                sugerenciaText.style.display = 'none';
            }
            
            // Resetear checkboxes
            document.getElementById('check-materiales').checked = false;
            document.getElementById('check-limpieza').checked = false;
            document.getElementById('check-equipos').checked = false;
            
            modalIniciarOp.show();
        });
    });

    // Submit: Iniciar Orden
    formIniciarOp.addEventListener('submit', function (event) {
        event.preventDefault();
        
        const opId = document.getElementById('modal-op-id').value;
        const linea = document.getElementById('modal-linea-produccion').value;
        
        // Validar checkboxes
        const checkMateriales = document.getElementById('check-materiales').checked;
        const checkLimpieza = document.getElementById('check-limpieza').checked;
        const checkEquipos = document.getElementById('check-equipos').checked;
        
        if (!checkMateriales || !checkLimpieza || !checkEquipos) {
            showNotification('⚠️ Debe completar todas las verificaciones', 'warning');
            return;
        }
        
        // Llamada API
        fetch(`/ordenes/api/${opId}/iniciar-trabajo`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ linea: parseInt(linea) })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                modalIniciarOp.hide();
                showNotification('✅ Orden iniciada correctamente', 'success');
                
                // Recargar página después de 1 segundo
                setTimeout(() => location.reload(), 1000);
            } else {
                showNotification('❌ Error: ' + (data.error || 'Error desconocido'), 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('❌ Error de red al intentar iniciar la orden', 'error');
        });
    });

    // 2. REPORTAR AVANCE DE PRODUCCIÓN
    formReportarAvance.addEventListener('submit', function (event) {
        event.preventDefault();
        
        const opId = document.getElementById('modal-report-op-id').value;
        const cantidadProducida = parseFloat(document.getElementById('cantidad-producida').value);
        const cantidadDesperdicio = parseFloat(document.getElementById('cantidad-desperdicio').value) || 0;
        const motivoDesperdicio = document.getElementById('motivo-desperdicio').value;
        const observaciones = document.getElementById('observaciones').value;
        
        // Validación básica
        if (!cantidadProducida || cantidadProducida <= 0) {
            showNotification('⚠️ Debe ingresar una cantidad producida válida', 'warning');
            return;
        }
        
        if (cantidadDesperdicio > 0 && !motivoDesperdicio) {
            showNotification('⚠️ Debe seleccionar un motivo de desperdicio', 'warning');
            return;
        }
        
        // Llamada API (ajusta la ruta según tu backend)
        fetch(`/ordenes/api/${opId}/reportar-avance`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                cantidad_producida: cantidadProducida,
                cantidad_desperdicio: cantidadDesperdicio,
                motivo_desperdicio: motivoDesperdicio,
                observaciones: observaciones
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                modalReportarAvance.hide();
                showNotification('📊 Avance reportado exitosamente', 'success');
                
                // Resetear formulario
                formReportarAvance.reset();
                
                // Recargar página después de 1 segundo
                setTimeout(() => location.reload(), 1000);
            } else {
                showNotification('❌ Error: ' + (data.error || 'Error desconocido'), 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('❌ Error de red al reportar avance', 'error');
        });
    });

    // 3. PAUSAR ORDEN DE PRODUCCIÓN
    formPausarOrden.addEventListener('submit', function (event) {
        event.preventDefault();
        
        const opId = document.getElementById('modal-pause-op-id').value;
        const motivoPausa = document.getElementById('motivo-pausa').value;
        const detallesPausa = document.getElementById('detalles-pausa').value;
        
        // Validación
        if (!motivoPausa) {
            showNotification('⚠️ Debe seleccionar un motivo de pausa', 'warning');
            return;
        }
        
        // Llamada API (ajusta la ruta según tu backend)
        fetch(`/ordenes/api/${opId}/pausar`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                motivo: motivoPausa,
                detalles: detallesPausa
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                modalPausarOrden.hide();
                showNotification('⏸️ Orden pausada. Tiempo de inactividad registrado.', 'warning');
                
                // Resetear formulario
                formPausarOrden.reset();
                
                // Recargar página después de 1 segundo
                setTimeout(() => location.reload(), 1000);
            } else {
                showNotification('❌ Error: ' + (data.error || 'Error desconocido'), 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('❌ Error de red al pausar la orden', 'error');
        });
    });

    // 4. FILTROS RÁPIDOS
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            // Activar botón seleccionado
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            const filter = this.dataset.filter;
            const cards = document.querySelectorAll('.kanban-card');
            
            cards.forEach(card => {
                let show = true;
                
                if (filter === 'todas') {
                    show = true;
                } else if (filter === 'mis-ordenes') {
                    // Mostrar solo órdenes con el operario actual
                    show = card.querySelector('.bi-person-fill') !== null;
                } else if (filter === 'linea-1') {
                    show = card.dataset.linea === '1';
                } else if (filter === 'linea-2') {
                    show = card.dataset.linea === '2';
                } else if (filter === 'alta-prioridad') {
                    show = card.dataset.prioridad === 'ALTA';
                }
                
                card.style.display = show ? '' : 'none';
            });
            
            // Actualizar contadores de columnas
            updateColumnCounts();
        });
    });

    // 5. COMPRIMIR/EXPANDIR COLUMNAS
    document.querySelectorAll('.kanban-compress-toggle').forEach(button => {
        button.addEventListener('click', function (e) {
            e.stopPropagation();
            
            const estado = this.dataset.estadoKey;
            const columnWrapper = document.querySelector(`.kanban-column-wrapper[data-estado="${estado}"]`);
            
            if (columnWrapper) {
                columnWrapper.classList.toggle('kanban-column-compressed');
                
                const isCompressed = columnWrapper.classList.contains('kanban-column-compressed');
                this.title = isCompressed ? 'Expandir columna' : 'Comprimir columna';
                
                // Alternar iconos
                const icon1 = this.querySelector('.bi-chevron-bar-left');
                const icon2 = this.querySelector('.bi-chevron-bar-right');
                if (isCompressed) {
                    icon1.style.display = 'none';
                    icon2.style.display = 'inline';
                } else {
                    icon1.style.display = 'inline';
                    icon2.style.display = 'none';
                }
            }
        });
    });

    // 6. OCULTAR/MOSTRAR COLUMNAS
    const columnToggles = document.querySelectorAll('.kanban-column-toggle');
    const columnToggleList = document.getElementById('kanbanColumnToggleList');
    
    // Evitar que el menú se cierre al hacer clic en checkboxes
    if (columnToggleList) {
        columnToggleList.addEventListener('click', function (e) {
            e.stopPropagation();
        });
    }

    columnToggles.forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            const estado = this.value;
            const columnWrapper = document.querySelector(`.kanban-column-wrapper[data-estado="${estado}"]`);
            
            if (columnWrapper) {
                columnWrapper.style.display = this.checked ? '' : 'none';
            }
        });
    });

    // 7. FUNCIONES AUXILIARES
    // Actualizar contadores de tarjetas visibles en columnas
    function updateColumnCounts() {
        document.querySelectorAll('.kanban-column').forEach(column => {
            const estado = column.dataset.estado;
            const visibleCards = column.querySelectorAll('.kanban-card[style=""]').length + 
                                column.querySelectorAll('.kanban-card:not([style])').length;
            const badge = column.querySelector('.column-header-controls .badge');
            if (badge) {
                badge.textContent = visibleCards;
            }
        });
    }

    // Agregar animaciones CSS
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
});

// Mostrar modal de pausa (llamado desde HTML)
function pauseOrder(opId) {
    document.getElementById('modal-pause-op-id').value = opId;
    const modalPausarOrden = new bootstrap.Modal(document.getElementById('modalPausarOrden'));
    modalPausarOrden.show();
}

// Mostrar modal de reporte (llamado desde HTML)
function reportProgress(opId) {
    document.getElementById('modal-report-op-id').value = opId;
    const modalReportarAvance = new bootstrap.Modal(document.getElementById('modalReportarAvance'));
    modalReportarAvance.show();
}

// Mostrar notificaciones toast
function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#10b981' : (type === 'error' ? '#ef4444' : '#f59e0b')};
        color: white;
        padding: 14px 20px;
        border-radius: 8px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        z-index: 2000;
        font-weight: 500;
        font-size: 14px;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}