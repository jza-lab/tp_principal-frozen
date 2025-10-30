document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('formulario-cliente');
    const contrasenaInput = document.getElementById('contrasena');
    const confirm_contrasenaInput = document.getElementById('confirm_contrasena');

    if (!form) return;
    
    const emailEmpresarialCheckbox = document.getElementById('email_empresarial');
    const razonSocialInput = document.getElementById('razon_social');
    const razonSocialRequiredSpan = document.querySelector('.required-by-email-empresarial');

    function toggleRazonSocialRequirement() {
        const isEmpresarial = emailEmpresarialCheckbox.checked;

        if (isEmpresarial) {
            razonSocialInput.required = true;
            if (razonSocialRequiredSpan) razonSocialRequiredSpan.style.display = 'inline';
        } else {
            razonSocialInput.required = false;
            if (razonSocialRequiredSpan) razonSocialRequiredSpan.style.display = 'none';
        }
    }

    if (emailEmpresarialCheckbox) {
        emailEmpresarialCheckbox.addEventListener('change', toggleRazonSocialRequirement);
    }

    toggleRazonSocialRequirement();

    function restrictToLetters(event) {
        if (event.ctrlKey || event.metaKey ||
            [8, 9, 13, 27, 46].includes(event.keyCode) ||
            (event.keyCode >= 35 && event.keyCode <= 40)
        ) {
            return;
        }

        const isLetterOrSpace = /[A-Za-zñÑáéíóúÁÉÍÓÚ\s]/.test(event.key);

        if (!isLetterOrSpace) {
            event.preventDefault();
        }
    }

    function restrictToNumbers(event) {
        if (event.ctrlKey || event.metaKey ||
            [8, 9, 13, 27, 46].includes(event.keyCode) ||
            (event.keyCode >= 35 && event.keyCode <= 40)
        ) {
            return;
        }
        const isDigit = /[0-9]/.test(event.key);

        if (!isDigit) {
            event.preventDefault();
        }
    }

    function validarCuil(cuil) {
        if (!cuil || cuil.length !== 11) {
            return false;
        }

        const cuilLimpio = cuil.replace(/[^0-9]/g, '');
        if (cuilLimpio.length !== 11) {
            return false;
        }

        const base = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];
        const digitoVerificador = parseInt(cuilLimpio.charAt(10), 10);
        let suma = 0;

        for (let i = 0; i < 10; i++) {
            suma += parseInt(cuilLimpio.charAt(i), 10) * base[i];
        }

        let resultado = 11 - (suma % 11);
        if (resultado === 11) {
            resultado = 0;
        } else if (resultado === 10) {
            // Caso especial para CUIT 20, 23, 24, 27, 30, etc. (se usa 9 en su lugar o se valida directamente)
            // En Argentina, los digitos verificadores 10 se convierten a 9.
            return digitoVerificador === 9;
        }

        return resultado === digitoVerificador;
    }

    const alturaInput = document.getElementById('altura');

    if (alturaInput) {
        alturaInput.addEventListener('input', function () {
            if (this.value.length > 5) {
                this.value = this.value.slice(0, 5);
            }
        });
    }

    const cuitPartes = ['cuit_parte1', 'cuit_parte2', 'cuit_parte3'];
    const cuitFeedback = document.getElementById('cuit-feedback');

    cuitPartes.forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('keypress', restrictToNumbers);
            input.addEventListener('input', () => {
                const parte1 = document.getElementById('cuit_parte1').value;
                const parte2 = document.getElementById('cuit_parte2').value;
                const parte3 = document.getElementById('cuit_parte3').value;
                const cuilCompleto = parte1 + parte2 + parte3;

                // Solo validar cuando las 11 partes estén ingresadas
                if (cuilCompleto.length === 11) {
                    if (validarCuil(cuilCompleto)) {
                        cuitFeedback.textContent = 'CUIT/CUIL Válido.';
                        cuitFeedback.className = 'form-text text-success';
                    } else {
                        cuitFeedback.textContent = 'CUIT/CUIL Inválido. Revise el número.';
                        cuitFeedback.className = 'form-text text-danger';
                    }
                } else if (cuilCompleto.length > 0) {
                    const faltantes = 11 - cuilCompleto.length
                    cuitFeedback.textContent = `Falta${faltantes > 1 ? 'n' : ''} ${faltantes} dígito${faltantes > 1 ? 's' : ''} (11 en total).`;
                    cuitFeedback.className = 'form-text text-warning';
                } else {
                    cuitFeedback.textContent = '';
                }
            });
        }
    });

    const telefonoInput = document.getElementById('telefono');
    if (telefonoInput) {
        telefonoInput.addEventListener('keypress', restrictToNumbers);
    }

    const nombreInput = document.getElementById('nombre');
    if (nombreInput) {
        nombreInput.addEventListener('keypress', restrictToLetters);
    }

    function getCsrfToken() {
        const tokenElement = form.querySelector('input[name="csrf_token"]');
        return tokenElement ? tokenElement.value : null;
    }
    const csrfToken = getCsrfToken();
    if (!csrfToken) {
        console.error("CSRF Token no encontrado en el formulario.");
        showNotificationModal('Error de Seguridad', 'Fallo al obtener el token de seguridad CSRF.');
        return;
    }

    const addressInputs = ['calle', 'altura', 'localidad', 'provincia', 'codigo_postal', 'piso', 'depto'];
    function setAddressValidationState(isValid) {
        addressInputs.forEach(id => {
            const input = document.getElementById(id);
            if (input) {
                input.classList.remove(isValid ? 'is-invalid' : 'is-valid');
                input.classList.add(isValid ? 'is-valid' : 'is-invalid');
            }
        });
    }

    function validateNonAddressFields() {
        let allValid = true;
        form.querySelectorAll('input, select, textarea').forEach(input => {
            if (addressInputs.includes(input.id)) {
                input.classList.remove('is-valid', 'is-invalid');
                return;
            }
            if (!input.checkValidity()) {
                input.classList.add('is-invalid');
                input.classList.remove('is-valid');
                allValid = false;
            } else {
                input.classList.add('is-valid');
                input.classList.remove('is-invalid');
            }
        });
        if (!allValid) {
            showNotificationModal('Formulario Incompleto', 'Por favor, complete correctamente todos los campos requeridos (excepto dirección).');
        }
        return allValid;
    }


    async function verifyAddress() {
        if (!validateNonAddressFields()) {
            return;
        }
        const calleInput = document.getElementById('calle');
        const alturaInput = document.getElementById('altura');
        const provinciaSelect = document.getElementById('provincia');
        const localidadInput = document.getElementById('localidad');

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

            const verificationResult = await response.json();

            if (response.ok && verificationResult.success) {
                setAddressValidationState(true);
                await enviarDatos();
            } else {
                let errorMessage = 'Dirección no válida o error de verificación.';
                if (verificationResult && verificationResult.error) {
                    errorMessage = verificationResult.error;
                }
                showNotificationModal(errorMessage, 'No se pudo validar la dirección.');
                setAddressValidationState(false);
            }
        } catch (error) {
            console.error('Error de red al verificar la direccion:', error);
            showNotificationModal('No se pudo conectar con el servidor de verificación.', 'error');
        }
    }

    async function enviarDatos() {
        if (!form.checkValidity()) {
            form.classList.add('was-validated');
            showNotificationModal('Formulario Incompleto', 'Por favor, complete todos los campos requeridos.');
            return;
        }

        const contrasena = document.getElementById('contrasena').value;
        const confirm_contrasena = document.getElementById('confirm_contrasena').value;

        if (contrasena.length < 8) {
            showNotificationModal('Error de Contraseña', 'La contraseña debe tener al menos 8 caracteres.');
            contrasenaInput.classList.add('is-invalid');
            confirm_contrasenaInput.classList.add('is-invalid');
            contrasenaInput.focus()
            return;
        }

        if (contrasena !== confirm_contrasena) {
            showNotificationModal('Error de Contraseña', 'Las contraseñas no coinciden.');
            contrasenaInput.classList.add('is-invalid');
            confirm_contrasenaInput.classList.add('is-invalid');
            contrasenaInput.focus()
            return;
        }

        const formData = new FormData(form);
        const cuit = `${formData.get('cuit_parte1')}-${formData.get('cuit_parte2')}-${formData.get('cuit_parte3')}`;

        const clienteData = {
            nombre: formData.get('nombre'),
            cuit: cuit,
            email: formData.get('email'),
            email_empresarial: document.getElementById('email_empresarial').checked,
            telefono: formData.get('telefono'),
            condicion_iva: formData.get('condicion_iva'),
            razon_social: formData.get('razon_social') || '',
            contrasena: contrasena,
            direccion: {
                calle: formData.get('calle'),
                altura: formData.get('altura'),
                localidad: formData.get('localidad'),
                provincia: formData.get('provincia'),
                codigo_postal: formData.get('codigo_postal'),
                piso: formData.get('piso') || null,
                depto: formData.get('depto') || null
            }
        };

        const url = '/cliente/register';
        const method = 'POST';

        try {
            const respuesta = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(clienteData)
            });

            const resultado = await respuesta.json();

            if (respuesta.ok && resultado.success) {
                showNotificationModal('¡Registro Exitoso!', 'Su cuenta ha sido creada. Será redirigido para iniciar sesión.');
                setTimeout(() => {
                    window.location.href = '/cliente/login';
                }, 2500);
            } else {
                let errorMessage = 'Ocurrió un error en el registro.';
                if (resultado && resultado.error) {
                    errorMessage = typeof resultado.error === 'object' ? Object.values(resultado.error).flat().join('<br>') : resultado.error;
                }
                showNotificationModal('Error de Registro', errorMessage);
            }
        } catch (error) {
            console.error('Error:', error);
            showNotificationModal('Error de Conexión', 'No se pudo conectar con el servidor. Inténtelo más tarde.');
        }
    }

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        event.stopPropagation();
        if (emailEmpresarialCheckbox.checked && !razonSocialInput.value.trim()) {
            razonSocialInput.setCustomValidity('La Razón Social es obligatoria para emails empresariales.');
            razonSocialInput.classList.add('is-invalid');
            showNotificationModal('Error de Formulario', 'Debe ingresar la Razón Social de su empresa (mail empresarial).', 'Por favor, ingrese la Razón Social de la empresa asociada.');
            return
        } else {
            razonSocialInput.setCustomValidity('');
            razonSocialInput.classList.remove('is-invalid');
        }
        
        verifyAddress();
    });
});
