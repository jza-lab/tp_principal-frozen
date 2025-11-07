document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('ordenProduccionForm');
    if (!form) {
        console.error('El formulario #ordenProduccionForm no se encontró en el DOM.');
        return;
    }

    const addItemBtn = document.getElementById('addIngredienteBtn');
    const ingredientesContainer = document.getElementById('ingredientes-container');
    const ingredienteTemplate = document.getElementById('ingrediente-template');
    
    let ingredienteIndex = 0;
    if (ingredientesContainer) {
        ingredienteIndex = ingredientesContainer.querySelectorAll('.ingrediente-row').length;
    }
    

    // --- 1. Añadir Ingrediente ---
    if (addItemBtn) {
        addItemBtn.addEventListener('click', function() {
            if (!ingredienteTemplate) {
                console.error('El template #ingrediente-template no existe.');
                return;
            }

            const templateContent = ingredienteTemplate.content.cloneNode(true);
            const newRow = templateContent.querySelector('.ingrediente-row');
            
            // Actualizar el prefijo del nombre para los campos del nuevo ítem
            newRow.querySelectorAll('[name]').forEach(el => {
                el.name = el.name.replace('__prefix__', ingredienteIndex);
            });

            ingredientesContainer.appendChild(newRow);
            ingredienteIndex++;
            updateUI();
        });
    }

    // --- 2. Eliminar Ingrediente ---
    if (ingredientesContainer) {
        ingredientesContainer.addEventListener('click', function(e) {
            if (e.target.closest('.remove-ingrediente-btn')) {
                e.preventDefault();
                e.target.closest('.ingrediente-row').remove();
                updateIngredienteIndices();
                updateUI();
            }
        });
    }

    // --- 3. Envío del Formulario con Fetch ---
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const submitButton = form.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.innerHTML;
        
        // Deshabilitar botón y mostrar spinner
        submitButton.disabled = true;
        submitButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Guardando...`;

        try {
            // Usar la variable global definida en el template
            const response = await fetch(CREAR_URL, {
                method: 'POST',
                body: new URLSearchParams(formData).toString(), // Enviar como x-www-form-urlencoded
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRF-TOKEN': formData.get('csrf_token')
                }
            });

            const result = await response.json();

            if (response.ok && result.success) {
                // Usar la variable global LISTA_URL para la redirección
                showNotificationModal('¡Éxito!', 'Orden de producción creada correctamente.', 'success', () => {
                    window.location.href = LISTA_URL;
                });
            } else {
                throw new Error(result.error || 'Ocurrió un error desconocido.');
            }

        } catch (error) {
            let errorMessage = 'No se pudo conectar con el servidor. Intente de nuevo más tarde.';
            if (error instanceof Error) {
                errorMessage = error.message;
            }
            showNotificationModal('Error', errorMessage, 'error');

        } finally {
            // Restaurar botón solo en caso de error. En caso de éxito, se redirige.
             if (!response.ok) {
                submitButton.disabled = false;
                submitButton.innerHTML = originalButtonText;
             }
        }
    });
    
    // --- 4. Funciones auxiliares ---
    function updateUI() {
        if (!ingredientesContainer) return;
        const noItemsMsg = document.getElementById('no-ingredientes-msg');
        if (noItemsMsg) {
            noItemsMsg.style.display = ingredientesContainer.children.length > 0 ? 'none' : 'block';
        }
    }

    function updateIngredienteIndices() {
        if (!ingredientesContainer) return;
        let index = 0;
        ingredientesContainer.querySelectorAll('.ingrediente-row').forEach(row => {
            row.querySelectorAll('[name]').forEach(el => {
                const name = el.getAttribute('name');
                if (name) {
                    el.setAttribute('name', name.replace(/items\[\d+\]/, `items[${index}]`));
                }
            });
            index++;
        });
        ingredienteIndex = index;
    }

    // --- Inicialización ---
    updateUI();
});