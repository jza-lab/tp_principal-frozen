import {
    clearValidation,
    validateUniqueField,
    validateNombre,
    validateApellido,
    validateForm,
    validateAddressField
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
    addEventListeners();

    function addEventListeners() {
        if (btnEditMode) btnEditMode.addEventListener('click', enterEditMode);
        if (btnSaveChanges) btnSaveChanges.addEventListener('click', saveChanges);
        if (btnCancelEdit) btnCancelEdit.addEventListener('click', handleCancelEdit);
    }

    // --- LÓGICA DE MODO EDICIÓN ---

    function enterEditMode() {
        isEditMode = true;
        originalFormState = captureFormState();

        actionBarView.style.display = 'none';
        actionBarEdit.style.display = 'flex';
        profileContent.classList.add('edit-mode');
        
        initializeSelectors({
            role_id: parseInt(originalFormState.role_id),
            turno_id: parseInt(originalFormState.turno_id),
            sectores_ids: USUARIO_SECTORES_IDS
        });

        profileForm.querySelectorAll('input, select').forEach(el => {
            el.disabled = false;
        });
        addValidationListeners();
    }
    
    function exitEditMode() {
        isEditMode = false;
        restoreFormState(originalFormState);

        actionBarEdit.style.display = 'none';
        actionBarView.style.display = 'flex';
        profileContent.classList.remove('edit-mode');

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
        if (!validateForm() || !addressVerified) {
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
            console.error('Error al guardar:', error);
        } finally {
            btnSaveChanges.disabled = false;
            btnSaveChanges.innerHTML = '<i class="bi bi-check-circle me-2"></i>Guardar Cambios';
        }
    }
});