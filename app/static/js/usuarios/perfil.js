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

    // Datos del usuario (estos se deben pasar desde el template)
    const userData = window.userData || {};

    // Configuración de campos editables
    const fieldConfig = {
        nombre: { type: 'text', required: true, label: 'Nombre' },
        apellido: { type: 'text', required: true, label: 'Apellido' },
        cuil_cuit: { type: 'text', required: false, label: 'CUIL/CUIT', pattern: '[0-9]{2}-[0-9]{8}-[0-9]{1}' },
        legajo: { type: 'text', required: false, label: 'Legajo' },
        email: { type: 'email', required: true, label: 'Email' },
        telefono: { type: 'tel', required: false, label: 'Teléfono' },
        direccion: { type: 'textarea', required: false, label: 'Dirección' },
        rol_id: { type: 'select', required: false, label: 'Rol' },
        turno: { type: 'select', required: false, label: 'Turno' },
        fecha_ingreso: { type: 'date', required: false, label: 'Fecha de Ingreso' }
    };

    if (btnEditMode) {
        btnEditMode.addEventListener('click', handleEnterEditMode);
    }

    if (btnSaveChanges) {
        btnSaveChanges.addEventListener('click', handleSaveChanges);
    }

    if (btnCancelEdit) {
        btnCancelEdit.addEventListener('click', handleCancelEdit);
    }

    // Detectar teclas ESC para cancelar y Ctrl+S para guardar
    document.addEventListener('keydown', function(e) {
        if (isEditMode) {
            // ESC para cancelar
            if (e.key === 'Escape') {
                e.preventDefault();
                handleCancelEdit();
            }
            // Ctrl+S o Cmd+S para guardar
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                handleSaveChanges();
            }
        }
    });

    function handleEnterEditMode() {
        isEditMode = true;
        
        // Cambiar barras de acción con animación
        actionBarView.style.opacity = '0';
        setTimeout(() => {
            actionBarView.style.display = 'none';
            actionBarEdit.style.display = 'flex';
            actionBarEdit.style.opacity = '0';
            setTimeout(() => {
                actionBarEdit.style.opacity = '1';
            }, 10);
        }, 300);
        
        // Agregar clase al perfil
        profileContent.classList.add('edit-mode');
        
        // Guardar valores originales y convertir a inputs
        convertFieldsToInputs();
        
        setTimeout(() => {
            const firstInput = profileContent.querySelector('.form-control-inline');
            if (firstInput) firstInput.focus();
        }, 400);
    }

    function convertFieldsToInputs() {
        document.querySelectorAll('.info-item[data-field]').forEach((item, index) => {
            const field = item.dataset.field;
            const valueDiv = item.querySelector('.info-value');
            const config = fieldConfig[field];
            
            if (!config) return;
            
            const originalValue = userData[field] || '';
            originalValues[field] = originalValue;
            
            // Crear input según el tipo de campo
            let inputHTML = createInputHTML(field, originalValue, config);
            
            valueDiv.innerHTML = inputHTML;
            valueDiv.classList.add('editing');
            
            // Aplicar animación de entrada con delay
            setTimeout(() => {
                const input = valueDiv.querySelector('.form-control-inline');
                if (input) {
                    input.style.animation = `slideInUp 0.3s ease-out ${index * 0.03}s backwards`;
                }
            }, 10);
        });
    }

    function createInputHTML(field, value, config) {
        const commonAttrs = `
            class="form-control-inline" 
            name="${field}" 
            ${config.required ? 'required' : ''}
            ${config.pattern ? `pattern="${config.pattern}"` : ''}
        `;

        switch (config.type) {
            case 'textarea':
                return `<textarea ${commonAttrs} rows="3" placeholder="Ingrese ${config.label.toLowerCase()}">${value}</textarea>`;
            
            case 'select':
                return createSelectHTML(field, value, commonAttrs);
            
            case 'date':
                return `<input type="date" ${commonAttrs} value="${value}">`;
            
            case 'email':
                return `<input type="email" ${commonAttrs} value="${value}" placeholder="correo@ejemplo.com">`;
            
            case 'tel':
                return `<input type="tel" ${commonAttrs} value="${value}" placeholder="Ingrese teléfono">`;
            
            default:
                return `<input type="text" ${commonAttrs} value="${value}" placeholder="Ingrese ${config.label.toLowerCase()}">`;
        }
    }

    function createSelectHTML(field, value, commonAttrs) {
        if (field === 'rol_id') {
            // Los roles deben venir del backend
            const roles = window.rolesDisponibles || [];
            let options = '<option value="">Seleccionar rol</option>';
            roles.forEach(rol => {
                const selected = rol.id == value ? 'selected' : '';
                options += `<option value="${rol.id}" ${selected}>${rol.nombre}</option>`;
            });
            return `<select ${commonAttrs}>${options}</select>`;
        }
        
        if (field === 'turno') {
            const turnos = ['Mañana', 'Tarde', 'Noche'];
            let options = '<option value="">Seleccionar turno</option>';
            turnos.forEach(turno => {
                const selected = turno === value ? 'selected' : '';
                options += `<option value="${turno}" ${selected}>${turno}</option>`;
            });
            return `<select ${commonAttrs}>${options}</select>`;
        }
        
        return `<input type="text" ${commonAttrs} value="${value}">`;
    }

    function handleCancelEdit() {
        if (!confirm('¿Está seguro que desea cancelar los cambios?')) {
            return;
        }
        
        exitEditMode();
    }

    function exitEditMode() {
        isEditMode = false;
        
        // Cambiar barras de acción con animación
        actionBarEdit.style.opacity = '0';
        setTimeout(() => {
            actionBarEdit.style.display = 'none';
            actionBarView.style.display = 'flex';
            actionBarView.style.opacity = '0';
            setTimeout(() => {
                actionBarView.style.opacity = '1';
            }, 10);
        }, 300);
        
        // Quitar clase del perfil
        profileContent.classList.remove('edit-mode');
        
        // Restaurar valores originales
        restoreOriginalValues();
        
        originalValues = {};
    }

    function restoreOriginalValues() {
        document.querySelectorAll('.info-item[data-field]').forEach(item => {
            const field = item.dataset.field;
            const valueDiv = item.querySelector('.info-value');
            let originalValue = originalValues[field];
            
            // Si es un valor vacío, mostrar "No especificado"
            if (!originalValue || originalValue === '') {
                originalValue = 'No especificado';
            }
            
            // Para campos especiales, formatear el valor
            if (field === 'fecha_ingreso' && originalValue !== 'No especificado') {
                originalValue = formatDate(originalValue);
            }
            
            valueDiv.innerHTML = originalValue;
            valueDiv.classList.remove('editing');
        });
    }

    function handleSaveChanges() {
        // Validar formulario
        if (!validateForm()) {
            showNotification('Por favor, complete todos los campos requeridos correctamente', 'error');
            return;
        }
        
        // Recopilar datos del formulario
        const formData = new FormData();
        let hasChanges = false;
        
        document.querySelectorAll('.info-item[data-field]').forEach(item => {
            const field = item.dataset.field;
            const input = item.querySelector('.form-control-inline');
            
            if (input) {
                const newValue = input.value.trim();
                const oldValue = originalValues[field] || '';
                
                // Verificar si hay cambios
                if (newValue !== oldValue) {
                    hasChanges = true;
                }
                
                formData.append(field, newValue);
            }
        });
        
        // Si no hay cambios, salir del modo edición
        if (!hasChanges) {
            showNotification('No se detectaron cambios', 'info');
            exitEditMode();
            return;
        }
        
        // Mostrar loading en el botón
        const originalContent = btnSaveChanges.innerHTML;
        btnSaveChanges.disabled = true;
        btnSaveChanges.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
        
        // Obtener la URL de edición desde el botón o un data attribute
        const editUrl = btnSaveChanges.dataset.url || window.location.href.replace('/ver/', '/editar/');
        
        // Enviar datos
        fetch(editUrl, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Error en la respuesta del servidor');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Actualizar valores en memoria
                document.querySelectorAll('.info-item[data-field]').forEach(item => {
                    const field = item.dataset.field;
                    const input = item.querySelector('.form-control-inline');
                    if (input) {
                        userData[field] = input.value.trim();
                    }
                });
                
                // Mostrar mensaje de éxito
                showNotification('Cambios guardados exitosamente', 'success');
                
                // Salir del modo edición
                exitEditMode();
                
                // Recargar después de un momento para reflejar todos los cambios
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                throw new Error(data.message || 'Error al guardar los cambios');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification(error.message || 'Error al guardar los cambios', 'error');
            btnSaveChanges.disabled = false;
            btnSaveChanges.innerHTML = originalContent;
        });
    }

    function validateForm() {
        let isValid = true;
        const errors = [];
        
        document.querySelectorAll('.info-item[data-field]').forEach(item => {
            const field = item.dataset.field;
            const input = item.querySelector('.form-control-inline');
            const config = fieldConfig[field];
            
            if (!input || !config) return;
            
            const value = input.value.trim();
            
            // Validar campos requeridos
            if (config.required && !value) {
                isValid = false;
                errors.push(`${config.label} es requerido`);
                input.classList.add('is-invalid');
            } else {
                input.classList.remove('is-invalid');
            }
            
            // Validar email
            if (config.type === 'email' && value) {
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(value)) {
                    isValid = false;
                    errors.push(`${config.label} no es válido`);
                    input.classList.add('is-invalid');
                }
            }
            
            // Validar patrón si existe
            if (config.pattern && value) {
                const regex = new RegExp(config.pattern);
                if (!regex.test(value)) {
                    isValid = false;
                    errors.push(`${config.label} no cumple con el formato esperado`);
                    input.classList.add('is-invalid');
                }
            }
        });
        
        // Mostrar errores específicos si existen
        if (errors.length > 0 && errors.length <= 3) {
            showNotification(errors.join('<br>'), 'error');
        }
        
        return isValid;
    }

    function showNotification(message, type = 'info') {
        const iconMap = {
            success: 'check-circle-fill',
            error: 'exclamation-circle-fill',
            warning: 'exclamation-triangle-fill',
            info: 'info-circle-fill'
        };
        
        const bgMap = {
            success: 'alert-success',
            error: 'alert-danger',
            warning: 'alert-warning',
            info: 'alert-info'
        };
        
        const notification = document.createElement('div');
        notification.className = `alert ${bgMap[type]} alert-notification`;
        notification.innerHTML = `
            <i class="bi bi-${iconMap[type]} me-2"></i>
            <span>${message}</span>
        `;
        
        document.body.appendChild(notification);
        
        // Trigger animation
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);
        
        // Auto remove after 4 seconds
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 400);
        }, 4000);
    }

    function formatDate(dateString) {
        if (!dateString) return 'No especificada';
        
        try {
            const date = new Date(dateString);
            if (isNaN(date)) return dateString;
            
            const day = String(date.getDate()).padStart(2, '0');
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const year = date.getFullYear();
            
            return `${day}/${month}/${year}`;
        } catch (e) {
            return dateString;
        }
    }

    window.showDeactivateModal = function() {
        const modal = new bootstrap.Modal(document.getElementById('deactivateModal'));
        modal.show();
    };

    console.log('✅ Módulo de perfil de usuario cargado correctamente');
});

// Función para copiar al portapapeles
function copyToClipboard(text, message = 'Copiado al portapapeles') {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            showNotification(message, 'success');
        });
    } else {
        // Fallback para navegadores antiguos
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showNotification(message, 'success');
        } catch (err) {
            console.error('Error al copiar:', err);
        }
        textArea.remove();
    }
}

// Función para mostrar confirmación
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}