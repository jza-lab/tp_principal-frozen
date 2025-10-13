document.addEventListener('DOMContentLoaded', function () {
    // Si no estamos en la página de crear un nuevo usuario, no ejecutar este script.
    // La variable IS_NEW es inyectada desde el template de Flask.
    if (typeof IS_NEW === 'undefined' || !IS_NEW) {
        console.log('Modo de edición de usuario detectado. El script de creación multi-paso no se ejecutará.');
        return; // Detiene la ejecución del script.
    }

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
    const telefonoInput = document.getElementById('telefono');
    const parte1_cuil = document.getElementById('cuit_parte1');
    const parte2_cuil = document.getElementById('cuit_parte2');
    const parte3_cuil = document.getElementById('cuit_parte3');
    const cuilGroup = document.querySelector('.cuit-input-group'); // Contenedor visual para errores
    const cuilHiddenInput = document.getElementById('cuil_cuit_hidden'); // El campo que guarda el valor final
    const cuilHelper = document.getElementById('cuil-helper');
    const requiredInputsStep1 = personalInfoSection ? personalInfoSection.querySelectorAll('input[required], select[required]') : [];

    // Campos del formulario - Paso 2
    const calleInput = document.getElementById('calle');
    const alturaInput = document.getElementById('altura');
    const provinciaSelect = document.getElementById('provincia');
    const localidadInput = document.getElementById('localidad');
    const pisoInput = document.getElementById('piso');
    const departamentoInput = document.getElementById('depto');
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
        cuil_cuit: false,
        telefono: false,
        turno: false,
        sectores: false,
        step1Complete: false,
        // Paso 2
        calle: false,
        altura: false,
        provincia: false,
        localidad: false,
        step2Complete: false,
        addressVerified: false
    };

    // ==================== SELECTOR DE ROLES ====================
    const rolCards = document.querySelectorAll('.rol-card');
    const rolInput = document.getElementById('role_id');
    let selectedRol = rolInput ? rolInput.value : null;

    // Inicializar rol seleccionado si existe
    if (selectedRol) {
        rolCards.forEach(card => {
            if (card.dataset.rolId === selectedRol) {
                card.classList.add('selected');
            }
        });
        validationState.rol = true;
    }

    rolCards.forEach(card => {
        card.addEventListener('click', function () {
            // Remover selección anterior
            rolCards.forEach(c => c.classList.remove('selected'));

            // Seleccionar nuevo rol
            this.classList.add('selected');
            selectedRol = this.dataset.rolId;
            if (rolInput) rolInput.value = selectedRol;

            validationState.rol = true;
            updateStepButtonState();

            console.log('Rol seleccionado:', selectedRol);
        });
    });

    // ==================== SELECTOR DE TURNOS ====================
    const turnoCards = document.querySelectorAll('.turno-card');
    const turnoInput = document.getElementById('turno_id');
    let selectedTurno = turnoInput ? turnoInput.value : null;

    // Inicializar turno seleccionado si existe
    if (selectedTurno) {
        turnoCards.forEach(card => {
            if (card.dataset.turnoId === selectedTurno) {
                card.classList.add('selected');
            }
        });
        validationState.turno = true;
    }

    turnoCards.forEach(card => {
        card.addEventListener('click', function () {
            // Remover selección anterior
            turnoCards.forEach(c => c.classList.remove('selected'));

            // Seleccionar nuevo turno
            this.classList.add('selected');
            selectedTurno = this.dataset.turnoId;
            if (turnoInput) turnoInput.value = selectedTurno;

            validationState.turno = true;
            updateStepButtonState();

            console.log('Turno seleccionado:', selectedTurno);
        });
    });

    // ==================== SELECTOR DE SECTORES ====================
    const MAX_SECTORES = 2;
    let selectedSectores = [];

    const sectorCards = document.querySelectorAll('.sector-card');
    const sectoresInput = document.getElementById('sectores');
    const counterText = document.getElementById('counterText');
    const sectoresCounter = document.getElementById('sectoresCounter');

    // Inicializar sectores seleccionados si existen
    sectorCards.forEach(card => {
        if (card.dataset.selected === 'true') {
            card.classList.add('selected');
            selectedSectores.push(card.dataset.sectorId);
        }
    });

    if (selectedSectores.length > 0) {
        validationState.sectores = true;
        updateSectorOrder();
        updateSectoresCounter();
        if (sectoresInput) sectoresInput.value = JSON.stringify(selectedSectores);
    }

    function updateSectoresCounter() {
        if (!counterText) return;

        counterText.textContent = `${selectedSectores.length}/${MAX_SECTORES}`;

        if (selectedSectores.length === MAX_SECTORES) {
            sectoresCounter.classList.add('warning');
            // Deshabilitar cards no seleccionadas
            sectorCards.forEach(card => {
                if (!card.classList.contains('selected')) {
                    card.classList.add('disabled');
                }
            });
        } else {
            sectoresCounter.classList.remove('warning');
            // Habilitar todas las cards
            sectorCards.forEach(card => {
                card.classList.remove('disabled');
            });
        }

        // Actualizar estado de validación
        validationState.sectores = selectedSectores.length > 0;
        updateStepButtonState();
    }

    function updateSectorOrder() {
        sectorCards.forEach(card => {
            if (card.classList.contains('selected')) {
                const order = selectedSectores.indexOf(card.dataset.sectorId) + 1;
                const badge = card.querySelector('.sector-badge');
                if (badge) badge.textContent = order;
            }
        });
    }

    sectorCards.forEach(card => {
        card.addEventListener('click', function () {
            if (this.classList.contains('disabled')) return;

            const sectorId = this.dataset.sectorId;

            if (this.classList.contains('selected')) {
                // Deseleccionar
                this.classList.remove('selected');
                selectedSectores = selectedSectores.filter(id => id !== sectorId);
            } else {
                // Seleccionar solo si no se alcanzó el máximo
                if (selectedSectores.length < MAX_SECTORES) {
                    this.classList.add('selected');
                    selectedSectores.push(sectorId);
                }
            }

            updateSectorOrder();
            updateSectoresCounter();
            if (sectoresInput) sectoresInput.value = JSON.stringify(selectedSectores);

            console.log('Sectores seleccionados:', selectedSectores);
        });
    });

    // Inicializar contador
    updateSectoresCounter();

    // --- FUNCIONES DE VALIDACIÓN ---

    function showError(inputElement, message) {
        if (!inputElement) return;
        const formField = inputElement.closest('.col-md-6, .col-md-8, .col-md-4, .col-12');
        if (!formField) return;

        // Ocultar mensaje de éxito si existe
        const successDiv = formField.querySelector('.valid-feedback');
        if (successDiv) successDiv.style.display = 'none';

        let errorDiv = formField.querySelector('.invalid-feedback');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.className = 'invalid-feedback';

            // Lógica para insertar el error en el lugar correcto
            if (inputElement.classList.contains('cuit-input-group')) {
                inputElement.insertAdjacentElement('afterend', errorDiv);
            } else {
                inputElement.parentNode.appendChild(errorDiv);
            }
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

        // Ocultar mensaje de error
        const errorDiv = formField.querySelector('.invalid-feedback');
        if (errorDiv) {
            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
        }

        // Lógica para crear y mostrar el mensaje de éxito
        let successDiv = formField.querySelector('.valid-feedback');
        if (!successDiv) {
            successDiv = document.createElement('div');
            successDiv.className = 'valid-feedback';

            if (inputElement.classList.contains('cuit-input-group')) {
                inputElement.insertAdjacentElement('afterend', successDiv);
            } else {
                inputElement.parentNode.appendChild(successDiv);
            }
        }
        successDiv.textContent = 'Válido.';
        successDiv.style.display = 'block';

        inputElement.classList.remove('is-invalid');
        inputElement.classList.add('is-valid');
    }

    function handleCuitChange() {
        // Sanitizar: solo números en cada campo
        if (parte1_cuil) parte1_cuil.value = parte1_cuil.value.replace(/\D/g, '');
        if (parte2_cuil) parte2_cuil.value = parte2_cuil.value.replace(/\D/g, '');
        if (parte3_cuil) parte3_cuil.value = parte3_cuil.value.replace(/\D/g, '');

        const val1 = parte1_cuil.value;
        const val2 = parte2_cuil.value;
        const val3 = parte3_cuil.value;
        const totalLength = (val1 + val2 + val3).length;
        const remaining = 11 - totalLength;

        if (totalLength > 0 && remaining > 0) {
            if (cuilHelper) {
                cuilHelper.textContent = `Faltan ${remaining} dígito(s).`;
                cuilHelper.style.display = 'block';
            }
        } else {
            if (cuilHelper) cuilHelper.style.display = 'none';
        }

        const combinedFormattedValue = `${val1}-${val2}-${val3}`;
        const valueForValidation = (val1 || val2 || val3) ? combinedFormattedValue : '';

        // 3. Asigna ese string al campo oculto que se enviará al backend
        if (cuilHiddenInput) {
            cuilHiddenInput.value = valueForValidation;
        }
        
        validateCuit(); // Llama a la validación específica
    }

    function validateCuit() {
        const value = cuilHiddenInput ? cuilHiddenInput.value : '';

        if (!value) {
            showError(cuilGroup, 'El CUIL/CUIT es un campo obligatorio.');
            validationState.cuil_cuit = false;
        } else {
            const cuilRegex = /^\d{2}-\d{8}-\d{1}$/;
            if (!cuilRegex.test(value)) {
                showError(cuilGroup, 'El formato del CUIL/CUIT no es válido o está incompleto.');
                validationState.cuil_cuit = false;
            } else {
                showSuccess(cuilGroup);
                validationState.cuil_cuit = true;
            }
        }
        updateStepButtonState();
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
        return function (...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), delay);
        };
    }

    async function verifyAddress() {
        // Reset verification status whenever a check is triggered
        validationState.addressVerified = false;

        if (!calleInput.value || !alturaInput.value || !localidadInput.value || !provinciaSelect.value) {
            if (addressFeedback) addressFeedback.innerHTML = '';
            updateStepButtonState(); // Update button state immediately
            return;
        }

        if (addressFeedback) {
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
                validationState.addressVerified = true;
            } else if (addressFeedback) {
                addressFeedback.innerHTML = `<i class="bi bi-x-circle-fill text-danger me-2"></i>Error: ${result.message || 'No se pudo verificar la dirección.'}`;
                addressFeedback.className = 'form-text text-danger my-2';
                validationState.addressVerified = false;
            }

        } catch (error) {
            console.error('Error al verificar dirección:', error);
            if (addressFeedback) {
                addressFeedback.innerHTML = '<i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>Error de red al verificar la dirección.';
                addressFeedback.className = 'form-text text-warning my-2';
            }
            validationState.addressVerified = false;
        } finally {
            updateStepButtonState();
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

        // --- Validaciones de formato ---
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

        // --- Validación asíncrona (unicidad) ---
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
                showSuccess(inputElement); // Éxito
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
            validationState.nombre = false;
        } else if (/\d/.test(nombre)) {
            showError(nombreInput, 'El nombre no puede contener números.');
            validationState.nombre = false;
        } else if (nombre.length < 2) {
            showError(nombreInput, 'El nombre debe tener al menos 2 caracteres.');
            validationState.nombre = false;
        } else {
            showSuccess(nombreInput);
            validationState.nombre = true;
        }

        updateStepButtonState();
    }

    function validateApellido() {
        const apellido = apellidoInput.value.trim();

        if (!apellido) {
            showError(apellidoInput, 'El apellido es obligatorio.');
            validationState.apellido = false;
        } else if (/\d/.test(apellido)) {
            showError(apellidoInput, 'El apellido no puede contener números.');
            validationState.apellido = false;
        } else if (apellido.length < 2) {
            showError(apellidoInput, 'El apellido debe tener al menos 2 caracteres.');
            validationState.apellido = false;
        } else {
            showSuccess(apellidoInput);
            validationState.apellido = true;
        }

        updateStepButtonState();
    }

    function validateRol() {
        if (!rolSelect.value || rolSelect.value === '') {
            showError(rolSelect, 'Debe seleccionar un rol.');
            validationState.rol = false;
        } else {
            showSuccess(rolSelect);
            validationState.rol = true;
        }

        updateStepButtonState();
    }

    function validatePassword() {
        if (!passwordInput) {
            validationState.password = true;
            return;
        }

        const password = passwordInput.value;

        if (!password) {
            showError(passwordInput, 'La contraseña es obligatoria.');
            validationState.password = false;
        } else if (password.length < 8) {
            showError(passwordInput, 'La contraseña debe tener al menos 8 caracteres.');
            validationState.password = false;
        } else {
            showSuccess(passwordInput);
            validationState.password = true;
        }

        updateStepButtonState();
    }

    function validateAddressField(field) {
        let inputElement, fieldName;

        switch (field) {
            case 'calle':
                inputElement = calleInput;
                fieldName = 'La calle';
                break;
            case 'altura':
                inputElement = alturaInput;
                fieldName = 'La altura';
                break;
            case 'provincia':
                inputElement = provinciaSelect;
                fieldName = 'La provincia';
                break;
            case 'localidad':
                inputElement = localidadInput;
                fieldName = 'La localidad';
                break;
        }

        if (!inputElement) return;

        const value = inputElement.value.trim();

        if (!value) {
            showError(inputElement, `${fieldName} es obligatoria.`);
            validationState[field] = false;
        } else {
            showSuccess(inputElement);
            validationState[field] = true;
        }

        updateStepButtonState();
    }

    function checkStep1Complete() {
        let allFilled = true;

        requiredInputsStep1.forEach(input => {
            if (!input.value || !input.value.trim()) {
                allFilled = false;
            }
        });

        const isStep1Valid = validationState.legajo &&
            validationState.email &&
            validationState.nombre &&
            validationState.apellido &&
            validationState.rol &&
            validationState.password &&
            validationState.cuil_cuit &&
            validationState.telefono &&
            validationState.turno &&
            validationState.sectores &&
            allFilled;

        validationState.step1Complete = isStep1Valid;
        return isStep1Valid;
    }

    function checkStep2Complete() {
        let allFilled = true;

        requiredInputsStep2.forEach(input => {
            if (!input.value || !input.value.trim()) {
                allFilled = false;
            }
        });

        const isStep2Valid = validationState.calle &&
            validationState.altura &&
            validationState.provincia &&
            validationState.localidad &&
            allFilled &&
            validationState.addressVerified;

        validationState.step2Complete = isStep2Valid;
        return isStep2Valid;
    }

    function updateStepButtonState() {
        if (currentStep === 1) {
            const isValid = checkStep1Complete();
            nextStepBtn.disabled = !isValid;

            if (isValid) {
                nextStepBtn.classList.remove('btn-secondary');
                nextStepBtn.classList.add('btn-primary');
            } else {
                nextStepBtn.classList.remove('btn-primary');
                nextStepBtn.classList.add('btn-secondary');
            }
        } else if (currentStep === 2) {
            const isValid = checkStep2Complete();
            nextStepBtn.disabled = !isValid;

            if (isValid) {
                nextStepBtn.classList.remove('btn-secondary');
                nextStepBtn.classList.add('btn-primary');
            } else {
                nextStepBtn.classList.remove('btn-primary');
                nextStepBtn.classList.add('btn-secondary');
            }
        }
    }

    // --- EVENT LISTENERS PARA VALIDACIÓN - PASO 1 ---

    if (nombreInput) {
        nombreInput.addEventListener('blur', validateNombre);
        nombreInput.addEventListener('input', function () {
            if (this.value.trim().length > 0) {
                validateNombre();
            }
        });
    }

    if (apellidoInput) {
        apellidoInput.addEventListener('blur', validateApellido);
        apellidoInput.addEventListener('input', function () {
            if (this.value.trim().length > 0) {
                validateApellido();
            }
        });
    }

    if (parte1_cuil && parte2_cuil && parte3_cuil) {
        parte1_cuil.addEventListener('input', handleCuitChange);
        parte2_cuil.addEventListener('input', handleCuitChange);
        parte3_cuil.addEventListener('input', handleCuitChange);

        parte1_cuil.addEventListener('keyup', () => { if (parte1_cuil.value.length === 2) parte2_cuil.focus(); });
        parte2_cuil.addEventListener('keyup', () => { if (parte2_cuil.value.length === 8) parte3_cuil.focus(); });
    }

    if (rolSelect) {
        rolSelect.addEventListener('change', validateRol);
        rolSelect.addEventListener('blur', validateRol);
    }

    if (legajoInput) {
        legajoInput.addEventListener('blur', function () {
            validateField('legajo', this.value);
        });
    }

    if (emailInput) {
        emailInput.addEventListener('blur', function () {
            validateField('email', this.value);
        });
    }


    if (telefonoInput) {
        telefonoInput.addEventListener('input', function () {
            // Sanitizar: solo números
            this.value = this.value.replace(/\D/g, '');
        });

        telefonoInput.addEventListener('blur', function () {
            validateField('telefono', this.value);
        });
    }

    if (passwordInput) {
        passwordInput.addEventListener('blur', validatePassword);
        passwordInput.addEventListener('input', function () {
            if (this.value.length >= 8) {
                validatePassword();
            }
        });
    }

    requiredInputsStep1.forEach(input => {
        input.addEventListener('input', () => {
            updateStepButtonState();
        });
    });

    // --- EVENT LISTENERS PARA VALIDACIÓN - PASO 2 ---

    if (calleInput) {
        calleInput.addEventListener('blur', () => validateAddressField('calle'));
        calleInput.addEventListener('input', () => {
            debouncedVerifyAddress();
            if (calleInput.value.trim().length > 0) {
                validateAddressField('calle');
            }
        });
    }

    if (alturaInput) {
        alturaInput.addEventListener('blur', () => validateAddressField('altura'));
        alturaInput.addEventListener('input', () => {
            debouncedVerifyAddress();
            if (alturaInput.value.trim().length > 0) {
                validateAddressField('altura');
            }
        });
    }

    if (provinciaSelect) {
        provinciaSelect.addEventListener('change', () => {
            verifyAddress();
            validateAddressField('provincia');
        });
        provinciaSelect.addEventListener('blur', () => validateAddressField('provincia'));
    }

    if (localidadInput) {
        localidadInput.addEventListener('blur', () => validateAddressField('localidad'));
        localidadInput.addEventListener('input', () => {
            debouncedVerifyAddress();
            if (localidadInput.value.trim().length > 0) {
                validateAddressField('localidad');
            }
        });
    }

    requiredInputsStep2.forEach(input => {
        input.addEventListener('input', () => {
            updateStepButtonState();
        });
    });

    // --- NAVEGACIÓN ENTRE PASOS ---

    function goToStep(step) {
        if (step === 1) {
            currentStep = 1;
            step1Element.classList.add('active');
            step1Element.classList.remove('completed');
            step2Element.classList.remove('active', 'completed');
            step3Element.classList.remove('active', 'completed');

            personalInfoSection.style.display = 'block';
            if (addressInfoSection) addressInfoSection.style.display = 'none';
            if (faceRegistrationSection) faceRegistrationSection.style.display = 'none';

            nextStepBtn.style.display = 'inline-block';
            nextStepBtn.innerHTML = 'Siguiente <i class="bi bi-arrow-right ms-1"></i>';
            prevStepBtn.style.display = 'none';
            submitFormBtn.style.display = 'none';
            cancelBtn.style.display = 'inline-block';

            updateStepButtonState();

        } else if (step === 2) {
            if (nextStepBtn.disabled) {
                showNotificationModal('Formulario Incompleto', 'Por favor, complete todos los campos obligatorios antes de continuar.', 'warning');
                return;
            }

            currentStep = 2;
            step1Element.classList.remove('active');
            step1Element.classList.add('completed');
            step2Element.classList.add('active');
            step2Element.classList.remove('completed');
            step3Element.classList.remove('active');

            personalInfoSection.style.display = 'none';
            if (addressInfoSection) addressInfoSection.style.display = 'block';
            if (faceRegistrationSection) faceRegistrationSection.style.display = 'none';

            nextStepBtn.style.display = 'inline-block';
            nextStepBtn.innerHTML = 'Siguiente <i class="bi bi-arrow-right ms-1"></i>';
            prevStepBtn.style.display = 'inline-block';
            submitFormBtn.style.display = 'none';
            cancelBtn.style.display = 'none';

            updateStepButtonState();

        } else if (step === 3) {
            if (!checkStep2Complete()) {
                const message = !validationState.addressVerified
                    ? 'La dirección ingresada no pudo ser verificada. Por favor, corrÃ­jala antes de continuar.'
                    : 'Por favor, complete todos los campos de dirección obligatorios antes de continuar.';
                showNotificationModal('Dirección Inválida', message, 'warning');
                return;
            }

            currentStep = 3;
            step1Element.classList.add('completed');
            step2Element.classList.remove('active');
            step2Element.classList.add('completed');
            step3Element.classList.add('active');

            personalInfoSection.style.display = 'none';
            if (addressInfoSection) addressInfoSection.style.display = 'none';
            if (faceRegistrationSection) faceRegistrationSection.style.display = 'block';

            nextStepBtn.style.display = 'none';
            prevStepBtn.style.display = 'inline-block';
            submitFormBtn.style.display = 'inline-block';
            submitFormBtn.disabled = true;
            cancelBtn.style.display = 'none';
        }
    }

    if (nextStepBtn) {
        nextStepBtn.addEventListener('click', () => {
            if (currentStep === 1) {
                goToStep(2);
            } else if (currentStep === 2) {
                goToStep(3);
            }
        });
    }

    if (prevStepBtn) {
        prevStepBtn.addEventListener('click', () => {
            if (currentStep === 2) {
                goToStep(1);
            } else if (currentStep === 3 && !photoTaken) {
                goToStep(2);
            }
        });
    }

    // --- LÓGICA DE LA CÁMARA ---

    if (startCameraBtn) {
        startCameraBtn.addEventListener('click', async function () {
            if (photoConfirmed) {
                console.log('Foto ya confirmada, no se puede iniciar la cámara nuevamente');
                return;
            }

            try {
                videoStream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        width: { ideal: 640 },
                        height: { ideal: 480 },
                        facingMode: 'user'
                    }
                });

                videoElement.srcObject = videoStream;

                const cameraInactive = document.getElementById('cameraInactive');
                const cameraActive = document.getElementById('cameraActive');

                if (cameraInactive) cameraInactive.style.display = 'none';
                if (cameraActive) cameraActive.style.display = 'block';

                this.disabled = true;
                this.innerHTML = '<i class="bi bi-camera-video-fill me-2"></i>Cámara Activa';

            } catch (error) {
                console.error('Error al acceder a la cámara:', error);
                showNotificationModal('Error de Cámara', 'No se pudo acceder a la cámara. Verifique los permisos y que no esté siendo usada por otra aplicación.', 'error');
            }
        });
    }

    if (capturePhotoBtn) {
        capturePhotoBtn.addEventListener('click', async function () {
            if (photoConfirmed) {
                console.log('Foto ya confirmada, no se puede capturar nuevamente');
                return;
            }

            if (!videoStream || !videoElement.srcObject) {
                showNotificationModal('Cámara no Iniciada', 'Por favor, inicie la cámara antes de capturar una foto.', 'warning');
                return;
            }

            const context = canvasElement.getContext('2d');
            canvasElement.width = videoElement.videoWidth;
            canvasElement.height = videoElement.videoHeight;
            context.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height);

            const imageData = canvasElement.toDataURL('image/jpeg', 0.8);

            this.disabled = true;
            this.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Verificando rostro...';

            if (prevStepBtn) {
                prevStepBtn.disabled = true;
                prevStepBtn.title = 'No puede volver después de capturar una foto';
            }

            try {
                const response = await fetch('/admin/usuarios/validar_rostro', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: imageData })
                });

                if (!response.ok) {
                    throw new Error('Error al validar el rostro');
                }

                const result = await response.json();

                if (!result.valid) {
                    const errorMessage = result.message || 'Error al validar el rostro';
                    showNotificationModal('Error de Validación Facial', errorMessage, 'error');

                    const photoPreview = document.getElementById('photoPreview');
                    if (photoPreview) {
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'alert alert-danger mt-3';
                        errorDiv.innerHTML = `<i class="bi bi-exclamation-triangle me-2"></i>${errorMessage}`;
                        photoPreview.appendChild(errorDiv);

                        setTimeout(() => errorDiv.remove(), 5000);
                    }

                    this.disabled = false;
                    this.innerHTML = '<i class="bi bi-camera me-2"></i>Capturar Foto';

                    if (prevStepBtn) {
                        prevStepBtn.disabled = false;
                        prevStepBtn.title = '';
                    }

                    faceDataInput.value = '';

                    return;
                }

                capturedImage.src = imageData;
                faceDataInput.value = imageData;

                const cameraActive = document.getElementById('cameraActive');
                const photoPreview = document.getElementById('photoPreview');

                if (cameraActive) cameraActive.style.display = 'none';
                if (photoPreview) photoPreview.style.display = 'block';

                photoTaken = true;

                this.disabled = false;
                this.innerHTML = '<i class="bi bi-camera me-2"></i>Capturar Foto';

            } catch (error) {
                console.error('Error al validar rostro:', error);
                showNotificationModal('Error de Conexión', 'No se pudo validar el rostro. Verifique su conexión e intente nuevamente.', 'error');

                this.disabled = false;
                this.innerHTML = '<i class="bi bi-camera me-2"></i>Capturar Foto';

                if (prevStepBtn) {
                    prevStepBtn.disabled = false;
                    prevStepBtn.title = '';
                }
            }
        });
    }

    if (confirmPhotoBtn) {
        confirmPhotoBtn.addEventListener('click', function () {
            if (photoConfirmed) {
                console.log('Foto ya confirmada');
                return;
            }

            if (!photoTaken || !faceDataInput.value) {
                showNotificationModal('Foto Requerida', 'Por favor, capture una foto antes de confirmar.', 'warning');
                return;
            }

            if (videoStream) {
                videoStream.getTracks().forEach(track => track.stop());
                videoStream = null;
            }

            photoConfirmed = true;
            step3Element.classList.add('completed');

            this.disabled = true;
            if (retakePhotoBtn) retakePhotoBtn.disabled = true;
            if (retakePhotoBtn2) retakePhotoBtn2.disabled = true;
            if (capturePhotoBtn) capturePhotoBtn.disabled = true;
            if (startCameraBtn) startCameraBtn.disabled = true;

            this.innerHTML = '<i class="bi bi-check-circle-fill me-2"></i>Foto Confirmada';
            this.classList.remove('btn-success');
            this.classList.add('btn-secondary');

            if (submitFormBtn) {
                submitFormBtn.disabled = false;
                submitFormBtn.classList.remove('btn-secondary');
                submitFormBtn.classList.add('btn-success');
            }

            showNotificationModal('Éxito', 'Rostro confirmado correctamente. Ahora puede finalizar la creación del usuario.', 'success');
        });
    }

    function retakePhoto() {
        if (photoConfirmed) {
            console.log('No se puede retomar la foto después de confirmar');
            return;
        }

        const photoPreview = document.getElementById('photoPreview');
        const cameraActive = document.getElementById('cameraActive');

        if (photoPreview) photoPreview.style.display = 'none';
        if (cameraActive) cameraActive.style.display = 'block';

        photoTaken = false;
        faceDataInput.value = '';

        if (prevStepBtn) {
            prevStepBtn.disabled = false;
            prevStepBtn.title = '';
        }

        if (!videoStream || !videoStream.active) {
            if (startCameraBtn) {
                startCameraBtn.disabled = false;
                startCameraBtn.innerHTML = '<i class="bi bi-camera-video me-2"></i>Activar Cámara';
            }
        }
    }

    if (retakePhotoBtn) {
        retakePhotoBtn.addEventListener('click', retakePhoto);
    }

    if (retakePhotoBtn2) {
        retakePhotoBtn2.addEventListener('click', retakePhoto);
    }

    // --- ENVÍO DEL FORMULARIO ---

    if (userForm) {
        userForm.addEventListener('submit', function (e) {
            if (currentStep === 3 && !photoConfirmed) {
                e.preventDefault();
                showNotificationModal('Rostro no Confirmado', 'Por favor, capture y confirme su rostro antes de crear el usuario.', 'warning');
                return false;
            }

            if (!faceDataInput || !faceDataInput.value) {
                e.preventDefault();
                showNotificationModal('Foto Requerida', 'No se ha capturado ninguna foto. Por favor, capture su rostro para continuar.', 'warning');
                return false;
            }

            if (submitFormBtn) {
                submitFormBtn.disabled = true;
                submitFormBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Creando usuario...';
            }
        });
    }

    // --- LIMPIEZA AL SALIR ---

    window.addEventListener('beforeunload', function () {
        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
        }
    });

    // --- INICIALIZACIÓN ---
    updateStepButtonState();

    // Validar campos iniciales si tienen valores
    if (nombreInput && nombreInput.value.trim()) validateNombre();
    if (apellidoInput && apellidoInput.value.trim()) validateApellido();
    if (rolSelect && rolSelect.value) validateRol();
    if (legajoInput && legajoInput.value.trim()) validateField('legajo', legajoInput.value);
    if (emailInput && emailInput.value.trim()) validateField('email', emailInput.value);
    if (passwordInput && passwordInput.value) validatePassword();
    if (parte1_cuil && (parte1_cuil.value || parte2_cuil.value || parte3_cuil.value)) {
        handleCuitChange();
    }
    if (telefonoInput && telefonoInput.value.trim()) validateField('telefono', telefonoInput.value);

    console.log('Formulario de usuario mejorado inicializado correctamente');
});