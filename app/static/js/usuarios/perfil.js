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
    let selectedRol = null;
    let selectedTurno = null;
    let selectedSectores = [];
    const MAX_SECTORES = 2;

    // Datos del usuario (estos se deben pasar desde el template)
    const userData = window.userData || {};
    const rolesDisponibles = window.rolesDisponibles || [];
    const turnosDisponibles = window.turnosDisponibles || [];
    const sectoresDisponibles = window.sectoresDisponibles || [];

    // Configuración de campos editables
    const fieldConfig = {
        nombre: { type: 'text', required: true, label: 'Nombre' },
        apellido: { type: 'text', required: true, label: 'Apellido' },
        cuil_cuit: { type: 'text', required: false, label: 'CUIL/CUIT', pattern: '\\d{11}' },
        legajo: { type: 'text', required: false, label: 'Legajo' },
        email: { type: 'email', required: true, label: 'Email' },
        telefono: { type: 'tel', required: false, label: 'Teléfono' },
        calle: { type: 'text', required: false, label: 'Calle' },
        altura: { type: 'number', required: false, label: 'Altura' },
        provincia: { type: 'provincia', required: false, label: 'Provincia' },
        localidad: { type: 'text', required: false, label: 'Localidad' },
        piso: { type: 'text', required: false, label: 'Piso' },
        depto: { type: 'text', required: false, label: 'Departamento' },
        codigo_postal: { type: 'text', required: false, label: 'Código Postal' },
        role_id: { type: 'role-selector', required: false, label: 'Rol' },
        turno_id: { type: 'turno-selector', required: false, label: 'Turno' },
        sectores: { type: 'sector-selector', required: false, label: 'Sectores' }
        // fecha_ingreso NO es editable
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
            if (e.key === 'Escape') {
                e.preventDefault();
                handleCancelEdit();
            }
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
            
            // Si no hay configuración o es fecha_ingreso, no convertir
            if (!config) return;
            
            let originalValue = valueDiv.textContent.trim();
            
            // Limpiar valores "vacíos"
            if (['No especificado', 'N/A', 'Sin rol', 'Nunca', 'No especificada', 'Sin turno', 'Sin sectores'].includes(originalValue)) {
                originalValue = '';
            }
            
            originalValues[field] = originalValue;
            
            // Crear input según el tipo de campo
            let inputHTML = createInputHTML(field, originalValue, config);
            
            valueDiv.innerHTML = inputHTML;
            valueDiv.classList.add('editing');
            
            // Aplicar animación de entrada con delay
            setTimeout(() => {
                const input = valueDiv.querySelector('.form-control-inline, .roles-grid-perfil, .turno-grid-perfil, .sectores-grid-perfil');
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
            
            case 'role-selector':
                return createRoleSelector(value);
            
            case 'turno-selector':
                return createTurnoSelector(value);
            
            case 'sector-selector':
                return createSectorSelector(value);
            
            case 'provincia':
                return createProvinciaSelect(value, commonAttrs);
            
            case 'date':
                return `<input type="date" ${commonAttrs} value="${value}">`;
            
            case 'email':
                return `<input type="email" ${commonAttrs} value="${value}" placeholder="correo@ejemplo.com">`;
            
            case 'tel':
                return `<input type="tel" ${commonAttrs} value="${value}" placeholder="Ingrese teléfono">`;
            
            case 'number':
                return `<input type="number" ${commonAttrs} value="${value}" placeholder="Ingrese ${config.label.toLowerCase()}">`;
            
            default:
                return `<input type="text" ${commonAttrs} value="${value}" placeholder="Ingrese ${config.label.toLowerCase()}">`;
        }
    }

    function createRoleSelector(currentValue) {
        const roleIcons = {
            'admin': 'bi-shield-fill-check',
            'supervisor': 'bi-person-badge',
            'operario': 'bi-person-gear',
            'gerente': 'bi-briefcase-fill',
            'rrhh': 'bi-people-fill',
            'recursos humanos': 'bi-people-fill',
            'seguridad': 'bi-shield-lock-fill',
            'default': 'bi-person-circle'
        };

        // Encontrar el rol actual
        const currentRole = rolesDisponibles.find(r => r.nombre.toLowerCase() === currentValue.toLowerCase());
        selectedRol = currentRole ? currentRole.id : null;

        let html = '<div class="roles-grid-perfil" id="roles-grid-perfil">';
        
        rolesDisponibles.forEach(rol => {
            const isSelected = selectedRol && rol.id === selectedRol;
            const iconClass = roleIcons[rol.nombre.toLowerCase()] || roleIcons['default'];
            
            html += `
                <div class="rol-card-perfil ${isSelected ? 'selected' : ''}" 
                     data-rol-id="${rol.id}" 
                     data-rol-name="${rol.nombre}">
                    <div class="rol-icon-perfil">
                        <i class="bi ${iconClass}"></i>
                    </div>
                    <p class="rol-nombre-perfil">${rol.nombre}</p>
                    <div class="rol-check-perfil">
                        <i class="bi bi-check-lg"></i>
                    </div>
                </div>
            `;
        });
        
        html += `</div><input type="hidden" name="role_id" id="role_id_input" value="${selectedRol || ''}">`;
        
        setTimeout(() => initRoleSelector(), 100);
        
        return html;
    }

    function createTurnoSelector(currentValue) {
        const turnoIcons = {
            'mañana': 'bi-sunrise',
            'manana': 'bi-sunrise',
            'tarde': 'bi-sun',
            'noche': 'bi-moon-stars',
            'default': 'bi-clock'
        };

        // Encontrar el turno actual
        const currentTurno = turnosDisponibles.find(t => t.nombre.toLowerCase() === currentValue.toLowerCase());
        selectedTurno = currentTurno ? currentTurno.id : null;

        let html = '<div class="turno-grid-perfil" id="turno-grid-perfil">';
        
        turnosDisponibles.forEach(turno => {
            const isSelected = selectedTurno && turno.id === selectedTurno;
            const iconClass = turnoIcons[turno.nombre.toLowerCase()] || turnoIcons['default'];
            
            html += `
                <div class="turno-card-perfil ${isSelected ? 'selected' : ''}" 
                     data-turno-id="${turno.id}" 
                     data-turno-name="${turno.nombre}">
                    <div class="turno-header-perfil">
                        <div class="turno-nombre-perfil">
                            <i class="bi ${iconClass}"></i>
                            ${turno.nombre}
                        </div>
                        <div class="turno-check-perfil">
                            <i class="bi bi-check-lg"></i>
                        </div>
                    </div>
                    <div class="turno-horario-perfil">
                        <i class="bi bi-clock"></i>
                        <span class="turno-time-perfil">${turno.hora_inicio} - ${turno.hora_fin}</span>
                    </div>
                </div>
            `;
        });
        
        html += `</div><input type="hidden" name="turno_id" id="turno_id_input" value="${selectedTurno || ''}">`;
        
        setTimeout(() => initTurnoSelector(), 100);
        
        return html;
    }

    function createSectorSelector(currentValue) {
        const sectorIcons = {
            'produccion': 'bi-gear-fill',
            'producción': 'bi-gear-fill',
            'almacen': 'bi-box-seam',
            'almacén': 'bi-box-seam',
            'logistica': 'bi-truck',
            'logística': 'bi-truck',
            'administracion': 'bi-building',
            'administración': 'bi-building',
            'calidad': 'bi-clipboard-check',
            'mantenimiento': 'bi-tools',
            'default': 'bi-grid-3x3-gap'
        };

        // Parsear sectores actuales (pueden venir separados por coma)
        selectedSectores = [];
        if (currentValue && currentValue !== '') {
            const sectorNames = currentValue.split(',').map(s => s.trim());
            sectorNames.forEach(name => {
                const sector = sectoresDisponibles.find(s => s.nombre === name);
                if (sector) selectedSectores.push(sector.id);
            });
        }

        let html = `
            <div class="sectores-info-perfil">
                <i class="bi bi-info-circle-fill"></i>
                <div class="sectores-info-text-perfil">
                    <strong>Seleccione hasta ${MAX_SECTORES} sectores</strong>
                </div>
                <div class="sectores-counter-perfil" id="sectores-counter-perfil">
                    <i class="bi bi-check-circle-fill me-1"></i>
                    <span id="counter-text-perfil">${selectedSectores.length}/${MAX_SECTORES}</span>
                </div>
            </div>
            <div class="sectores-grid-perfil" id="sectores-grid-perfil">
        `;
        
        sectoresDisponibles.forEach((sector, index) => {
            const isSelected = selectedSectores.includes(sector.id);
            const iconClass = sectorIcons[sector.nombre.toLowerCase()] || sectorIcons['default'];
            const order = isSelected ? selectedSectores.indexOf(sector.id) + 1 : 1;
            
            html += `
                <div class="sector-card-perfil ${isSelected ? 'selected' : ''}" 
                     data-sector-id="${sector.id}" 
                     data-sector-name="${sector.nombre}">
                    <div class="sector-icon-perfil">
                        <i class="bi ${iconClass}"></i>
                    </div>
                    <p class="sector-nombre-perfil">${sector.nombre}</p>
                    <div class="sector-badge-perfil">${order}</div>
                </div>
            `;
        });
        
        html += `</div><input type="hidden" name="sectores" id="sectores_input" value="${JSON.stringify(selectedSectores)}">`;
        
        setTimeout(() => {
            initSectorSelector();
            updateSectoresCounter();
        }, 100);
        
        return html;
    }

    function createProvinciaSelect(value, commonAttrs) {
        const provincias = [
            "Buenos Aires", "CABA", "Catamarca", "Chaco", "Chubut",
            "Córdoba", "Corrientes", "Entre Ríos", "Formosa", "Jujuy",
            "La Pampa", "La Rioja", "Mendoza", "Misiones", "Neuquén",
            "Río Negro", "Salta", "San Juan", "San Luis", "Santa Cruz",
            "Santa Fe", "Santiago del Estero", "Tierra del Fuego", "Tucumán"
        ];
        
        let options = '<option value="">Seleccionar provincia...</option>';
        provincias.forEach(provincia => {
            const selected = provincia === value ? 'selected' : '';
            options += `<option value="${provincia}" ${selected}>${provincia}</option>`;
        });
        
        return `<select ${commonAttrs}>${options}</select>`;
    }

    // ==================== INICIALIZACIÓN DE SELECTORES ====================

    function initRoleSelector() {
        const rolCards = document.querySelectorAll('.rol-card-perfil');
        const rolInput = document.getElementById('role_id_input');
        
        rolCards.forEach(card => {
            card.addEventListener('click', function() {
                // Remover selección anterior
                rolCards.forEach(c => c.classList.remove('selected'));
                
                // Seleccionar nuevo rol
                this.classList.add('selected');
                selectedRol = parseInt(this.dataset.rolId);
                if (rolInput) rolInput.value = selectedRol;
                
                console.log('Rol seleccionado:', selectedRol);
            });
        });
    }

    function initTurnoSelector() {
        const turnoCards = document.querySelectorAll('.turno-card-perfil');
        const turnoInput = document.getElementById('turno_id_input');
        
        turnoCards.forEach(card => {
            card.addEventListener('click', function() {
                // Remover selección anterior
                turnoCards.forEach(c => c.classList.remove('selected'));
                
                // Seleccionar nuevo turno
                this.classList.add('selected');
                selectedTurno = parseInt(this.dataset.turnoId);
                if (turnoInput) turnoInput.value = selectedTurno;
                
                console.log('Turno seleccionado:', selectedTurno);
            });
        });
    }

    function initSectorSelector() {
        const sectorCards = document.querySelectorAll('.sector-card-perfil');
        const sectoresInput = document.getElementById('sectores_input');
        
        sectorCards.forEach(card => {
            card.addEventListener('click', function() {
                if (this.classList.contains('disabled')) return;
                
                const sectorId = parseInt(this.dataset.sectorId);
                
                if (this.classList.contains('selected')) {
                    // Deseleccionar
                    this.classList.remove('selected');
                    selectedSectores = selectedSectores.filter(id => id !== sectorId);
                } else {
                    // Seleccionar solo si no se alcanzó el máximo
                    if (selectedSectores.length < MAX_SECTORES) {
                        this.classList.add('selected');
                        selectedSectores.push(sectorId);
                    } else {
                        showNotification(`Solo puede seleccionar hasta ${MAX_SECTORES} sectores`, 'warning');
                        return;
                    }
                }
                
                updateSectorOrder();
                updateSectoresCounter();
                if (sectoresInput) sectoresInput.value = JSON.stringify(selectedSectores);
                
                console.log('Sectores seleccionados:', selectedSectores);
            });
        });
    }

    function updateSectorOrder() {
        const sectorCards = document.querySelectorAll('.sector-card-perfil');
        sectorCards.forEach(card => {
            if (card.classList.contains('selected')) {
                const sectorId = parseInt(card.dataset.sectorId);
                const order = selectedSectores.indexOf(sectorId) + 1;
                const badge = card.querySelector('.sector-badge-perfil');
                if (badge) badge.textContent = order;
            }
        });
    }

    function updateSectoresCounter() {
        const counterText = document.getElementById('counter-text-perfil');
        const sectoresCounter = document.getElementById('sectores-counter-perfil');
        
        if (counterText) {
            counterText.textContent = `${selectedSectores.length}/${MAX_SECTORES}`;
        }
        
        if (sectoresCounter) {
            sectoresCounter.classList.remove('warning');
            
            if (selectedSectores.length === MAX_SECTORES) {
                sectoresCounter.classList.add('warning');
            }
        }
        
        // Deshabilitar/habilitar cards
        const sectorCards = document.querySelectorAll('.sector-card-perfil');
        sectorCards.forEach(card => {
            if (selectedSectores.length >= MAX_SECTORES && !card.classList.contains('selected')) {
                card.classList.add('disabled');
            } else {
                card.classList.remove('disabled');
            }
        });
    }

    // ==================== VALIDACIÓN DE DIRECCIÓN ====================

    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), delay);
        };
    }

    async function verifyAddress(calleInput, alturaInput, localidadInput, provinciaInput) {
        const calle = calleInput ? calleInput.value.trim() : '';
        const altura = alturaInput ? alturaInput.value.trim() : '';
        const localidad = localidadInput ? localidadInput.value.trim() : '';
        const provincia = provinciaInput ? provinciaInput.value : '';

        if (!calle || !altura || !localidad || !provincia) {
            return;
        }

        const feedbackDiv = document.getElementById('address-feedback-perfil');
        if (feedbackDiv) {
            feedbackDiv.className = 'address-feedback-perfil loading';
            feedbackDiv.innerHTML = '<i class="bi bi-hourglass-split"></i>Verificando dirección...';
        }

        try {
            const response = await fetch('/admin/usuarios/verificar_direccion', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ calle, altura, localidad, provincia })
            });

            const result = await response.json();

            if (result.success && feedbackDiv) {
                const normalized = result.data;
                const normalizedAddress = `${normalized.calle.nombre} ${normalized.altura.valor}, ${normalized.localidad_censal.nombre}, ${normalized.provincia.nombre}`;
                feedbackDiv.className = 'address-feedback-perfil success';
                feedbackDiv.innerHTML = `<i class="bi bi-check-circle-fill"></i>Dirección verificada: ${normalizedAddress}`;
            } else if (feedbackDiv) {
                feedbackDiv.className = 'address-feedback-perfil error';
                feedbackDiv.innerHTML = `<i class="bi bi-x-circle-fill"></i>${result.message || 'No se pudo verificar la dirección'}`;
            }
        } catch (error) {
            console.error('Error al verificar dirección:', error);
            if (feedbackDiv) {
                feedbackDiv.className = 'address-feedback-perfil error';
                feedbackDiv.innerHTML = '<i class="bi bi-exclamation-triangle-fill"></i>Error de red al verificar la dirección';
            }
        }
    }

    const debouncedVerifyAddress = debounce(verifyAddress, 800);

    // Agregar verificación de dirección cuando se editen campos de dirección
    document.addEventListener('input', function(e) {
        if (!isEditMode) return;

        const fieldName = e.target.name;
        if (['calle', 'altura', 'localidad', 'provincia'].includes(fieldName)) {
            const calleInput = document.querySelector('input[name="calle"]');
            const alturaInput = document.querySelector('input[name="altura"]');
            const localidadInput = document.querySelector('input[name="localidad"]');
            const provinciaInput = document.querySelector('select[name="provincia"]');

            // Agregar div de feedback si no existe
            const direccionItem = document.querySelector('.info-item[data-field="calle"]');
            if (direccionItem && !document.getElementById('address-feedback-perfil')) {
                const feedbackDiv = document.createElement('div');
                feedbackDiv.id = 'address-feedback-perfil';
                direccionItem.appendChild(feedbackDiv);
            }

            debouncedVerifyAddress(calleInput, alturaInput, localidadInput, provinciaInput);
        }
    });

    function handleCancelEdit() {
        const cancelModal = new bootstrap.Modal(document.getElementById('cancelEditModal'));
        cancelModal.show();

        document.getElementById('confirm-cancel-edit').onclick = function() {
            cancelModal.hide();
            exitEditMode();
        };
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
        selectedRol = null;
        selectedTurno = null;
        selectedSectores = [];
    }

    function restoreOriginalValues() {
        document.querySelectorAll('.info-item[data-field]').forEach(item => {
            const field = item.dataset.field;
            const valueDiv = item.querySelector('.info-value');
            let originalValue = originalValues[field];
            
            // Si es un valor vacío, mostrar texto apropiado
            if (!originalValue || originalValue === '') {
                const emptyTexts = {
                    'role_id': 'Sin rol',
                    'legajo': 'N/A',
                    'fecha_ingreso': 'No especificada',
                    'turno_id': 'Sin turno',
                    'sectores': 'Sin sectores'
                };
                originalValue = emptyTexts[field] || 'No especificado';
            }
            
            // Para fechas, formatear
            if (field === 'fecha_ingreso' && originalValue !== 'No especificada' && originalValue.includes('-')) {
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
            let input = item.querySelector('.form-control-inline');
            
            // Para selectores especiales, obtener el input hidden
            if (!input) {
                if (field === 'role_id') input = document.getElementById('role_id_input');
                if (field === 'turno_id') input = document.getElementById('turno_id_input');
                if (field === 'sectores') input = document.getElementById('sectores_input');
            }
            
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
                showNotification('Cambios guardados exitosamente', 'success');
                
                // Recargar la página para mostrar los cambios
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

    window.showDeactivateModal = function() {
        const modal = new bootstrap.Modal(document.getElementById('deactivateModal'));
        modal.show();
    };

    console.log('✅ Módulo de perfil de usuario cargado correctamente');
});

// Funciones auxiliares globales
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
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 400);
    }, 4000);
}