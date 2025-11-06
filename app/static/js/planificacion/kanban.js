document.addEventListener('DOMContentLoaded', function () {
    
    // ===== INICIALIZACIÓN =====
    console.log('📋 Tablero Kanban inicializado');
    
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
                // Mostrar solo órdenes del operario actual
                // Necesitas pasar el ID del operario actual desde el backend
                const operarioId = card.dataset.operario;
                show = operarioId && operarioId !== '';
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
        // --- Botón Aprobar Calidad ---
        if (e.target.matches('.btn-approve-quality') || e.target.closest('.btn-approve-quality')) {
            const button = e.target.closest('.btn-approve-quality');
            const opId = button.dataset.opId;
            
            if (!opId) return;

            // Deshabilitar botón para evitar doble clic
            button.disabled = true;
            button.innerHTML = '<i class="bi bi-hourglass-split"></i> Aprobando...';

            approveQualityCheck(opId, button);
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
    const initializeDragAndDrop = () => {
        document.querySelectorAll('.kanban-cards').forEach(container => {
            new Sortable(container, {
                group: 'kanban',
                animation: 150,
                ghostClass: 'sortable-ghost',
                dragClass: 'sortable-drag',
                onEnd: function(evt) {
                    const cardId = evt.item.dataset.opId;
                    const newColumn = evt.to.closest('.kanban-column').dataset.estado;
                    
                    console.log(`Orden ${cardId} movida a ${newColumn}`);
                    
                    // Aquí puedes hacer una llamada al backend para actualizar el estado
                    // updateOrderStatus(cardId, newColumn);
                }
            });
        });
    };
    
    // Descomentar para habilitar drag & drop
    // if (typeof Sortable !== 'undefined') {
    //     initializeDragAndDrop();
    // }
    
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