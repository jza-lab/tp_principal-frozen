import {
    clearValidation,
    validateUniqueField,
    validateNombre,
    validateApellido,
    validateForm,
    validateAddressField,
    showError,
    showSuccess
} from './utils/validaciones.js';

import {
    initializeSelectors
} from './utils/selectores.js';


document.addEventListener('DOMContentLoaded', function () {
    // --- ELEMENTOS DEL DOM ---
    const btnEditMode = document.getElementById('btn-edit-mode');
    const btnSaveChanges = document.getElementById('btn-save-changes');
    const btnCancelEdit = document.getElementById('btn-cancel-edit');
    const actionBarView = document.getElementById('action-bar-view');
    const actionBarEdit = document.getElementById('action-bar-edit');
    const profileContent = document.querySelector('.profile-content');
    const profileForm = document.getElementById('profile-form');

    // --- ESTADO ---
    let isEditMode = false;
    let originalFormState = {};
    let addressVerified = true; // Asumimos que la dirección inicial es válida

    // --- INICIALIZACIÓN ---
    initializePage();

    function initializePage() {
        const initialState = {
            role_id: USER_ROLE_ID,
            turno_id: USER_TURNO_ID,
            sectores_ids: USUARIO_SECTORES_IDS
        };
        initializeSelectors(initialState);
        addEventListeners();
    }

    function addEventListeners() {
        if (btnEditMode) btnEditMode.addEventListener('click', enterEditMode);
        if (btnSaveChanges) btnSaveChanges.addEventListener('click', saveChanges);
        if (btnCancelEdit) btnCancelEdit.addEventListener('click', handleCancelEdit);
    }
    // --- LÓGICA DE MODO EDICIÓN ---

    function enterEditMode() {
        isEditMode = true;

        actionBarView.style.display = 'none';
        actionBarEdit.style.display = 'flex';
        profileContent.classList.remove('view-mode');
        profileContent.classList.add('edit-mode');

        profileForm.querySelectorAll('input, select').forEach(el => {
            el.disabled = false;
        });
        
        originalFormState = captureFormState();
        addValidationListeners();
    }
    
    function exitEditMode() {
        isEditMode = false;
        restoreFormState(originalFormState);

        actionBarEdit.style.display = 'none';
        actionBarView.style.display = 'flex';
        profileContent.classList.remove('edit-mode');
        profileContent.classList.add('view-mode');

        profileForm.querySelectorAll('input, select').forEach(el => {
            el.disabled = true;
            clearValidation(el);
        });
    }

    function handleCancelEdit() {
        const cancelModal = new bootstrap.Modal(document.getElementById('cancelEditModal'));
        cancelModal.show();
        document.getElementById('confirm-cancel-edit').onclick = () => {
            cancelModal.hide();
            exitEditMode();
        };
    }

    // --- MANEJO DE DATOS Y ESTADO DEL FORMULARIO ---

    function captureFormState() {
        const state = {};
        new FormData(profileForm).forEach((value, key) => {
            state[key] = value;
        });
        return state;
    }

    function restoreFormState(state) {
        for (const key in state) {
            const element = profileForm.elements[key];
            if (element) {
                element.value = state[key];
            }
        }
    }
    
     function addValidationListeners() {
        document.getElementById('nombre').addEventListener('blur', (e) => validateNombre(e.target));
        document.getElementById('apellido').addEventListener('blur', (e) => validateApellido(e.target));
        document.getElementById('legajo').addEventListener('blur', (e) => validateUniqueField('legajo', e.target.value, e.target, USER_ID));
        document.getElementById('email').addEventListener('blur', (e) => validateUniqueField('email', e.target.value, e.target, USER_ID));
        document.getElementById('telefono').addEventListener('blur', (e) => validateUniqueField('telefono', e.target.value, e.target, USER_ID));
        
        const cuilParte1 = document.getElementById('cuit_parte1');
        const cuilParte2 = document.getElementById('cuit_parte2');
        const cuilParte3 = document.getElementById('cuit_parte3');
        const cuilFields = [cuilParte1, cuilParte2, cuilParte3];

        cuilFields.forEach(field => {
            if(field) {
                field.addEventListener('blur', handleCuitValidation);
                field.addEventListener('input', syncCuitHiddenInput);
            }
        });

        const debouncedVerifyAddress = debounce(verifyAddress, 800);
        const addressFields = [document.getElementById('calle'), document.getElementById('altura'), document.getElementById('provincia'), document.getElementById('localidad')];
        addressFields.forEach(field => {
            field.addEventListener('input', () => {
                validateAddressField(field);
                debouncedVerifyAddress();
            });
        });
    }

    function syncCuitHiddenInput() {
        const cuilParte1 = document.getElementById('cuit_parte1');
        const cuilParte2 = document.getElementById('cuit_parte2');
        const cuilParte3 = document.getElementById('cuit_parte3');
        const cuilHiddenInput = document.getElementById('cuil_cuit_hidden');
        const value = `${cuilParte1.value}-${cuilParte2.value}-${cuilParte3.value}`;
        cuilHiddenInput.value = value;
    }

    function handleCuitValidation() {
        syncCuitHiddenInput();
        const cuilGroup = document.querySelector('.cuit-input-group');
        const cuilHiddenInput = document.getElementById('cuil_cuit_hidden');
        const cuilParte1 = document.getElementById('cuit_parte1');
        const cuilParte2 = document.getElementById('cuit_parte2');
        const cuilParte3 = document.getElementById('cuit_parte3');
        
        if (cuilParte1.value.length === 2 && cuilParte2.value.length === 8 && cuilParte3.value.length === 1) {
            validateUniqueField('cuil_cuit', cuilHiddenInput.value, cuilGroup, USER_ID);
        }
    }

    function debounce(func, delay) {
        let timeout;
        return function (...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), delay);
        };
    }

    async function verifyAddress() {
        addressVerified = false;
        const calleInput = document.getElementById('calle');
        const alturaInput = document.getElementById('altura');
        const provinciaSelect = document.getElementById('provincia');
        const localidadInput = document.getElementById('localidad');
        const addressFeedback = document.getElementById('address-feedback');
        
        if (!calleInput.value || !alturaInput.value || !localidadInput.value || !provinciaSelect.value) {
            addressFeedback.innerHTML = '';
            return;
        }

        addressFeedback.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Verificando dirección...';
        
        try {
            const response = await fetch('/api/validar/direccion', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    calle: calleInput.value,
                    altura: alturaInput.value,
                    localidad: localidadInput.value,
                    provincia: provinciaSelect.value
                })
            });
            const result = await response.json();
            if (result.success) {
                const normalized = result.data;
                const normalizedAddress = `${normalized.calle.nombre} ${normalized.altura.valor}, ${normalized.localidad_censal.nombre}, ${normalized.provincia.nombre}`;
                addressFeedback.innerHTML = `<i class="bi bi-check-circle-fill text-success me-2"></i>Dirección verificada: ${normalizedAddress}`;
                addressVerified = true;
            } else {
                addressFeedback.innerHTML = `<i class="bi bi-x-circle-fill text-danger me-2"></i>Error: ${result.message || 'No se pudo verificar.'}`;
            }
        } catch (error) {
            addressFeedback.innerHTML = '<i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>Error de red al verificar.';
        }
    }

    // --- LÓGICA DE GUARDADO ---
    async function saveChanges() {
        // Validación de campos básicos
        const isFormValid = validateForm();
        const areSectoresValid = validateSectores();

        if (!isFormValid || !addressVerified || !areSectoresValid) {
            return;
        }

        if (!formHasChanged()) {
            const noChangesModalEl = document.getElementById('noChangesModal');
            const noChangesModal = new bootstrap.Modal(noChangesModalEl);
            
            // Añadir listener para salir del modo edición al confirmar
            const confirmBtn = document.getElementById('btn-no-changes-confirm');
            confirmBtn.addEventListener('click', () => {
                noChangesModal.hide();
                exitEditMode();
            }, { once: true }); // Usar 'once' para que el listener se auto-elimine

            noChangesModal.show();
            return;
        }

        const formData = new FormData(profileForm);
        const url = btnSaveChanges.dataset.url;

        btnSaveChanges.disabled = true;
        btnSaveChanges.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...';

        try {
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || 'Error al guardar los cambios.');
            }
            window.location.reload();
        } catch (error) {
            showToast(error.message, 'error');
            console.error('Error al guardar:', error);
        } finally {
            btnSaveChanges.disabled = false;
            btnSaveChanges.innerHTML = '<i class="bi bi-check-circle me-2"></i>Guardar Cambios';
        }
    }

    function formHasChanged() {
        const currentState = captureFormState();
        // Rol: Comparamos como números para evitar errores de tipo (e.g., '1' vs 1)
        currentState.role_id = document.getElementById('role_id').value;
        originalFormState.role_id = String(USER_ROLE_ID);

        // Turno: Comparamos como números
        currentState.turno_id = document.getElementById('turno_id').value;
        originalFormState.turno_id = String(USER_TURNO_ID);

        // Sectores: Normalizamos a un string JSON ordenado para una comparación consistente
        const currentSectores = JSON.parse(document.getElementById('sectores').value || '[]').map(Number).sort();
        currentState.sectores = JSON.stringify(currentSectores);
        const originalSectores = (USUARIO_SECTORES_IDS || []).map(Number).sort();
        originalFormState.sectores = JSON.stringify(originalSectores);

        for (const key in originalFormState) {
            if (originalFormState[key] !== currentState[key]) {
                // Para depuración:
                // console.log(`'${key}' ha cambiado. Original: '${originalFormState[key]}', Actual: '${currentState[key]}'`);
                return true;
            }
        }
        return false;
    }

    function showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container-profile');
        if (!toastContainer) {
            console.error('El contenedor de toasts no se encuentra en la página.');
            return;
        }

        const toastId = 'toast-' + Date.now();
        const toastIcon = type === 'success' ? '<i class="bi bi-check-circle-fill"></i>' :
                          type === 'error' ? '<i class="bi bi-x-circle-fill"></i>' :
                          '<i class="bi bi-info-circle-fill"></i>';
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white bg-${type === 'error' ? 'danger' : (type === 'success' ? 'success' : 'primary')}" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        ${toastIcon} ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        toastContainer.insertAdjacentHTML('beforeend', toastHtml);

        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { delay: 4000 });
        toast.show();
        toastElement.addEventListener('hidden.bs.toast', () => toastElement.remove());
    }

    // Hacer la función accesible globalmente para el onclick del HTML
    window.showDeactivateModal = function() {
        const deactivateModal = new bootstrap.Modal(document.getElementById('deactivateModal'));
        deactivateModal.show();
    }
    
    function validateSectores() {
        const sectoresInput = document.getElementById('sectores');
        const sectoresGrid = document.getElementById('sectoresGrid');
        const value = sectoresInput.value;

        // Limpiar validación previa al interactuar
        clearValidation(sectoresGrid);

        try {
            const sectores = JSON.parse(value);
            if (!Array.isArray(sectores) || sectores.length === 0) {
                showError(sectoresGrid, 'Debe seleccionar al menos un sector.');
                return false;
            }
        } catch (e) {
            // Si el JSON es inválido, también es un error.
            showError(sectoresGrid, 'La selección de sectores es inválida.');
            return false;
        }

        showSuccess(sectoresGrid, 'Selección de sectores válida.');
        return true;
    }
});