document.addEventListener('DOMContentLoaded', function () {
    // --- ELEMENTOS DEL DOM ---
    const userForm = document.getElementById('userForm');
    const step1Element = document.getElementById('step1');
    const step2Element = document.getElementById('step2');
    const step3Element = document.getElementById('step3');
    const personalInfoSection = document.getElementById('personalInfo');
    const addressInfoSection = document.getElementById('addressInfo');
    const faceRegistrationSection = document.getElementById('faceRegistration');

    // Botones de navegación
    const nextStepBtn = document.getElementById('nextStep');
    const prevStepBtn = document.getElementById('prevStep');
    const submitFormBtn = document.getElementById('submitForm');
    const cancelBtn = document.getElementById('cancelBtn');

    // Campos del formulario - Paso 1
    const legajoInput = document.getElementById('legajo');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const nombreInput = document.getElementById('nombre');
    const apellidoInput = document.getElementById('apellido');
    const rolSelect = document.getElementById('role_id');
    const cuilInput = document.getElementById('cuil_cuit');
    const telefonoInput = document.getElementById('telefono');
    const cuilHelper = document.getElementById('cuil-helper');
    const requiredInputsStep1 = personalInfoSection ? personalInfoSection.querySelectorAll('input[required], select[required]') : [];

    // Campos del formulario - Paso 2
    const calleInput = document.getElementById('calle');
    const alturaInput = document.getElementById('altura');
    const provinciaSelect = document.getElementById('provincia');
    const localidadInput = document.getElementById('localidad');
    const pisoInput = document.getElementById('piso');
    const departamentoInput = document.getElementById('departamento');
    const direccionInput = document.getElementById('direccion');
    const addressFeedback = document.getElementById('address-feedback');
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
        // Paso 1
        legajo: false,
        email: false,
        password: false,
        nombre: false,
        apellido: false,
        rol: false,
        cuil_cuit: true, // Opcional, válido por defecto
        telefono: true, // Opcional, válido por defecto
        step1Complete: false,
        // Paso 2
        calle: false,
        altura: false,
        provincia: false,
        localidad: false,
        step2Complete: false
    };

    // --- FUNCIONES DE VALIDACIÓN ---

    function showError(inputElement, message) {
        if (!inputElement) return;
        const formField = inputElement.closest('.col-md-6, .col-md-8, .col-md-4, .col-12');
        if (!formField) return;

        let errorDiv = formField.querySelector('.invalid-feedback');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.className = 'invalid-feedback';
            inputElement.parentNode.appendChild(errorDiv);
        }

        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        inputElement.classList.remove('is-valid');
        inputElement.classList.add('is-invalid');
    }

    function showSuccess(inputElement) {
        if (!inputElement) return;
        const formField = inputElement.closest('.col-md-6, .col-md-8, .col-md-4, .col-12');
        if (!formField) return;

        const errorDiv = formField.querySelector('.invalid-feedback');
        if (errorDiv) {
            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
        }

        inputElement.classList.remove('is-invalid');
        inputElement.classList.add('is-valid');
    }

    function clearError(inputElement) {
        if (!inputElement) return;
        const formField = inputElement.closest('.col-md-6, .col-md-8, .col-md-4, .col-12');
        if (!formField) return;

        const errorDiv = formField.querySelector('.invalid-feedback');
        if (errorDiv) {
            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
        }

        inputElement.classList.remove('is-invalid');
        inputElement.classList.remove('is-valid');
    }

    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), delay);
        };
    }

    async function verifyAddress() {
        if (!calleInput.value || !alturaInput.value || !localidadInput.value || !provinciaSelect.value) {
            if(addressFeedback) addressFeedback.innerHTML = '';
            return;
        }

        if(addressFeedback) {
            addressFeedback.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Verificando dirección...';
            addressFeedback.className = 'form-text text-muted my-2';
        }

        try {
            const response = await fetch('/admin/usuarios/verificar_direccion', {
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

            if (result.success && addressFeedback) {
                const normalized = result.data;
                const normalizedAddress = `${normalized.calle.nombre} ${normalized.altura.valor}, ${normalized.localidad_censal.nombre}, ${normalized.provincia.nombre}`;
                addressFeedback.innerHTML = `<i class="bi bi-check-circle-fill text-success me-2"></i>Dirección verificada: ${normalizedAddress}`;
                addressFeedback.className = 'form-text text-success my-2';
            } else if(addressFeedback) {
                addressFeedback.innerHTML = `<i class="bi bi-x-circle-fill text-danger me-2"></i>Error: ${result.message || 'No se pudo verificar la dirección.'}`;
                addressFeedback.className = 'form-text text-danger my-2';
            }

        } catch (error) {
            console.error('Error al verificar dirección:', error);
            if(addressFeedback) {
                addressFeedback.innerHTML = '<i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>Error de red al verificar la dirección.';
                addressFeedback.className = 'form-text text-warning my-2';
            }
        }
    }

    const debouncedVerifyAddress = debounce(verifyAddress, 800);

    async function validateField(field, value) {
        let inputElement;

        switch (field) {
            case 'legajo':
                inputElement = legajoInput;
                break;
            case 'email':
                inputElement = emailInput;
                break;
            case 'cuil_cuit':
                inputElement = cuilInput;
                break;
            case 'telefono':
                inputElement = telefonoInput;
                break;
            default:
                return;
        }
        
        const isOptional = ['cuil_cuit', 'telefono'].includes(field);

        if (isOptional && (!value || !value.trim())) {
            clearError(inputElement);
            validationState[field] = true;
            updateStepButtonState();
            return;
        }
        
        if (!value || !value.trim()) {
            showError(inputElement, 'Este campo es obligatorio.');
            validationState[field] = false;
            updateStepButtonState();
            return;
        }

        if (field === 'email') {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                showError(inputElement, 'Por favor, ingrese un email válido (ejemplo: usuario@dominio.com).');
                validationState[field] = false;
                updateStepButtonState();
                return;
            }
        }

        if (field === 'cuil_cuit') {
            const cuilRegex = /^\d{11}$/;
            if (!cuilRegex.test(value)) {
                showError(inputElement, 'El CUIL/CUIT debe contener exactamente 11 dígitos numéricos.');
                validationState[field] = false;
                updateStepButtonState();
                return;
            }
        }

        if (field === 'telefono') {
            const telefonoRegex = /^\d{7,15}$/;
            if (!telefonoRegex.test(value)) {
                showError(inputElement, 'El teléfono debe contener solo números y tener entre 7 y 15 dígitos.');
                validationState[field] = false;
                updateStepButtonState();
                return;
            }
        }

        try {
            const response = await fetch('/admin/usuarios/validar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ field, value })
            });

            if (!response.ok) throw new Error('Error en la validación del servidor');

            const result = await response.json();

            if (!result.valid) {
                showError(inputElement, result.message || 'Valor ya en uso.');
                validationState[field] = false;
            } else {
                showSuccess(inputElement);
                validationState[field] = true;
            }
        } catch (error) {
            console.error('Error al validar campo:', error);
            showError(inputElement, 'Error de red al validar. Intente nuevamente.');
            validationState[field] = false;
        }
        
        updateStepButtonState();
    }

    function validateNombre() {
        const nombre = nombreInput.value.trim();
        if (!nombre) {
            showError(nombreInput, 'El nombre es obligatorio.');
            return false;
        } else if (/\d/.test(nombre)) {
            showError(nombreInput, 'El nombre no puede contener números.');
            return false;
        } else if (nombre.length < 2) {
            showError(nombreInput, 'El nombre debe tener al menos 2 caracteres.');
            return false;
        } else {
            showSuccess(nombreInput);
            return true;
        }
    }

    function validateApellido() {
        const apellido = apellidoInput.value.trim();
        if (!apellido) {
            showError(apellidoInput, 'El apellido es obligatorio.');
            return false;
        } else if (/\d/.test(apellido)) {
            showError(apellidoInput, 'El apellido no puede contener números.');
            return false;
        } else if (apellido.length < 2) {
            showError(apellidoInput, 'El apellido debe tener al menos 2 caracteres.');
            return false;
        } else {
            showSuccess(apellidoInput);
            return true;
        }
    }

    function validateRol() {
        if (!rolSelect.value || rolSelect.value === '') {
            showError(rolSelect, 'Debe seleccionar un rol.');
            return false;
        } else {
            showSuccess(rolSelect);
            return true;
        }
    }

    function validatePassword() {
        if (!passwordInput) return true;
        const password = passwordInput.value;
        if (!password) {
            showError(passwordInput, 'La contraseña es obligatoria.');
            return false;
        } else if (password.length < 8) {
            showError(passwordInput, 'La contraseña debe tener al menos 8 caracteres.');
            return false;
        } else {
            showSuccess(passwordInput);
            return true;
        }
    }

    function validateAddressField(field) {
        let inputElement, fieldName;
        switch(field) {
            case 'calle': inputElement = calleInput; fieldName = 'La calle'; break;
            case 'altura': inputElement = alturaInput; fieldName = 'La altura'; break;
            case 'provincia': inputElement = provinciaSelect; fieldName = 'La provincia'; break;
            case 'localidad': inputElement = localidadInput; fieldName = 'La localidad'; break;
        }
        if (!inputElement) return true;
        const value = inputElement.value.trim();
        if (!value) {
            showError(inputElement, `${fieldName} es obligatoria.`);
            return false;
        } else {
            showSuccess(inputElement);
            return true;
        }
    }

    function updateStepButtonState() {
        if (currentStep === 1) {
            const isValid = checkStep1Complete();
            nextStepBtn.disabled = !isValid;
        } else if (currentStep === 2) {
            const isValid = checkStep2Complete();
            nextStepBtn.disabled = !isValid;
        }
    }

    function checkStep1Complete() {
        validationState.nombre = validateNombre();
        validationState.apellido = validateApellido();
        validationState.rol = validateRol();
        validationState.password = validatePassword();
        validateField('legajo', legajoInput.value);
        validateField('email', emailInput.value);
        validateField('cuil_cuit', cuilInput.value);
        validateField('telefono', telefonoInput.value);

        return validationState.nombre && validationState.apellido && validationState.rol && validationState.password && validationState.legajo && validationState.email && validationState.cuil_cuit && validationState.telefono;
    }

    function checkStep2Complete() {
        validationState.calle = validateAddressField('calle');
        validationState.altura = validateAddressField('altura');
        validationState.provincia = validateAddressField('provincia');
        validationState.localidad = validateAddressField('localidad');
        return validationState.calle && validationState.altura && validationState.provincia && validationState.localidad;
    }

    // --- NAVEGACIÓN ENTRE PASOS ---
    function goToStep(step) {
        currentStep = step;
        const sections = [personalInfoSection, addressInfoSection, faceRegistrationSection];
        const steps = [step1Element, step2Element, step3Element];

        sections.forEach((section, index) => {
            if (section) section.style.display = (index + 1 === step) ? 'block' : 'none';
        });

        steps.forEach((stepEl, index) => {
            if (stepEl) {
                stepEl.classList.toggle('active', index + 1 === step);
                stepEl.classList.toggle('completed', index + 1 < step);
            }
        });
        
        prevStepBtn.style.display = (step > 1) ? 'inline-block' : 'none';
        nextStepBtn.style.display = (step < 3) ? 'inline-block' : 'none';
        submitFormBtn.style.display = (step === 3) ? 'inline-block' : 'none';
        cancelBtn.style.display = (step === 1) ? 'inline-block' : 'none';

        updateStepButtonState();
    }
    
    if (nextStepBtn) nextStepBtn.addEventListener('click', () => goToStep(currentStep + 1));
    if (prevStepBtn) prevStepBtn.addEventListener('click', () => goToStep(currentStep - 1));

    // --- LÓGICA DE LA CÁMARA ---
    // (Se omite por brevedad, es la misma que antes)

    // --- ENVÍO DEL FORMULARIO ---
    if (userForm) {
        userForm.addEventListener('submit', function (e) {
            e.preventDefault(); // Siempre prevenir el envío por defecto

            const isStep1Valid = checkStep1Complete();
            if (!isStep1Valid) {
                goToStep(1);
                showNotificationModal('Formulario Incompleto', 'Por favor, corrija los errores en la sección de Datos Personales.', 'error');
                return;
            }

            const isStep2Valid = checkStep2Complete();
            if (!isStep2Valid) {
                goToStep(2);
                showNotificationModal('Formulario Incompleto', 'Por favor, corrija los errores en la sección de Dirección.', 'error');
                return;
            }

            if (faceRegistrationSection && (!photoConfirmed || !faceDataInput.value)) {
                goToStep(3);
                showNotificationModal('Registro Facial Requerido', 'Por favor, complete el registro facial para continuar.', 'warning');
                return;
            }
            
            // Si todo es válido, enviar el formulario
            if (submitFormBtn) {
                submitFormBtn.disabled = true;
                submitFormBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Creando usuario...';
            }
            userForm.submit();
        });
    }

    // --- INICIALIZACIÓN ---
    goToStep(1); // Iniciar en el paso 1
});