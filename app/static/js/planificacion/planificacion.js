document.addEventListener('DOMContentLoaded', function () {
    const selectAllCheckbox = document.getElementById('select-all-items');
    const itemCheckboxes = document.querySelectorAll('.item-checkbox');
    const createOrdersBtn = document.getElementById('create-orders-btn');
    const selectedCountSpan = document.getElementById('selected-count');
    const planificacionForm = document.getElementById('planificacion-form');

    // Función para actualizar el contador y el estado del botón
    function updateSelectionState() {
        const checkedCount = document.querySelectorAll('.item-checkbox:checked').length;
        
        // Actualizar contador
        if (selectedCountSpan) {
            selectedCountSpan.textContent = `${checkedCount} seleccionado${checkedCount !== 1 ? 's' : ''}`;
        }
        
        // Habilitar/deshabilitar botón
        if (createOrdersBtn) {
            createOrdersBtn.disabled = checkedCount === 0;
        }

        // Actualizar estado visual de las filas
        itemCheckboxes.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (checkbox.checked) {
                row.classList.add('selected');
            } else {
                row.classList.remove('selected');
            }
        });
    }

    // Select all functionality
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function () {
            itemCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            updateSelectionState();
        });
    }

    // Individual checkbox functionality
    itemCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            // Actualizar el checkbox de "Seleccionar todos"
            if (!this.checked) {
                if (selectAllCheckbox) selectAllCheckbox.checked = false;
            } else {
                const allChecked = Array.from(itemCheckboxes).every(c => c.checked);
                if (selectAllCheckbox && allChecked) {
                    selectAllCheckbox.checked = true;
                }
            }
            updateSelectionState();
        });
    });

    // Click en la fila para seleccionar
    const itemRows = document.querySelectorAll('.item-row');
    itemRows.forEach(row => {
        row.addEventListener('click', function(e) {
            // No hacer nada si se hizo click en el checkbox
            if (e.target.type === 'checkbox') return;
            
            const checkbox = this.querySelector('.item-checkbox');
            if (checkbox) {
                checkbox.checked = !checkbox.checked;
                checkbox.dispatchEvent(new Event('change'));
            }
        });
    });

    // Confirmación al enviar
    if (planificacionForm) {
        planificacionForm.addEventListener('submit', function(e) {
            e.preventDefault(); // Prevenir el envío por defecto para usar el modal

            const checkedCount = document.querySelectorAll('.item-checkbox:checked').length;
            
            if (checkedCount === 0) {
                showNotificationModal('Selección Requerida', 'Por favor, seleccione al menos un ítem para crear órdenes de producción.', 'warning');
                return;
            }

            const confirmMessage = `¿Está seguro de que desea crear órdenes de producción para los ${checkedCount} ítems seleccionados?`;
            
            // Usar el modal de confirmación genérico
            showConfirmationModal(
                'Confirmar Creación', 
                confirmMessage, 
                function() {
                    // Callback de confirmación: agregar estado de carga y enviar el formulario
                    if (createOrdersBtn) {
                        createOrdersBtn.disabled = true;
                        createOrdersBtn.classList.add('btn-loading');
                        createOrdersBtn.innerHTML = '<i class="bi bi-gear-fill me-2"></i>Creando órdenes...';
                    }
                    planificacionForm.submit(); // Enviar el formulario programáticamente
                },
                'success' // Usar un botón verde para la confirmación
            );
        });
    }

    // Inicializar estado
    updateSelectionState();
});
