/**
 * Módulo formValidator.js
 * 
 * Proporciona funciones reutilizables para la validación de formularios en las páginas de creación y edición de usuarios.
 * Incluye validaciones de formato (cliente) y validaciones de unicidad (servidor).
 * También exporta funciones de utilidad para mostrar mensajes de éxito y error.
 */

/**
 * Muestra un mensaje de error para un campo de entrada.
 * @param {HTMLElement} element - El elemento de entrada (o un contenedor como .input-group).
 * @param {string} message - El mensaje de error a mostrar.
 */
export function showError(element, message) {
    if (!element) return;
    const formField = element.closest('.info-item, .col-md-6, .col-12');
    if (!formField) return;

    // Ocultar mensaje de éxito si existe
    const successDiv = formField.querySelector('.valid-feedback');
    if (successDiv) successDiv.style.display = 'none';

    let errorDiv = formField.querySelector('.invalid-feedback');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'invalid-feedback';
        element.parentNode.appendChild(errorDiv);
    }

    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    element.classList.remove('is-valid');
    element.classList.add('is-invalid');
}

/**
 * Muestra un mensaje de éxito para un campo de entrada.
 * @param {HTMLElement} element - El elemento de entrada.
 * @param {string} [message='Válido.'] - El mensaje de éxito.
 */
export function showSuccess(element, message = 'Válido.') {
    if (!element) return;
    const formField = element.closest('.info-item, .col-md-6, .col-12');
    if (!formField) return;

    // Ocultar mensaje de error
    const errorDiv = formField.querySelector('.invalid-feedback');
    if (errorDiv) errorDiv.style.display = 'none';

    let successDiv = formField.querySelector('.valid-feedback');
    if (!successDiv) {
        successDiv = document.createElement('div');
        successDiv.className = 'valid-feedback';
        element.parentNode.appendChild(successDiv);
    }
    successDiv.textContent = message;
    successDiv.style.display = 'block';

    element.classList.remove('is-invalid');
    element.classList.add('is-valid');
}

/**
 * Limpia cualquier mensaje de validación (error o éxito) de un campo.
 * @param {HTMLElement} element - El elemento de entrada.
 */
export function clearValidation(element) {
    if (!element) return;
    const formField = element.closest('.info-item, .col-md-6, .col-12');
    if (!formField) return;

    const errorDiv = formField.querySelector('.invalid-feedback');
    if (errorDiv) errorDiv.style.display = 'none';

    const successDiv = formField.querySelector('.valid-feedback');
    if (successDiv) successDiv.style.display = 'none';

    element.classList.remove('is-invalid', 'is-valid');
}


// --- Lógica de Validación Específica ---

/**
 * Valida un campo de forma asíncrona contra el servidor (para unicidad).
 * @param {string} field - El nombre del campo (ej. 'legajo', 'email').
 * @param {string} value - El valor a validar.
 * @param {HTMLElement} element - El elemento del DOM para mostrar feedback.
 * @param {number|null} userId - El ID del usuario a excluir de la validación (para modo edición).
 * @returns {Promise<boolean>} - True si es válido, False si no.
 */
export async function validateUniqueField(field, value, element, userId = null) {
    // Primero, validaciones de formato síncronas
    if (!value || !value.trim()) {
        showError(element, 'Este campo es obligatorio.');
        return false;
    }
     if (field === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        showError(element, 'Formato de email inválido.');
        return false;
    }
    if (field === 'telefono' && !/^\d{7,15}$/.test(value)) {
        showError(element, 'Debe contener entre 7 y 15 dígitos numéricos.');
        return false;
    }
     if (field === 'cuil_cuit' && !/^\d{2}-\d{8}-\d{1}$/.test(value)) {
        showError(element, 'Formato de CUIL/CUIT inválido.');
        return false;
    }

    // Validación asíncrona
    try {
        const payload = { field, value };
        if (userId) {
            payload.user_id = userId;
        }

        const response = await fetch('/api/validar/campo_usuario', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Error de servidor');

        const result = await response.json();
        if (!result.valid) {
            showError(element, result.message || 'Este valor ya está en uso.');
            return false;
        } else {
            showSuccess(element, 'Disponible.');
            return true;
        }
    } catch (error) {
        console.error(`Error validando ${field}:`, error);
        showError(element, 'Error de red al validar.');
        return false;
    }
}

/**
 * Valida el campo 'nombre'.
 * @param {HTMLInputElement} inputElement - El input del nombre.
 * @returns {boolean} - True si es válido, False si no.
 */
export function validateNombre(inputElement) {
    const value = inputElement.value.trim();
    if (!value) {
        showError(inputElement, 'El nombre es obligatorio.');
        return false;
    }
    if (/\d/.test(value)) {
        showError(inputElement, 'No puede contener números.');
        return false;
    }
    if (value.length < 2) {
        showError(inputElement, 'Debe tener al menos 2 caracteres.');
        return false;
    }
    showSuccess(inputElement);
    return true;
}

/**
 * Valida el campo 'apellido'.
 * @param {HTMLInputElement} inputElement - El input del apellido.
 * @returns {boolean} - True si es válido, False si no.
 */
export function validateApellido(inputElement) {
    const value = inputElement.value.trim();
    if (!value) {
        showError(inputElement, 'El apellido es obligatorio.');
        return false;
    }
    if (/\d/.test(value)) {
        showError(inputElement, 'No puede contener números.');
        return false;
    }
    if (value.length < 2) {
        showError(inputElement, 'Debe tener al menos 2 caracteres.');
        return false;
    }
    showSuccess(inputElement);
    return true;
}

/**
 * Valida el campo 'password' (solo en creación).
 * @param {HTMLInputElement} inputElement - El input de la contraseña.
 * @returns {boolean} - True si es válido, False si no.
 */
export function validatePassword(inputElement) {
    const value = inputElement.value;
    if (!value) {
        showError(inputElement, 'La contraseña es obligatoria.');
        return false;
    }
    if (value.length < 8) {
        showError(inputElement, 'Debe tener al menos 8 caracteres.');
        return false;
    }
    showSuccess(inputElement);
    return true;
}

/**
 * Valida campos de dirección requeridos.
 * @param {HTMLInputElement|HTMLSelectElement} inputElement - El input de la dirección.
 * @returns {boolean} - True si es válido, False si no.
 */
export function validateAddressField(inputElement) {
    const value = inputElement.value.trim();
    if (!value) {
        showError(inputElement, 'Este campo es obligatorio.');
        return false;
    }
    showSuccess(inputElement);
    return true;
}
/**
 * Realiza una validación completa de todos los campos visibles en el formulario.
 * @returns {boolean} - True si todo el formulario es válido.
 */
export function validateForm() {
    let isValid = true;
    const fieldsToValidate = [
        { element: document.getElementById('nombre'), validator: validateNombre },
        { element: document.getElementById('apellido'), validator: validateApellido },
        // Añadir más validaciones síncronas aquí si es necesario
    ];

    fieldsToValidate.forEach(({ element, validator }) => {
        if (element && !validator(element)) {
            isValid = false;
        }
    });

    // Comprobar si algún campo ya tiene la clase 'is-invalid'
    if (document.querySelector('.form-control.is-invalid, .cuit-input-group.is-invalid')) {
        isValid = false;
    }

    return isValid;
}