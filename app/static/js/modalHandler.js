/**
 * Muestra un modal de confirmación genérico con dos botones (Confirmar/Cancelar).
 * @param {string} title - El título del modal.
 * @param {string} body - El mensaje en el cuerpo del modal.
 * @param {function} confirmCallback - La función que se ejecutará si el usuario hace clic en "Confirmar".
 * @param {string} [buttonType='primary'] - El estilo del botón de confirmación ('primary', 'success', 'danger').
 */
function showConfirmationModal(title, body, confirmCallback, buttonType = 'primary') {
    const modalElement = document.getElementById('confirmationModal');
    if (!modalElement) {
        console.error('Modal element #confirmationModal not found in the DOM.');
        return;
    }

    const modalTitle = modalElement.querySelector('#modalTitle');
    const modalBody = modalElement.querySelector('#modalBody');
    const modalConfirmButton = modalElement.querySelector('#modalConfirmButton');
    const modalCancelButton = modalElement.querySelector('#modalCancelButton');

    // Asignar contenido y configurar botones
    modalTitle.textContent = title;
    modalBody.textContent = body;
    modalConfirmButton.textContent = 'Confirmar';
    modalConfirmButton.className = `btn btn-${buttonType}`; // Asignar clase de estilo
    modalCancelButton.style.display = ''; // Asegurarse de que el botón Cancelar esté visible

    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);

    // Clonar y reemplazar el botón para limpiar listeners de eventos anteriores
    const newConfirmButton = modalConfirmButton.cloneNode(true);
    modalConfirmButton.parentNode.replaceChild(newConfirmButton, modalConfirmButton);
    
    // Asignar el nuevo callback
    newConfirmButton.addEventListener('click', () => {
        confirmCallback();
        modal.hide();
    });

    modal.show();
}


document.addEventListener('DOMContentLoaded', function () {
    // Función para obtener el valor de una cookie por su nombre
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Modal de confirmación para formularios (class="needs-confirmation")
    document.body.addEventListener('submit', function(event) {
        const form = event.target;
        if (form.classList.contains('needs-confirmation')) {
            event.preventDefault(); // Detener el envío del formulario
            
            const message = form.dataset.confirmMessage || '¿Está seguro de que desea realizar esta acción?';
            const title = form.dataset.confirmTitle || 'Confirmar Acción';
            
            showConfirmationModal(title, message, function() {
                // Si el usuario confirma, se envía el formulario
                form.submit();
            });
        }
    });

    // Modal de confirmación genérico (class="confirm-form")
    const confirmationModal = document.getElementById('confirmationModal');
    if (confirmationModal) {
        let confirmAction = null;

        confirmationModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            if (!button || !button.closest('.confirm-form')) {
                // Si el modal no fue disparado por un botón dentro de un .confirm-form, no hacer nada.
                // Limpiamos cualquier acción anterior para evitar ejecuciones accidentales.
                confirmAction = null;
                return;
            }
            
            const form = button.closest('.confirm-form');
            const url = form.action;
            const message = form.dataset.message || '¿Estás seguro?';
            const title = form.dataset.title || 'Confirmación';
            const buttonType = form.dataset.buttonType || 'primary';

            const modalTitle = confirmationModal.querySelector('#modalTitle');
            const modalBody = confirmationModal.querySelector('#modalBody');
            const modalConfirmButton = confirmationModal.querySelector('#modalConfirmButton');

            modalTitle.textContent = title;
            modalBody.innerHTML = message;
            modalConfirmButton.className = `btn btn-${buttonType}`;

            // Guardamos la acción a ejecutar cuando se confirme
            confirmAction = function() {
                const csrfToken = getCookie('csrf_access_token');
                
                fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRF-TOKEN': csrfToken,
                        'Content-Type': 'application/json' 
                    },
                }).then(response => {
                    if (response.redirected) {
                        window.location.href = response.url;
                    } else {
                        // Si no hay redirección, recargamos la página para ver los cambios (ej. flash messages)
                        window.location.reload();
                    }
                }).catch(error => {
                    console.error('Error al realizar la acción:', error);
                    showNotificationModal('Error', 'Ocurrió un error al procesar la solicitud.', 'error');
                });
            };
        });

        // Event listener para el botón de confirmación
        const confirmButton = confirmationModal.querySelector('#modalConfirmButton');
        confirmButton.addEventListener('click', function() {
            if (typeof confirmAction === 'function') {
                confirmAction();
                const modal = bootstrap.Modal.getInstance(confirmationModal);
                modal.hide();
                confirmAction = null; // Limpiar la acción después de usarla
            }
        });

        // Limpiar la acción si el modal se cierra sin confirmar
        confirmationModal.addEventListener('hide.bs.modal', function() {
            confirmAction = null;
        });
    }
});


/**
 * Muestra un modal de notificación con un solo botón (OK).
 * @param {string} title - El título del modal.
 * @param {string} body - El mensaje en el cuerpo del modal.
 * @param {string} [type='info'] - El tipo de notificación ('success', 'error', 'info') para colorear el botón.
 * @param {function} [closeCallback] - (Opcional) La función que se ejecutará después de que el modal se cierre.
 */
function showNotificationModal(title, body, type = 'info', closeCallback) {
    const modalElement = document.getElementById('notificationModal');
    if (!modalElement) {
        console.error('Modal element #notificationModal not found in the DOM.');
        return;
    }

    const modalTitle = modalElement.querySelector('#notificationModalTitle');
    const modalBody = modalElement.querySelector('#notificationModalBody');
    const modalOkButton = modalElement.querySelector('#notificationModalOkButton');

    // Asignar contenido y configurar botones
    modalTitle.textContent = title;
    modalBody.innerHTML = body; // Usar innerHTML para permitir contenido HTML

    // Cambiar color del botón según el tipo de notificación
    let buttonClass = 'btn btn-primary';
    if (type === 'success') {
        buttonClass = 'btn btn-success';
    } else if (type === 'error') {
        buttonClass = 'btn btn-danger';
    }
    modalOkButton.className = buttonClass;

    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);

    // Si hay un callback, lo ejecutamos DESPUÉS de que el modal se oculte.
    // Usamos { once: true } para que el listener se elimine automáticamente después de ejecutarse una vez.
    if (closeCallback && typeof closeCallback === 'function') {
        modalElement.addEventListener('hidden.bs.modal', closeCallback, { once: true });
    }

    modal.show();
}