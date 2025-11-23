document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('form-vehiculo');
    if (!form) return;

    const fields = {
        patente: document.getElementById('patente'),
        tipo_vehiculo: document.getElementById('tipo_vehiculo'),
        capacidad_kg: document.getElementById('capacidad_kg'),
        nombre_conductor: document.getElementById('nombre_conductor'),
        dni_conductor: document.getElementById('dni_conductor'),
        telefono_conductor: document.getElementById('telefono_conductor')
    };

    // Rangos de capacidad según tipo de vehículo
    const capacityRanges = {
        "Camioneta / Utilitario": { min: 600, max: 1000 },
        "Combi / Furgon": { min: 1500, max: 2500 },
        "Camión (Liviano)": { min: 3500, max: 6000 }
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

    const updateCapacityLimits = () => {
        const tipoSelect = fields.tipo_vehiculo;
        const capacidadInput = fields.capacidad_kg;
        const capacidadHelp = document.getElementById('capacidad-help');

        if (!tipoSelect || !capacidadInput) return;

        const selectedType = tipoSelect.value;
        const range = capacityRanges[selectedType];

        if (range) {
            capacidadInput.min = range.min;
            capacidadInput.max = range.max;
            if (capacidadHelp) {
                capacidadHelp.textContent = `Rango permitido para ${selectedType}: ${range.min} - ${range.max} kg.`;
            }
            // Re-validar si ya tiene valor
            if (capacidadInput.value) {
                validators.capacidad_kg(capacidadInput);
            }
        } else {
            capacidadInput.removeAttribute('min');
            capacidadInput.removeAttribute('max');
            if (capacidadHelp) {
                capacidadHelp.textContent = 'Seleccione un tipo de vehículo para ver el rango permitido.';
            }
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
        tipo_vehiculo: (inputElement) => {
            if (!inputElement.value) {
                showError(inputElement, 'Debe seleccionar un tipo de vehículo.');
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
            
            const tipoSelect = fields.tipo_vehiculo;
            if (!tipoSelect || !tipoSelect.value) {
                 showError(inputElement, 'Seleccione primero el tipo de vehículo.');
                 return false;
            }

            const range = capacityRanges[tipoSelect.value];
            if (!range) {
                // Fallback si algo falla
                return true; 
            }

            const numberValue = parseFloat(value);
            if (isNaN(numberValue)) {
                showError(inputElement, 'Debe ser un número válido.');
                return false;
            }

            if (numberValue < range.min || numberValue > range.max) {
                showError(inputElement, `Debe ser un valor entre ${range.min} y ${range.max} kg.`);
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
        if (inputElement) {
             if (fieldName === 'tipo_vehiculo') {
                inputElement.addEventListener('change', () => {
                    updateCapacityLimits();
                    validator(inputElement);
                });
            } else {
                inputElement.addEventListener('input', () => {
                    validator(inputElement);
                });
            }
        }
    }

    // Inicializar límites si ya hay un valor seleccionado (edición)
    if (fields.tipo_vehiculo && fields.tipo_vehiculo.value) {
        updateCapacityLimits();
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
