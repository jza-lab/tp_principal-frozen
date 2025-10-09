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
});
