document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('ordenProduccionForm');
    if (!form) {
        console.error('El formulario #ordenProduccionForm no se encontró en el DOM.');
        return;
    }

    const addItemBtn = document.getElementById('addIngredienteBtn');
    const ingredientesContainer = document.getElementById('ingredientes-container');
    const ingredienteTemplate = document.getElementById('ingrediente-template');
    
    let ingredienteIndex = ingredientesContainer.querySelectorAll('.ingrediente-row').length;

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
    ingredientesContainer.addEventListener('click', function(e) {
        if (e.target.closest('.remove-ingrediente-btn')) {
            e.preventDefault();
            e.target.closest('.ingrediente-row').remove();
            updateIngredienteIndices();
            updateUI();
        }
    });

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
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRF-TOKEN': form.querySelector('[name=csrf_token]').value
                }
            });

            const result = await response.json();

            if (result.success) {
                Swal.fire({
                    icon: 'success',
                    title: '¡Éxito!',
                    text: result.message || 'La operación se completó correctamente.',
                    timer: 2000,
                    showConfirmButton: false
                }).then(() => {
                    if (result.redirect_url) {
                        window.location.href = result.redirect_url;
                    } else {
                        // Si no hay redirección, podría ser útil recargar o resetear el form
                        location.reload(); 
                    }
                });
            } else {
                throw new Error(result.error || 'Ocurrió un error desconocido.');
            }

        } catch (error) {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: error.message
            });
        } finally {
            // Restaurar botón
            submitButton.disabled = false;
            submitButton.innerHTML = originalButtonText;
        }
    });
    
    // --- 4. Funciones auxiliares ---
    function updateUI() {
        const noItemsMsg = document.getElementById('no-ingredientes-msg');
        if (noItemsMsg) {
            noItemsMsg.style.display = ingredientesContainer.children.length > 0 ? 'none' : 'block';
        }
    }

    function updateIngredienteIndices() {
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
