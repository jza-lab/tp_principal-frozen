import {
    validateUniqueField,
    validateNombre,
    validateApellido,
    validatePassword,
    validateAddressField
} from './utils/validaciones.js';

import {
    initializeSelectors,
    getSelectorsState
} from './utils/selectores.js';


document.addEventListener('DOMContentLoaded', function () {
    if (typeof IS_NEW === 'undefined' || !IS_NEW) {
        return; 
    }

    // --- ELEMENTOS DEL DOM ---
    const userForm = document.getElementById('userForm');
    const step1Element = document.getElementById('step1');
    const step2Element = document.getElementById('step2');
    const step3Element = document.getElementById('step3');
    const personalInfoSection = document.getElementById('personalInfo');
    const addressInfoSection = document.getElementById('addressInfo');
    const faceRegistrationSection = document.getElementById('faceRegistration');
    const nextStepBtn = document.getElementById('nextStep');
    const prevStepBtn = document.getElementById('prevStep');
    const submitFormBtn = document.getElementById('submitForm');
    const cancelBtn = document.getElementById('cancelBtn');

    // Campos del formulario
    const nombreInput = document.getElementById('nombre');
    const apellidoInput = document.getElementById('apellido');
    const legajoInput = document.getElementById('legajo');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const telefonoInput = document.getElementById('telefono');
    
    // Campos del CUIL
    const cuilParte1 = document.getElementById('cuit_parte1');
    const cuilParte2 = document.getElementById('cuit_parte2');
    const cuilParte3 = document.getElementById('cuit_parte3');
    const cuilGroup = document.querySelector('.cuit-input-group');
    const cuilHiddenInput = document.getElementById('cuil_cuit_hidden');

    // Campos de dirección
    const calleInput = document.getElementById('calle');
    const alturaInput = document.getElementById('altura');
    const provinciaSelect = document.getElementById('provincia');
    const localidadInput = document.getElementById('localidad');
    const addressFeedback = document.getElementById('address-feedback');

    const requiredInputsStep1 = personalInfoSection ? personalInfoSection.querySelectorAll('input[required], select[required]') : [];
    const requiredInputsStep2 = addressInfoSection ? addressInfoSection.querySelectorAll('input[required], select[required]') : [];

    // Elementos de la cámara
    const startCameraBtn = document.getElementById('startCamera');
    const capturePhotoBtn = document.getElementById('capturePhoto');
    const confirmPhotoBtn = document.getElementById('confirmPhoto');
    const retakePhotoBtn = document.getElementById('retakePhoto');
    const retakePhotoBtn2 = document.getElementById('retakePhoto2');
    const videoElement = document.getElementById('videoElement');
    const canvasElement = document.getElementById('canvasElement');
    const capturedImage = document.getElementById('capturedImage');
    const faceDataInput = document.getElementById('faceData');


    // --- ESTADO DE LA APLICACIÓN ---
    let currentStep = 1;
    let videoStream = null;
    let photoTaken = false;
    let photoConfirmed = false;
    const validationState = {
        step1Complete: false,
        step2Complete: false,
        addressVerified: false
    };

    // --- INICIALIZACIÓN ---
    initializeSelectors();
    addEventListeners();
    updateStepButtonState();

    // --- MANEJADORES DE EVENTOS ---
    function addEventListeners() {
        userForm.addEventListener('submit', handleFormSubmit);
        nextStepBtn.addEventListener('click', () => goToStep(currentStep + 1));
        prevStepBtn.addEventListener('click', () => goToStep(currentStep - 1));

        // Validaciones Paso 1
        nombreInput.addEventListener('blur', () => validateNombre(nombreInput));
        apellidoInput.addEventListener('blur', () => validateApellido(apellidoInput));
        legajoInput.addEventListener('blur', () => validateUniqueField('legajo', legajoInput.value, legajoInput));
        emailInput.addEventListener('blur', () => validateUniqueField('email', emailInput.value, emailInput));
        passwordInput.addEventListener('blur', () => validatePassword(passwordInput));
        telefonoInput.addEventListener('blur', () => validateUniqueField('telefono', telefonoInput.value, telefonoInput));

        const cuilFields = [cuilParte1, cuilParte2, cuilParte3];
        cuilFields.forEach(field => {
            field.addEventListener('blur', handleCuitValidation);
            field.addEventListener('input', syncCuitHiddenInput);
        });

        const debouncedVerifyAddress = debounce(verifyAddress, 800);
        const addressFields = [calleInput, alturaInput, provinciaSelect, localidadInput];
        addressFields.forEach(field => {
            field.addEventListener('input', () => {
                validateAddressField(field);
                debouncedVerifyAddress();
            });
        });
        
        startCameraBtn.addEventListener('click', startCamera);
        capturePhotoBtn.addEventListener('click', capturePhoto);
        confirmPhotoBtn.addEventListener('click', confirmPhoto);
        retakePhotoBtn.addEventListener('click', retakePhoto);
        retakePhotoBtn2.addEventListener('click', retakePhoto);

        document.getElementById('userForm').addEventListener('input', updateStepButtonState);
        document.getElementById('userForm').addEventListener('selectionChanged', updateStepButtonState);
    }
    
    // --- LÓGICA DE VALIDACIÓN ---
    function syncCuitHiddenInput() {
        const value = `${cuilParte1.value}-${cuilParte2.value}-${cuilParte3.value}`;
        cuilHiddenInput.value = value;
    }

    function handleCuitValidation() {
        syncCuitHiddenInput();
        if (cuilParte1.value.length === 2 && cuilParte2.value.length === 8 && cuilParte3.value.length === 1) {
            validateUniqueField('cuil_cuit', cuilHiddenInput.value, cuilGroup);
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
        validationState.addressVerified = false;
        if (!calleInput.value || !alturaInput.value || !localidadInput.value || !provinciaSelect.value) {
            addressFeedback.innerHTML = '';
            updateStepButtonState();
            return;
        }

        addressFeedback.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Verificando dirección...';
        const csrfToken = document.querySelector('input[name="csrf_token"]').value;
        
        try {
            const response = await fetch('/api/validar/direccion', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
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
                validationState.addressVerified = true;
            } else {
                addressFeedback.innerHTML = `<i class="bi bi-x-circle-fill text-danger me-2"></i>Error: ${result.message || 'No se pudo verificar.'}`;
            }
        } catch (error) {
            addressFeedback.innerHTML = '<i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>Error de red al verificar.';
        } finally {
            updateStepButtonState();
        }
    }

    // --- LÓGICA DE NAVEGACIÓN Y VALIDACIÓN DE PASOS ---
    function checkStep1Complete() {
        let allInputsValid = true;
        requiredInputsStep1.forEach(input => {
            if (!input.value || input.classList.contains('is-invalid')) {
                allInputsValid = false;
            }
        });
        const selectorsState = getSelectorsState();
        const allSelectorsValid = selectorsState.role_id !== null &&
                                  selectorsState.turno_id !== null &&
                                  selectorsState.sectores.length > 0;
        return allInputsValid && allSelectorsValid;
    }

    function checkStep2Complete() {
        let allValid = true;
        requiredInputsStep2.forEach(input => {
            if (!input.value || input.classList.contains('is-invalid')) {
                allValid = false;
            }
        });
        return allValid && validationState.addressVerified;
    }

    function updateStepButtonState() {
        if (currentStep === 1) {
            nextStepBtn.disabled = !checkStep1Complete();
        } else if (currentStep === 2) {
            nextStepBtn.disabled = !checkStep2Complete();
        }
    }

    function goToStep(step) {
        if (step === 2 && !checkStep1Complete()) return;
        if (step === 3 && !checkStep2Complete()) return;
        currentStep = step;
        
        step1Element.classList.toggle('active', currentStep === 1);
        step1Element.classList.toggle('completed', currentStep > 1);
        step2Element.classList.toggle('active', currentStep === 2);
        step2Element.classList.toggle('completed', currentStep > 2);
        step3Element.classList.toggle('active', currentStep === 3);

        personalInfoSection.style.display = (currentStep === 1) ? 'block' : 'none';
        addressInfoSection.style.display = (currentStep === 2) ? 'block' : 'none';
        faceRegistrationSection.style.display = (currentStep === 3) ? 'block' : 'none';

        prevStepBtn.style.display = (currentStep > 1) ? 'inline-block' : 'none';
        nextStepBtn.style.display = (currentStep < 3) ? 'inline-block' : 'none';
        submitFormBtn.style.display = (currentStep === 3) ? 'inline-block' : 'none';
        cancelBtn.style.display = (currentStep === 1) ? 'inline-block' : 'none';
        
        if (currentStep === 3) submitFormBtn.disabled = !photoConfirmed;
        updateStepButtonState();
    }
    
    // --- LÓGICA DE LA CÁMARA ---
    async function startCamera() {
        try {
            videoStream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' } });
            videoElement.srcObject = videoStream;
            document.getElementById('cameraInactive').style.display = 'none';
            document.getElementById('cameraActive').style.display = 'block';
        } catch (error) { console.error('Error al acceder a la cámara:', error); showNotificationModal('Error de Cámara', 'No se pudo acceder a la cámara. Verifique los permisos.'); }
    }

    async function capturePhoto() {
        const context = canvasElement.getContext('2d');
        canvasElement.width = videoElement.videoWidth;
        canvasElement.height = videoElement.videoHeight;
        context.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height);
        const imageData = canvasElement.toDataURL('image/jpeg', 0.8);

        capturePhotoBtn.disabled = true;
        capturePhotoBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Verificando...';
        const csrfToken = document.querySelector('input[name="csrf_token"]').value;

        try {
            const response = await fetch('/api/validar/rostro', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ image: imageData })
            });
            const result = await response.json();

            if (!response.ok || !result.valid) {
                throw new Error(result.message || 'No se pudo validar el rostro.');
            }

            capturedImage.src = imageData;
            faceDataInput.value = imageData;
            document.getElementById('cameraActive').style.display = 'none';
            document.getElementById('photoPreview').style.display = 'block';
            photoTaken = true;

        } catch (error) {
            console.error('Error en validación facial:', error);
            showNotificationModal('Error de Validación', error.message);
        } finally {
            capturePhotoBtn.disabled = false;
            capturePhotoBtn.innerHTML = '<i class="bi bi-camera me-2"></i> Capturar Foto';
        }
    }

    function confirmPhoto() {
        if (!photoTaken) return;
        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
        }
        photoConfirmed = true;
        step3Element.classList.add('completed');
        submitFormBtn.disabled = false;
        confirmPhotoBtn.disabled = true;
        retakePhotoBtn.disabled = true;
        retakePhotoBtn2.disabled = true;
        
        showNotificationModal('Éxito', 'Rostro confirmado. Ya puede crear el empleado.');
    }

    function retakePhoto() {
        photoTaken = false;
        faceDataInput.value = '';
        document.getElementById('photoPreview').style.display = 'none';
        document.getElementById('cameraActive').style.display = 'block';
        if (!videoStream || !videoStream.active) {
            startCamera();
        }
    }

    // --- ENVÍO DE FORMULARIO ---
    function handleFormSubmit(e) {
        if (currentStep === 3 && !photoConfirmed) {
            e.preventDefault();
            showNotificationModal('Rostro no Confirmado', 'Por favor, capture y confirme su rostro antes de crear el usuario.');
            return;
        }
        submitFormBtn.disabled = true;
        submitFormBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Creando empleado...';
    }

    // --- UTILIDADES ---
    function showNotificationModal(title, message) {
        const existingModal = document.getElementById('notificationModal');
        if (existingModal) existingModal.remove();

        const modalHTML = `
            <div class="modal fade" id="notificationModal" tabindex="-1">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body"><p>${message}</p></div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-primary" data-bs-dismiss="modal">Entendido</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        const modal = new bootstrap.Modal(document.getElementById('notificationModal'));
        modal.show();
    }
});