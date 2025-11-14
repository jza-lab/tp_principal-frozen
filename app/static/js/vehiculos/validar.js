document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('form-vehiculo');
    if (!form) return;

    const fields = {
        patente: document.getElementById('patente'),
        capacidad_kg: document.getElementById('capacidad_kg'),
        nombre_conductor: document.getElementById('nombre_conductor'),
        dni_conductor: document.getElementById('dni_conductor'),
        telefono_conductor: document.getElementById('telefono_conductor')
    };

    // --- Funciones de Feedback (UI) ---
    const showError = (element, message) => {
        if (!element) return;
        element.classList.remove('is-valid');
        element.classList.add('is-invalid');
        const errorDiv = document.getElementById(element.id + '-error');
        if (errorDiv) {
            errorDiv.textContent = message;
        }
    };

    const showSuccess = (element) => {
        if (!element) return;
        element.classList.remove('is-invalid');
        element.classList.add('is-valid');
        const errorDiv = document.getElementById(element.id + '-error');
        if (errorDiv) {
            errorDiv.textContent = '';
        }
    };
    
    // --- Lógica de Validación Específica ---
    const validators = {
        patente: (inputElement) => {
            const value = inputElement.value.trim().toUpperCase().replace(/\s/g, '');
            if (!value) {
                showError(inputElement, 'La patente es obligatoria.');
                return false;
            }
            if (!/^(?:[A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2})$/.test(value)) {
                showError(inputElement, 'Formato inválido.');
                return false;
            }
            showSuccess(inputElement);
            return true;
        },
        capacidad_kg: (inputElement) => {
            const value = inputElement.value;
            if (value === '' || value === null) {
                showError(inputElement, 'La capacidad es requerida.');
                return false;
            }
            const numberValue = parseFloat(value);
            if (isNaN(numberValue) || numberValue < 250 || numberValue > 1500) {
                showError(inputElement, 'Debe ser un valor entre 250 y 1500.');
                return false;
            }
            showSuccess(inputElement);
            return true;
        },
        nombre_conductor: (inputElement) => {
            const value = inputElement.value.trim();
            if (!value) {
                showError(inputElement, 'El nombre es obligatorio.');
                return false;
            }
            if (/\d/.test(value)) {
                showError(inputElement, 'No puede contener números.');
                return false;
            }
            if (value.length < 3) {
                showError(inputElement, 'Debe tener al menos 3 caracteres.');
                return false;
            }
            showSuccess(inputElement);
            return true;
        },
        dni_conductor: (inputElement) => {
            const value = inputElement.value.trim();
            if (!value) {
                showError(inputElement, 'El DNI es obligatorio.');
                return false;
            }
            if (!/^\d{7,8}$/.test(value)) {
                showError(inputElement, 'Debe ser un número de 7 u 8 dígitos.');
                return false;
            }
            showSuccess(inputElement);
            return true;
        },
        telefono_conductor: (inputElement) => {
            const value = inputElement.value.trim();
            if (value && !/^\d{7,}$/.test(value)) {
                showError(inputElement, 'Debe ser un número de al menos 7 dígitos.');
                return false;
            }
            showSuccess(inputElement);
            return true;
        }
    };

    // Asignar eventos de validación en tiempo real (input)
    for (const fieldName in fields) {
        const inputElement = fields[fieldName];
        const validator = validators[fieldName];
        if (inputElement && validator) {
            inputElement.addEventListener('input', () => {
                validator(inputElement);
            });
        }
    }

    // Validación final al intentar enviar el formulario
    form.addEventListener('submit', function (event) {
        let isFormValid = true;
        for (const fieldName in fields) {
            const inputElement = fields[fieldName];
            const validator = validators[fieldName];
            if (inputElement && validator) {
                if (!validator(inputElement)) {
                    isFormValid = false;
                }
            }
        }

        if (!isFormValid) {
            event.preventDefault();
        }
    });
});
