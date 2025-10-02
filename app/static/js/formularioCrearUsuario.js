document.addEventListener('DOMContentLoaded', function () {
    // --- ELEMENTOS DEL DOM ---
    const userForm = document.getElementById('userForm');
    const step1Element = document.getElementById('step1');
    const step2Element = document.getElementById('step2');
    const basicInfoSection = document.getElementById('basicInfo');
    const faceRegistrationSection = document.getElementById('faceRegistration');

    // Botones de navegación
    const nextStepBtn = document.getElementById('nextStep');
    const prevStepBtn = document.getElementById('prevStep');
    const submitFormBtn = document.getElementById('submitForm');
    const cancelBtn = document.getElementById('cancelBtn');

    // Campos del formulario
    const legajoInput = document.getElementById('legajo');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const nombreInput = document.getElementById('nombre');
    const apellidoInput = document.getElementById('apellido');
    const rolSelect = document.getElementById('rol');
    const requiredInputs = basicInfoSection.querySelectorAll('input[required], select[required]');

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
        legajo: false,
        email: false,
        password: false,
        nombre: false,
        apellido: false,
        rol: false,
        requiredFields: false
    };

    // --- FUNCIONES DE VALIDACIÓN ---

    function showError(inputElement, message) {
        if (!inputElement) return;
        
        const formField = inputElement.closest('.col-md-6, .col-12');
        if (!formField) return;
        
        let errorDiv = formField.querySelector('.invalid-feedback');
        
        // Crear el div de error si no existe
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.className = 'invalid-feedback';
            inputElement.parentNode.appendChild(errorDiv);
        }
        
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        inputElement.classList.add('is-invalid');
        inputElement.classList.remove('is-valid');
    }

    function clearError(inputElement) {
        if (!inputElement) return;
        
        const formField = inputElement.closest('.col-md-6, .col-12');
        if (!formField) return;
        
        const errorDiv = formField.querySelector('.invalid-feedback');
        if (errorDiv) {
            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
        }
        
        inputElement.classList.remove('is-invalid');
        inputElement.classList.add('is-valid');
    }

    async function validateField(field, value) {
        let inputElement;
        
        if (field === 'legajo') {
            inputElement = legajoInput;
        } else if (field === 'email') {
            inputElement = emailInput;
        }
        
        clearError(inputElement);

        if (!value || !value.trim()) {
            showError(inputElement, 'Este campo es obligatorio.');
            validationState[field] = false;
            updateNextButtonState();
            return;
        }

        // Validación específica de email
        if (field === 'email') {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                showError(inputElement, 'Por favor, ingrese un email válido (ejemplo: usuario@dominio.com).');
                validationState[field] = false;
                updateNextButtonState();
                return;
            }
        }

        try {
            const response = await fetch('/admin/usuarios/validar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ field, value })
            });

            if (!response.ok) {
                throw new Error('Error en la validación del servidor');
            }

            const result = await response.json();

            if (!result.valid) {
                showError(inputElement, result.message || 'Valor ya en uso.');
                validationState[field] = false;
            } else {
                validationState[field] = true;
            }
        } catch (error) {
            console.error('Error al validar campo:', error);
            showError(inputElement, 'Error de red al validar. Intente nuevamente.');
            validationState[field] = false;
        }
        
        updateNextButtonState();
    }

    function validateNombre() {
        clearError(nombreInput);
        
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
            validationState.nombre = true;
        }
        
        updateNextButtonState();
    }

    function validateApellido() {
        clearError(apellidoInput);
        
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
            validationState.apellido = true;
        }
        
        updateNextButtonState();
    }

    function validateRol() {
        clearError(rolSelect);
        
        if (!rolSelect.value || rolSelect.value === '') {
            showError(rolSelect, 'Debe seleccionar un rol.');
            validationState.rol = false;
        } else {
            validationState.rol = true;
        }
        
        updateNextButtonState();
    }

    function validatePassword() {
        clearError(passwordInput);
        
        const password = passwordInput.value;
        
        if (!password) {
            showError(passwordInput, 'La contraseña es obligatoria.');
            validationState.password = false;
        } else if (password.length < 8) {
            showError(passwordInput, 'La contraseña debe tener al menos 8 caracteres.');
            validationState.password = false;
        } else {
            validationState.password = true;
        }
        
        updateNextButtonState();
    }

    function checkRequiredFields() {
        let allFilled = true;
        
        requiredInputs.forEach(input => {
            if (!input.value || !input.value.trim()) {
                allFilled = false;
            }
        });
        
        validationState.requiredFields = allFilled;
        updateNextButtonState();
    }

    function updateNextButtonState() {
        const isStep1Valid = Object.values(validationState).every(isValid => isValid === true);
        nextStepBtn.disabled = !isStep1Valid;
        
        if (isStep1Valid) {
            nextStepBtn.classList.remove('btn-secondary');
            nextStepBtn.classList.add('btn-primary');
        } else {
            nextStepBtn.classList.remove('btn-primary');
            nextStepBtn.classList.add('btn-secondary');
        }
    }

    // --- EVENT LISTENERS PARA VALIDACIÓN ---

    if (nombreInput) {
        nombreInput.addEventListener('blur', validateNombre);
        nombreInput.addEventListener('input', function() {
            checkRequiredFields();
            // Validar en tiempo real si ya hay contenido
            if (this.value.trim().length > 0) {
                validateNombre();
            }
        });
    }

    if (apellidoInput) {
        apellidoInput.addEventListener('blur', validateApellido);
        apellidoInput.addEventListener('input', function() {
            checkRequiredFields();
            // Validar en tiempo real si ya hay contenido
            if (this.value.trim().length > 0) {
                validateApellido();
            }
        });
    }

    if (rolSelect) {
        rolSelect.addEventListener('change', validateRol);
        rolSelect.addEventListener('blur', validateRol);
    }

    if (legajoInput) {
        legajoInput.addEventListener('blur', function() {
            validateField('legajo', this.value);
        });
        legajoInput.addEventListener('input', checkRequiredFields);
    }

    if (emailInput) {
        emailInput.addEventListener('blur', function() {
            validateField('email', this.value);
        });
        emailInput.addEventListener('input', checkRequiredFields);
    }

    if (passwordInput) {
        passwordInput.addEventListener('blur', validatePassword);
        passwordInput.addEventListener('input', function() {
            checkRequiredFields();
            if (this.value.length >= 8) {
                validatePassword();
            }
        });
    }

    // Validar todos los campos requeridos al cambiar
    requiredInputs.forEach(input => {
        input.addEventListener('input', checkRequiredFields);
    });

    // --- NAVEGACIÓN ENTRE PASOS ---

    function goToStep(step) {
        if (step === 1) {
            currentStep = 1;
            step1Element.classList.add('active');
            step1Element.classList.remove('completed');
            step2Element.classList.remove('active', 'completed');
            
            basicInfoSection.style.display = 'block';
            faceRegistrationSection.style.display = 'none';
            
            nextStepBtn.style.display = 'inline-block';
            prevStepBtn.style.display = 'none';
            submitFormBtn.style.display = 'none';
            cancelBtn.style.display = 'inline-block';
            
        } else if (step === 2) {
            if (nextStepBtn.disabled) {
                showNotificationModal('Formulario Incompleto', 'Por favor, corrija los errores resaltados antes de continuar.', 'warning');
                return;
            }
            
            currentStep = 2;
            step1Element.classList.remove('active');
            step1Element.classList.add('completed');
            step2Element.classList.add('active');

            basicInfoSection.style.display = 'none';
            faceRegistrationSection.style.display = 'block';

            nextStepBtn.style.display = 'none';
            prevStepBtn.style.display = 'inline-block';
            submitFormBtn.style.display = 'inline-block';
            cancelBtn.style.display = 'none';
        }
    }
    
    if (nextStepBtn) {
        nextStepBtn.addEventListener('click', () => goToStep(2));
    }
    
    if (prevStepBtn) {
        prevStepBtn.addEventListener('click', () => goToStep(1));
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
                        width: { ideal: 320 }, 
                        height: { ideal: 240 }, 
                        facingMode: 'user' 
                    }
                });
                
                videoElement.srcObject = videoStream;
                
                const cameraInactive = document.getElementById('cameraInactive');
                const cameraActive = document.getElementById('cameraActive');
                
                if (cameraInactive) cameraInactive.style.display = 'none';
                if (cameraActive) cameraActive.style.display = 'block';
                
                this.disabled = true;
                this.textContent = 'Cámara Activa';
                
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
            
            // Mostrar estado de carga
            this.disabled = true;
            this.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Verificando rostro...';
            
            // Bloquear botón de volver después de capturar foto
            if (prevStepBtn) {
                prevStepBtn.disabled = true;
                prevStepBtn.title = 'No puede volver después de capturar una foto';
            }
            
            try {
                // Validar el rostro con el backend
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
                    // Mostrar error específico
                    const errorMessage = result.message || 'Error al validar el rostro';
                    showNotificationModal('Error de Validación Facial', errorMessage, 'error');
                    
                    // Mostrar error visual en la interfaz
                    const photoPreview = document.getElementById('photoPreview');
                    if (photoPreview) {
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'alert alert-danger mt-3';
                        errorDiv.innerHTML = `<i class="bi bi-exclamation-triangle me-2"></i>${errorMessage}`;
                        photoPreview.appendChild(errorDiv);
                        
                        // Remover el error después de 5 segundos
                        setTimeout(() => errorDiv.remove(), 5000);
                    }
                    
                    // Permitir retomar foto
                    this.disabled = false;
                    this.innerHTML = '<i class="bi bi-camera me-2"></i>Capturar Foto';
                    
                    // Desbloquear botón de volver
                    if (prevStepBtn) {
                        prevStepBtn.disabled = false;
                        prevStepBtn.title = '';
                    }
                    
                    // Limpiar la foto capturada
                    faceDataInput.value = '';
                    
                    return;
                }
                
                // Si la validación es exitosa, mostrar la foto
                capturedImage.src = imageData;
                faceDataInput.value = imageData;
                
                const cameraActive = document.getElementById('cameraActive');
                const photoPreview = document.getElementById('photoPreview');
                
                if (cameraActive) cameraActive.style.display = 'none';
                if (photoPreview) photoPreview.style.display = 'block';
                
                photoTaken = true;
                
                // Restaurar botón
                this.disabled = false;
                this.innerHTML = '<i class="bi bi-camera me-2"></i>Capturar Foto';
                
            } catch (error) {
                console.error('Error al validar rostro:', error);
                showNotificationModal('Error de Conexión', 'No se pudo validar el rostro. Verifique su conexión e intente nuevamente.', 'error');
                
                // Permitir retomar foto
                this.disabled = false;
                this.innerHTML = '<i class="bi bi-camera me-2"></i>Capturar Foto';
                
                // Desbloquear botón de volver
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

            // Detener el stream de video
            if (videoStream) {
                videoStream.getTracks().forEach(track => track.stop());
                videoStream = null;
            }
            
            photoConfirmed = true;
            step2Element.classList.add('completed');

            // Deshabilitar botones
            this.disabled = true;
            if (retakePhotoBtn) retakePhotoBtn.disabled = true;
            if (retakePhotoBtn2) retakePhotoBtn2.disabled = true;
            if (capturePhotoBtn) capturePhotoBtn.disabled = true;
            if (startCameraBtn) startCameraBtn.disabled = true;

            // Actualizar UI
            this.innerHTML = '<i class="bi bi-check-circle-fill me-2"></i>Foto Confirmada';
            this.classList.remove('btn-success');
            this.classList.add('btn-secondary');
            
            // Habilitar el botón de envío
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
        
        // Habilitar botón de volver de nuevo al retomar
        if (prevStepBtn) {
            prevStepBtn.disabled = false;
            prevStepBtn.title = '';
        }
        
        // Reiniciar cámara si no está activa
        if (!videoStream || !videoStream.active) {
            if (startCameraBtn) {
                startCameraBtn.disabled = false;
                startCameraBtn.textContent = 'Iniciar Cámara';
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
            if (currentStep === 2 && !photoConfirmed) {
                e.preventDefault();
                showNotificationModal('Rostro no Confirmado', 'Por favor, capture y confirme su rostro antes de crear el usuario.', 'warning');
                return false;
            }
            
            if (!faceDataInput.value) {
                e.preventDefault();
                showNotificationModal('Foto Requerida', 'No se ha capturado ninguna foto. Por favor, capture su rostro para continuar.', 'warning');
                return false;
            }
            
            // Deshabilitar el botón de envío para evitar doble submit
            if (submitFormBtn) {
                submitFormBtn.disabled = true;
                submitFormBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Creando usuario...';
            }
        });
    }

    // --- LIMPIEZA AL SALIR ---
    
    window.addEventListener('beforeunload', function() {
        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
        }
    });

    // --- INICIALIZACIÓN ---
    updateNextButtonState();
    checkRequiredFields();
    
    // Validar campos iniciales si tienen valores
    if (nombreInput && nombreInput.value.trim()) validateNombre();
    if (apellidoInput && apellidoInput.value.trim()) validateApellido();
    if (rolSelect && rolSelect.value) validateRol();
    if (legajoInput && legajoInput.value.trim()) validateField('legajo', legajoInput.value);
    if (emailInput && emailInput.value.trim()) validateField('email', emailInput.value);
    if (passwordInput && passwordInput.value) validatePassword();
    
    console.log('Formulario de usuario inicializado correctamente');
});