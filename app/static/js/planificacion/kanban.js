document.addEventListener('DOMContentLoaded', function () {
    
    // ===== INICIALIZACIÓN =====
    console.log('📋 Tablero Kanban inicializado');
    
    // ===== LÓGICA PARA COLAPSO DE COLUMNAS CON CONTROLES SUPERIORES =====
    const columnToggles = document.querySelectorAll('.column-toggle-checkbox');
    const toggleAllColumns = document.getElementById('toggle-all-columns');
    const columnWrappers = document.querySelectorAll('.kanban-column-wrapper');

    // Función para actualizar el estado de una columna
    const updateColumnState = (columnKey, isVisible) => {
        const columnWrapper = document.querySelector(`.kanban-column-wrapper[data-estado="${columnKey}"]`);
        if (columnWrapper) {
            if (isVisible) {
                columnWrapper.classList.remove('kanban-column-compressed');
            } else {
                columnWrapper.classList.add('kanban-column-compressed');
            }
        }
    };

    // Función para guardar el estado en localStorage
    const saveColumnStates = () => {
        const states = {};
        columnToggles.forEach(toggle => {
            states[toggle.dataset.columnKey] = toggle.checked;
        });
        localStorage.setItem('kanbanColumnStates', JSON.stringify(states));
    };

    // Función para cargar el estado desde localStorage
    const loadColumnStates = () => {
        const states = JSON.parse(localStorage.getItem('kanbanColumnStates'));
        if (states) {
            columnToggles.forEach(toggle => {
                const columnKey = toggle.dataset.columnKey;
                toggle.checked = states[columnKey] !== false; // Por defecto es true
                updateColumnState(columnKey, toggle.checked);
            });
            updateToggleAllState();
        }
    };

    // Función para actualizar el estado del checkbox "Todas"
    const updateToggleAllState = () => {
        const allChecked = Array.from(columnToggles).every(toggle => toggle.checked);
        toggleAllColumns.checked = allChecked;
    };

    // Event listener para los checkboxes individuales
    columnToggles.forEach(toggle => {
        toggle.addEventListener('change', () => {
            updateColumnState(toggle.dataset.columnKey, toggle.checked);
            saveColumnStates();
            updateToggleAllState();
        });
    });

    // Event listener para el checkbox "Todas"
    toggleAllColumns.addEventListener('change', () => {
        const isChecked = toggleAllColumns.checked;
        columnToggles.forEach(toggle => {
            toggle.checked = isChecked;
            updateColumnState(toggle.dataset.columnKey, isChecked);
        });
        saveColumnStates();
    });

    // Cargar estados al iniciar
    loadColumnStates();
    
    // ===== FILTROS =====
    const filterButtons = document.querySelectorAll('.filter-btn');
    const allCards = document.querySelectorAll('.kanban-card');
    
    filterButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            // Activar botón seleccionado
            filterButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            const filter = this.dataset.filter;
            applyFilter(filter);
        });
    });
    
    function applyFilter(filter) {
        let visibleCount = 0;
        
        allCards.forEach(card => {
            let show = true;
            
            if (filter === 'todas') {
                show = true;
            } else if (filter === 'mis-ordenes') {
                const operarioId = card.dataset.operario;
                const supervisorId = card.dataset.supervisorId;
                const creadorId = card.dataset.creadorId;
                const aprobadorId = card.dataset.aprobadorId;
                show = (operarioId && operarioId == CURRENT_USER_ID) ||
                       (supervisorId && supervisorId == CURRENT_USER_ID) ||
                       (creadorId && creadorId == CURRENT_USER_ID) ||
                       (aprobadorId && aprobadorId == CURRENT_USER_ID);
            } else if (filter === 'linea-1') {
                show = card.dataset.linea === '1';
            } else if (filter === 'linea-2') {
                show = card.dataset.linea === '2';
            } else if (filter === 'alta-prioridad') {
                show = card.dataset.prioridad === 'ALTA';
            } else if (filter === 'retrasadas') {
                show = card.classList.contains('card-retrasada');
            }
            
            if (show) {
                card.style.display = '';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });
        
        // Actualizar contadores de columnas
        updateColumnCounts();
        
        // Mostrar mensaje si no hay resultados
        showEmptyStateIfNeeded();
        
        console.log(`Filtro aplicado: ${filter} - ${visibleCount} tarjetas visibles`);
    }
    
    // ===== ACTUALIZAR CONTADORES =====
    function updateColumnCounts() {
        document.querySelectorAll('.kanban-column').forEach(column => {
            const estado = column.dataset.estado;
            const visibleCards = column.querySelectorAll('.kanban-card:not([style*="display: none"])');
            const badge = column.querySelector('.column-count-badge');
            
            if (badge) {
                badge.textContent = visibleCards.length;
            }
        });
    }
    
    // ===== MOSTRAR ESTADO VACÍO =====
    function showEmptyStateIfNeeded() {
        document.querySelectorAll('.kanban-cards').forEach(container => {
            const visibleCards = container.querySelectorAll('.kanban-card:not([style*="display: none"])');
            const emptyState = container.querySelector('.empty-state');
            
            if (visibleCards.length === 0 && !emptyState) {
                // Crear estado vacío si no existe
                const emptyDiv = document.createElement('div');
                emptyDiv.className = 'empty-state';
                emptyDiv.innerHTML = '<i class="bi bi-inbox"></i><p>Sin órdenes para este filtro</p>';
                container.appendChild(emptyDiv);
            } else if (visibleCards.length > 0 && emptyState) {
                // Remover estado vacío si hay tarjetas
                emptyState.remove();
            }
        });
    }
    
    // ===== HOVER EN CARDS (MOSTRAR MÁS INFO) =====
    allCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.zIndex = '10';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.zIndex = '1';
        });
    });
    
    // ===== ACCIONES DE TARJETA =====
    document.addEventListener('click', function(e) {
        if (e.target.matches('.btn-procesar-calidad') || e.target.closest('.btn-procesar-calidad')) {
            const button = e.target.closest('.btn-procesar-calidad');
            const opId = button.dataset.opId;
            if (opId) {
                openQualityControlModal(opId);
            }
        }
    });

    async function approveQualityCheck(opId, buttonElement) {
        try {
            const response = await fetch(`api/op/${opId}/aprobar-calidad`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const result = await response.json();

            if (result.success) {
                showNotification(`Orden ${opId} aprobada y completada.`, 'success');
                
                // Mover la tarjeta a la columna 'COMPLETADA'
                const card = buttonElement.closest('.kanban-card');
                const completedColumn = document.getElementById('kanban-cards-COMPLETADA');
                if (card && completedColumn) {
                    completedColumn.prepend(card); // Mover la tarjeta a la nueva columna.
                    
                    // Actualizar el botón para reflejar el estado completado.
                    buttonElement.innerHTML = '<i class="bi bi-check-circle-fill"></i> Aprobado';
                    buttonElement.disabled = true;

                    updateColumnCounts();
                }
            } else {
                showNotification(`Error: ${result.error || 'No se pudo aprobar la orden.'}`, 'error');
                buttonElement.disabled = false;
                buttonElement.innerHTML = '<i class="bi bi-check2-circle"></i> Aprobar';
            }
        } catch (error) {
            console.error('Error en la llamada API para aprobar calidad:', error);
            showNotification('Error de conexión al intentar aprobar.', 'error');
            buttonElement.disabled = false;
            buttonElement.innerHTML = '<i class="bi bi-check2-circle"></i> Aprobar';
        }
    }


    // ===== DRAG & DROP (OPCIONAL - REQUIERE SORTABLE.JS) =====
    // Si quieres habilitar arrastrar y soltar entre columnas
    // const initializeDragAndDrop = () => {
    //     document.querySelectorAll('.kanban-cards').forEach(container => {
    //         new Sortable(container, {
    //             group: 'kanban',
    //             animation: 150,
    //             ghostClass: 'sortable-ghost',
    //             dragClass: 'sortable-drag',
    //             onEnd: function(evt) {
    //                 const cardId = evt.item.dataset.opId;
    //                 const newColumn = evt.to.closest('.kanban-column').dataset.estado;
                    
    //                 console.log(`Orden ${cardId} movida a ${newColumn}`);
                    
    //                 if (newColumn === 'CONTROL_DE_CALIDAD') {
    //                     evt.from.appendChild(evt.item);
    //                     openQualityControlModal(cardId);
    //                 } else {
    //                     // updateOrderStatus(cardId, newColumn);
    //                 }
    //             }
    //         });
    //     });
    // };

    function openQualityControlModal(opId) {
        const card = document.querySelector(`.kanban-card[data-op-id="${opId}"]`);
        if (!card) return;

        const modal = new bootstrap.Modal(document.getElementById('modalControlCalidadOp'));
        
        const codigo = card.querySelector('.product-code').innerText;
        const producto = card.querySelector('.product-name').innerText;
        const cantidadProducida = card.dataset.cantidadProducida || '0';

        document.getElementById('op-codigo').innerText = codigo;
        document.getElementById('op-producto').innerText = producto;
        document.getElementById('op-cantidad-producida').innerText = cantidadProducida;
        document.getElementById('op-id').value = opId;
        
        const form = document.getElementById('form-control-calidad-op');
        form.reset();
        form.classList.remove('was-validated');

        // Disparar el evento change manualmente para aplicar la lógica inicial (ocultar/mostrar campos)
        // ya que "Aprobar lote completo" está preseleccionado.
        const event = new Event('change');
        const decisionSelect = document.getElementById('decision-inspeccion');
        if (decisionSelect) {
             decisionSelect.dispatchEvent(event);
        }

        modal.show();
    }

    const decisionSelect = document.getElementById('decision-inspeccion');
    if (decisionSelect) {
        decisionSelect.addEventListener('change', function() {
            const decision = this.value;
            const camposCantidades = document.getElementById('campos-cantidades');
            const campoRechazar = document.getElementById('campo-rechazar');
            const inputRechazar = document.getElementById('cantidad-rechazada');
            const campoCuarentena = document.getElementById('campo-cuarentena');
            const inputCuarentena = document.getElementById('cantidad-cuarentena');
            const containerMotivo = document.getElementById('container-motivo-inspeccion');

            // Resetear todo
            camposCantidades.style.display = 'none';
            campoRechazar.style.display = 'none';
            campoCuarentena.style.display = 'none';
            inputRechazar.required = false;
            inputRechazar.min = '';
            inputCuarentena.required = false;
            inputCuarentena.min = '';
            
            if (containerMotivo) {
                containerMotivo.style.display = 'none';
            }

            // Configurar según la decisión
            if (decision === 'APROBADO') {
                // No hacer nada, ya se ocultó todo arriba
            } else {
                // Mostrar motivo para cualquier opción que no sea APROBADO
                if (containerMotivo) {
                    containerMotivo.style.display = 'block';
                }

                if (decision === 'RECHAZO_PARCIAL') {
                    camposCantidades.style.display = 'block';
                    campoRechazar.style.display = 'block';
                    inputRechazar.required = true;
                    inputRechazar.min = '1';
                    inputRechazar.step = '1';
                } else if (decision === 'CUARENTENA_PARCIAL') {
                    camposCantidades.style.display = 'block';
                    campoCuarentena.style.display = 'block';
                    inputCuarentena.required = true;
                    inputCuarentena.min = '0.01';
                } else if (decision === 'MIXTO') {
                    camposCantidades.style.display = 'block';
                    campoRechazar.style.display = 'block';
                    campoCuarentena.style.display = 'block';
                    inputRechazar.required = true;
                    inputRechazar.min = '1';
                    inputRechazar.step = '1';
                    inputCuarentena.required = true;
                    inputCuarentena.min = '0.01';
                }
            }
        });
    }

    const btnProcesar = document.getElementById('btn-procesar-qc');
    if (btnProcesar) {
        btnProcesar.addEventListener('click', processQC);
    }

    async function processQC() {
        const opId = document.getElementById('op-id').value;
        const form = document.getElementById('form-control-calidad-op');

        // La validación ahora es manejada por checkValidity gracias a los atributos dinámicos.
        if (!form.checkValidity()) {
            form.classList.add('was-validated');
            // Opcional: mostrar una notificación general si se prefiere a los tooltips del navegador
            showNotification('Por favor, complete todos los campos requeridos.', 'warning');
            return;
        }
        form.classList.remove('was-validated');

        const formData = new FormData(form);
        const decision = formData.get('decision_inspeccion');
        formData.append('decision', decision);

        try {
            const response = await fetch(`/produccion/kanban/api/op/${opId}/procesar-calidad`, {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();

            if (result.success) {
                showNotification(result.message || 'Decisión de calidad procesada.', 'success');
                const modal = bootstrap.Modal.getInstance(document.getElementById('modalControlCalidadOp'));
                modal.hide();

                // Recargar la página para reflejar todos los cambios de estado y datos.
                window.location.reload();

                const card = document.querySelector(`.kanban-card[data-op-id="${opId}"]`);
                if (card) {
                    const cantidadProducida = parseFloat(document.getElementById('op-cantidad-producida').innerText);
                    const cantidadRechazada = parseFloat(formData.get('cantidad_rechazada') || 0);

                    if ((decision === 'RECHAZO_PARCIAL' || decision === 'MIXTO') && cantidadRechazada >= cantidadProducida) {
                        card.remove();
                    } else {
                        const completedColumn = document.getElementById('kanban-cards-COMPLETADA');
                        if (completedColumn) {
                            completedColumn.prepend(card);
                        }
                    }
                    updateColumnCounts();
                }
            } else {
                showNotification(`Error: ${result.error || 'No se pudo procesar la decisión.'}`, 'error');
            }
        } catch (error) {
            console.error('Error en la llamada API para procesar calidad:', error);
            showNotification('Error de conexión al intentar procesar la decisión.', 'error');
        }
    }
    
    // ===== BÚSQUEDA RÁPIDA (OPCIONAL) =====
    const createSearchBar = () => {
        const quickFilters = document.querySelector('.quick-filters');
        
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = '🔍 Buscar por código o producto...';
        searchInput.className = 'form-control form-control-sm';
        searchInput.style.width = '250px';
        searchInput.style.marginLeft = 'auto';
        
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            
            allCards.forEach(card => {
                const productName = card.querySelector('.product-name').textContent.toLowerCase();
                const productCode = card.querySelector('.product-code').textContent.toLowerCase();
                
                const matches = productName.includes(searchTerm) || productCode.includes(searchTerm);
                card.style.display = matches ? '' : 'none';
            });
            
            updateColumnCounts();
            showEmptyStateIfNeeded();
        });
        
        quickFilters.appendChild(searchInput);
    };
    
    // Descomentar para habilitar búsqueda
    // createSearchBar();
    
    // ===== NOTIFICACIONES (OPCIONAL) =====
    const showNotification = (message, type = 'info') => {
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
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            z-index: 10000;
            font-weight: 600;
            font-size: 14px;
            animation: slideInRight 0.3s ease;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    };
    
    // Agregar estilos de animación
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOutRight {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
        .sortable-ghost {
            opacity: 0.4;
            background: #f3f4f6;
        }
        .sortable-drag {
            opacity: 1;
            cursor: move;
        }
    `;
    document.head.appendChild(style);
    
    // ===== SHORTCUTS DE TECLADO (OPCIONAL) =====
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + 1-5 para cambiar filtros
        if ((e.ctrlKey || e.metaKey) && e.key >= '1' && e.key <= '6') {
            e.preventDefault();
            const buttons = Array.from(filterButtons);
            const index = parseInt(e.key) - 1;
            if (buttons[index]) {
                buttons[index].click();
            }
        }
    });
    
    console.log('✅ Tablero Kanban listo');
    console.log('💡 Atajos de teclado: Ctrl/Cmd + 1-6 para filtros rápidos');
});