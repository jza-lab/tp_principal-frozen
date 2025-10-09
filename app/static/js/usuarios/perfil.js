document.addEventListener('DOMContentLoaded', function() {
    const btnEditMode = document.getElementById('btn-edit-mode');
    const btnSaveChanges = document.getElementById('btn-save-changes');
    const btnCancelEdit = document.getElementById('btn-cancel-edit');
    const actionBarView = document.getElementById('action-bar-view');
    const actionBarEdit = document.getElementById('action-bar-edit');
    const profileContent = document.querySelector('.profile-content');
    const editForm = document.getElementById('edit-form');
    
    let originalValues = {};
    let isEditMode = false;

    // Datos del usuario para el formulario
    const userData = {
        nombre: "{{ usuario.nombre }}",
        apellido: "{{ usuario.apellido }}",
        cuil_cuit: "{{ usuario.cuil_cuit or '' }}",
        legajo: "{{ usuario.legajo or '' }}",
        email: "{{ usuario.email }}",
        telefono: "{{ usuario.telefono or '' }}",
        direccion: "{{ usuario.direccion_formateada or '' }}",
        rol_id: "{{ usuario.rol_id or '' }}",
        turno: "{{ usuario.turno or '' }}",
        fecha_ingreso: "{{ usuario.fecha_ingreso.strftime('%Y-%m-%d') if usuario.fecha_ingreso else '' }}"
    };

    // Activar modo edición
    btnEditMode.addEventListener('click', function() {
        enterEditMode();
    });

    // Guardar cambios
    btnSaveChanges.addEventListener('click', function() {
        saveChanges();
    });

    // Cancelar edición
    btnCancelEdit.addEventListener('click', function() {
        exitEditMode();
    });

    function enterEditMode() {
        isEditMode = true;
        
        // Cambiar barras de acción
        actionBarView.style.display = 'none';
        actionBarEdit.style.display = 'flex';
        
        // Agregar clase al perfil
        profileContent.classList.add('edit-mode');
        
        // Guardar valores originales y convertir a inputs
        document.querySelectorAll('.info-item[data-field]').forEach(item => {
            const field = item.dataset.field;
            const valueDiv = item.querySelector('.info-value');
            const originalValue = userData[field];
            
            originalValues[field] = originalValue;
            
            // Crear input según el tipo de campo
            let inputHTML = '';
            
            if (field === 'direccion') {
                inputHTML = `<textarea class="form-control-inline" name="${field}" rows="2">${originalValue}</textarea>`;
            } else if (field === 'rol_id') {
                inputHTML = `<select class="form-control-inline" name="${field}">
                    <option value="">Seleccionar rol</option>
                    <!-- Aquí deberías cargar los roles disponibles -->
                    <option value="{{ usuario.rol_id }}" selected>{{ usuario.roles.nombre if usuario.roles else 'Sin rol' }}</option>
                </select>`;
            } else if (field === 'turno') {
                inputHTML = `<select class="form-control-inline" name="${field}">
                    <option value="">Seleccionar turno</option>
                    <option value="Mañana" ${'selected' if usuario.turno == 'Mañana' else ''}>Mañana</option>
                    <option value="Tarde" ${'selected' if usuario.turno == 'Tarde' else ''}>Tarde</option>
                    <option value="Noche" ${'selected' if usuario.turno == 'Noche' else ''}>Noche</option>
                </select>`;
            } else if (field === 'fecha_ingreso') {
                inputHTML = `<input type="date" class="form-control-inline" name="${field}" value="${originalValue}">`;
            } else if (field === 'email') {
                inputHTML = `<input type="email" class="form-control-inline" name="${field}" value="${originalValue}" required>`;
            } else {
                inputHTML = `<input type="text" class="form-control-inline" name="${field}" value="${originalValue}">`;
            }
            
            valueDiv.innerHTML = inputHTML;
            valueDiv.classList.add('editing');
        });
        
        // Animación de entrada
        setTimeout(() => {
            document.querySelectorAll('.form-control-inline').forEach((input, index) => {
                input.style.animation = `slideInUp 0.3s ease-out ${index * 0.03}s backwards`;
            });
        }, 10);
    }

    function exitEditMode() {
        isEditMode = false;
        
        // Cambiar barras de acción
        actionBarView.style.display = 'flex';
        actionBarEdit.style.display = 'none';
        
        // Quitar clase del perfil
        profileContent.classList.remove('edit-mode');
        
        // Restaurar valores originales
        document.querySelectorAll('.info-item[data-field]').forEach(item => {
            const field = item.dataset.field;
            const valueDiv = item.querySelector('.info-value');
            const originalValue = originalValues[field];
            
            valueDiv.innerHTML = originalValue || 'No especificado';
            valueDiv.classList.remove('editing');
        });
        
        originalValues = {};
    }

    function saveChanges() {
        // Recopilar datos del formulario
        const formData = new FormData();
        
        document.querySelectorAll('.info-item[data-field]').forEach(item => {
            const field = item.dataset.field;
            const input = item.querySelector('.form-control-inline');
            if (input) {
                formData.append(field, input.value);
            }
        });
        
        // Mostrar loading en el botón
        const originalContent = btnSaveChanges.innerHTML;
        btnSaveChanges.disabled = true;
        btnSaveChanges.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
        
        // Enviar datos
        fetch("{{ url_for('admin_usuario.editar_usuario', id=usuario.id) }}", {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Mostrar mensaje de éxito
                showNotification('Cambios guardados exitosamente', 'success');
                
                // Actualizar valores en la vista
                document.querySelectorAll('.info-item[data-field]').forEach(item => {
                    const field = item.dataset.field;
                    const input = item.querySelector('.form-control-inline');
                    if (input) {
                        userData[field] = input.value;
                    }
                });
                
                // Salir del modo edición
                exitEditMode();
                
                // Recargar la página después de 1 segundo para reflejar todos los cambios
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                showNotification(data.message || 'Error al guardar los cambios', 'error');
                btnSaveChanges.disabled = false;
                btnSaveChanges.innerHTML = originalContent;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error al guardar los cambios', 'error');
            btnSaveChanges.disabled = false;
            btnSaveChanges.innerHTML = originalContent;
        });
        }

        function showNotification(message, type) {
            const notification = document.createElement('div');
            notification.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-notification`;
            notification.innerHTML = `
                <i class="bi bi-${type === 'success' ? 'check-circle' : 'exclamation-circle'} me-2"></i>
                ${message}
            `;
            
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.classList.add('show');
            }, 10);
            
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        }
    });

    function showDeactivateModal() {
        const modal = new bootstrap.Modal(document.getElementById('deactivateModal'));
        modal.show();
    }

