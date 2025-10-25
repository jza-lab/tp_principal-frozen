/**
 * @file modalHandler.js
 * @description Script para gestionar la aparición y comportamiento de un modal de confirmación genérico.
 *
 * Funcionalidad:
 * 1.  Escucha clics en elementos con el atributo `data-bs-toggle="modal"` y `data-bs-target` apuntando a `#confirmationModal`.
 * 2.  Al abrir el modal, captura los atributos `data-action` y `data-form-id` del botón que lo activó.
 * 3.  Almacena esta información para que el botón "Confirmar" del modal sepa qué formulario debe enviar.
 * 4.  (MODIFICADO) Al hacer clic en "Confirmar", en lugar de crear un nuevo formulario, busca el formulario original
 *     por su ID y lo envía directamente. Esto permite que otros scripts, como `formCSRFHandler.js`,
 *     intercepten el envío y añadan las cabeceras de seguridad necesarias (CSRF).
 */

document.addEventListener('DOMContentLoaded', function() {
    const confirmationModal = document.getElementById('confirmationModal');
    if (confirmationModal) {
        let formToSubmit = null;

        confirmationModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget; // Botón que activó el modal
            const formId = button.getAttribute('data-form-id');

            if (formId) {
                formToSubmit = document.getElementById(formId);
                if (!formToSubmit) {
                    console.error(`Error: No se encontró el formulario con ID: ${formId}`);
                }
            } else {
                // Fallback para botones que no están asociados a un formulario (ej. un simple enlace)
                // En este caso, el botón de confirmar podría redirigir o realizar otra acción.
                const actionUrl = button.getAttribute('data-action');
                formToSubmit = null; // Limpiamos por si había un formulario anterior
                
                const confirmButton = confirmationModal.querySelector('#modalConfirmButton');
                if(actionUrl) {
                    confirmButton.onclick = () => {
                        window.location.href = actionUrl;
                    };
                }
            }
        });

        const modalConfirmButton = confirmationModal.querySelector('#modalConfirmButton');

        if (modalConfirmButton) {
            modalConfirmButton.addEventListener('click', function() {
                if (formToSubmit) {
                    // Cierra el modal
                    const modalInstance = bootstrap.Modal.getInstance(confirmationModal);
                    modalInstance.hide();
                    
                    // Envía el formulario original. Esto permitirá que formCSRFHandler.js lo intercepte.
                    // Usamos requestSubmit() para disparar los eventos de validación y envío del formulario.
                    if (typeof formToSubmit.requestSubmit === 'function') {
                        formToSubmit.requestSubmit();
                    } else {
                        // Fallback para navegadores más antiguos
                        formToSubmit.submit();
                    }
                } else {
                    console.log("No hay un formulario para enviar. La acción debería haber sido manejada por un 'onclick' si es un enlace.");
                }
            });
        }
    }
});
