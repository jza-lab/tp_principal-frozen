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
    let selectedRoles = []; // Array para almacenar roles seleccionados
    const MAX_ROLES = 2; // Máximo de roles permitidos

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

    // EVENT LISTENERS PRINCIPALES
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
            
            // Obtener el valor actual mostrado en la página (no de userData)
            let originalValue = valueDiv.textContent.trim();
            
            // Para roles, extraer el ID si hay múltiples
            if (field === 'rol_id' && originalValue && originalValue !== 'Sin rol') {
                // Si hay múltiples roles separados por coma
                if (originalValue.includes(',')) {
                    const roleNames = originalValue.split(',').map(n => n.trim());
                    const roles = window.rolesDisponibles || [];
                    const roleIds = roleNames.map(name => {
                        const rol = roles.find(r => r.nombre === name);
                        return rol ? rol.id : null;
                    }).filter(id => id !== null);
                    originalValue = roleIds.join(',');
                }
            }
            
            // Si el valor es "No especificado" o similar, usar cadena vacía
            if (originalValue === 'No especificado' || originalValue === 'N/A' || originalValue === 'Sin rol' || originalValue === 'Nunca' || originalValue === 'No especificada') {
                originalValue = '';
            }
            
            // Para fechas, convertir el formato DD/MM/YYYY a YYYY-MM-DD
            if (field === 'fecha_ingreso' && originalValue && originalValue.includes('/')) {
                const parts = originalValue.split('/');
                if (parts.length === 3) {
                    originalValue = `${parts[2]}-${parts[1]}-${parts[0]}`;
                }
            }
            
            originalValues[field] = originalValue;
            
            // Crear input según el tipo de campo
            let inputHTML = createInputHTML(field, originalValue, config);
            
            valueDiv.innerHTML = inputHTML;
            valueDiv.classList.add('editing');
            
            // Aplicar animación de entrada con delay
            setTimeout(() => {
                const input = valueDiv.querySelector('.form-control-inline, #role_id_input');
                if (input && input.classList.contains('form-control-inline')) {
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
            // Crear selector interactivo de roles
            const roles = window.rolesDisponibles || [];
            
            // Inicializar roles seleccionados
            selectedRoles = [];
            if (value && value !== '' && value !== 'Sin rol') {
                const rolEncontrado = roles.find(r => r.nombre === value);
                if (rolEncontrado) {
                    selectedRoles.push(rolEncontrado.id);
                }
            }
            
            // Iconos para diferentes tipos de roles
            const roleIcons = {
                'admin': 'bi-shield-fill-check',
                'supervisor': 'bi-person-badge',
                'operario': 'bi-person-gear',
                'gerente': 'bi-briefcase-fill',
                'rrhh': 'bi-people-fill',
                'seguridad': 'bi-shield-lock-fill',
                'default': 'bi-person-circle'
            };
            
            let html = `
                <div class="role-selector-info">
                    <i class="bi bi-info-circle-fill"></i>
                    <div class="role-selector-info-text">
                        <strong>Seleccione hasta ${MAX_ROLES} roles</strong>
                        <span>Puede asignar múltiples responsabilidades al usuario</span>
                    </div>
                    <div class="role-counter" id="role-counter">
                        <i class="bi bi-check2-circle"></i>
                        <span><span id="role-count">0</span>/${MAX_ROLES}</span>
                    </div>
                </div>
                <div class="role-selector-container">
            `;
            
            roles.forEach(rol => {
                const isSelected = selectedRoles.includes(rol.id);
                const iconClass = roleIcons[rol.nombre.toLowerCase()] || roleIcons['default'];
                const description = getRoleDescription(rol.nombre);
                
                html += `
                    <div class="role-option ${isSelected ? 'selected' : ''}" 
                         data-role-id="${rol.id}" 
                         data-role-name="${rol.nombre}">
                        <div class="role-option-check">
                            <i class="bi bi-check-lg"></i>
                        </div>
                        <div class="role-option-icon">
                            <i class="bi ${iconClass}"></i>
                        </div>
                        <h6 class="role-option-name">${rol.nombre}</h6>
                        <p class="role-option-description">${description}</p>
                    </div>
                `;
            });
            
            html += `
                </div>
                <input type="hidden" name="role_id" id="role_id_input" value="${selectedRoles.join(',')}">
            `;
            
            // Agregar event listeners después de un pequeño delay
            setTimeout(() => {
                initRoleSelector();
                updateRoleCounter();
            }, 100);
            
            return html;
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

        function getRoleDescription(roleName) {
        const descriptions = {
            'Admin': 'Acceso total al sistema',
            'Supervisor': 'Gestión de personal y operaciones',
            'Operario': 'Acceso a funciones operativas',
            'Gerente': 'Dirección y toma de decisiones',
            'RRHH': 'Gestión de recursos humanos',
            'Vendedor': 'Gestión de ventas y clientes',
            'IT': 'Soporte técnico y mantenimiento',
            'Supervisor_Calidad': 'Control y aseguramiento de calidad',
        };
        return descriptions[roleName] || 'Rol del sistema';
    }

     function initRoleSelector() {
        const roleOptions = document.querySelectorAll('.role-option');
        
        roleOptions.forEach(option => {
            option.addEventListener('click', function() {
                const roleId = parseInt(this.dataset.roleId);
                const roleName = this.dataset.roleName;
                
                if (this.classList.contains('selected')) {
                    // Deseleccionar
                    this.classList.remove('selected');
                    selectedRoles = selectedRoles.filter(id => id !== roleId);
                } else {
                    // Verificar límite
                    if (selectedRoles.length >= MAX_ROLES) {
                        showNotification(`Solo puede seleccionar hasta ${MAX_ROLES} roles`, 'warning');
                        return;
                    }
                    // Seleccionar
                    this.classList.add('selected');
                    selectedRoles.push(roleId);
                }
                
                // Actualizar input hidden
                const hiddenInput = document.getElementById('role_id_input');
                if (hiddenInput) {
                    hiddenInput.value = selectedRoles.join(',');
                }
                
                // Actualizar contador
                updateRoleCounter();
                
                // Actualizar estado de opciones
                updateRoleOptions();
            });
        });
    }

    function updateRoleCounter() {
        const counter = document.getElementById('role-counter');
        const countSpan = document.getElementById('role-count');
        
        if (counter && countSpan) {
            countSpan.textContent = selectedRoles.length;
            
            counter.classList.remove('full', 'warning');
            
            if (selectedRoles.length === MAX_ROLES) {
                counter.classList.add('full');
            } else if (selectedRoles.length > 0) {
                counter.classList.add('warning');
            }
        }
    }
 
    function updateRoleOptions() {
        const roleOptions = document.querySelectorAll('.role-option');
        
        roleOptions.forEach(option => {
            if (selectedRoles.length >= MAX_ROLES && !option.classList.contains('selected')) {
                option.classList.add('disabled');
            } else {
                option.classList.remove('disabled');
            }
        });
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
                if (field === 'rol_id') {
                    originalValue = 'Sin rol';
                } else if (field === 'legajo') {
                    originalValue = 'N/A';
                } else if (field === 'fecha_ingreso') {
                    originalValue = 'No especificada';
                } else if (field === 'direccion') {
                    originalValue = 'No especificada';
                } else {
                    originalValue = 'No especificado';
                }
            }
            
            // Para campos especiales, formatear el valor
            if (field === 'fecha_ingreso' && originalValue !== 'No especificada' && originalValue.includes('-')) {
                // Convertir de YYYY-MM-DD a DD/MM/YYYY
                const parts = originalValue.split('-');
                if (parts.length === 3) {
                    originalValue = `${parts[2]}/${parts[1]}/${parts[0]}`;
                }
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
            const input = item.querySelector('.form-control-inline, #role_id_input');
            
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
                // Actualizar valores en la interfaz sin recargar
                document.querySelectorAll('.info-item[data-field]').forEach(item => {
                    const field = item.dataset.field;
                    const valueDiv = item.querySelector('.info-value');
                    
                    if (field === 'rol_id') {
                        // Para roles, mostrar los nombres seleccionados
                        const hiddenInput = document.getElementById('role_id_input');
                        if (hiddenInput && hiddenInput.value) {
                            const roleIds = hiddenInput.value.split(',').map(id => parseInt(id));
                            const roles = window.rolesDisponibles || [];
                            const roleNames = roleIds.map(id => {
                                const rol = roles.find(r => r.id === id);
                                return rol ? rol.nombre : '';
                            }).filter(name => name !== '');
                            
                            if (roleNames.length > 0) {
                                valueDiv.textContent = roleNames.join(', ');
                            } else {
                                valueDiv.textContent = 'Sin rol';
                            }
                        } else {
                            valueDiv.textContent = 'Sin rol';
                        }
                    } else {
                        const input = item.querySelector('.form-control-inline');
                        if (input && valueDiv) {
                            let newValue = input.value.trim();
                            
                            // Formatear valores especiales para mostrar
                            if (!newValue || newValue === '') {
                                if (field === 'legajo') {
                                    newValue = 'N/A';
                                } else if (field === 'fecha_ingreso') {
                                    newValue = 'No especificada';
                                } else {
                                    newValue = 'No especificado';
                                }
                            } else if (field === 'fecha_ingreso' && newValue.includes('-')) {
                                // Convertir fecha de YYYY-MM-DD a DD/MM/YYYY
                                const parts = newValue.split('-');
                                if (parts.length === 3) {
                                    newValue = `${parts[2]}/${parts[1]}/${parts[0]}`;
                                }
                            } else if (input.tagName === 'SELECT') {
                                // Mostrar el texto seleccionado en lugar del valor
                                const selectedOption = input.options[input.selectedIndex];
                                newValue = selectedOption ? selectedOption.text : newValue;
                            }
                            
                            // Actualizar el valor mostrado
                            valueDiv.textContent = newValue;
                        }
                    }
                });
                
                // Mostrar mensaje de éxito
                showNotification('Cambios guardados exitosamente', 'success');
                
                // Salir del modo edición
                exitEditMode();
                
                // Opcional: Recargar después de un momento para asegurar sincronización
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

    function confirmAction(message, callback) {
        if (confirm(message)) {
            callback();
        }
    }

    // Datos del usuario actual
    window.userData = {
        nombre: "{{ usuario.nombre }}",
        apellido: "{{ usuario.apellido }}",
        email: "{{ usuario.email }}",
        legajo: "{{ usuario.legajo or '' }}",
        cuil_cuit: "{{ usuario.cuil_cuit or '' }}",
        telefono: "{{ usuario.telefono or '' }}",
        direccion: "{{ usuario.direccion_formateada or '' }}",
        rol_id: "{{ usuario.role_id or '' }}",
        turno: "{{ usuario.turno or '' }}",
        fecha_ingreso: "{{ usuario.fecha_ingreso.strftime('%Y-%m-%d') if usuario.fecha_ingreso else '' }}"
    };

    /*
    window.rolesDisponibles = [
        {% for rol in roles_disponibles %}
        { id: {{ rol.id }}, nombre: "{{ rol.nombre }}" }{% if not loop.last %},{% endif %}
        {% endfor %}
    ];*/
