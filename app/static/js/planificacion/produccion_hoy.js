document.addEventListener('DOMContentLoaded', function () {
    const modalIniciarOpElement = document.getElementById('modalIniciarOp');
    if (!modalIniciarOpElement) {
        console.error("El modal 'modalIniciarOp' no se encontró en el DOM.");
        return;
    }
    const modalIniciarOp = new bootstrap.Modal(modalIniciarOpElement);

    const formIniciarOp = document.getElementById('formIniciarOp');
    const modalOpIdInput = document.getElementById('modal-op-id');
    const modalOpCodigoSpan = document.getElementById('modal-op-codigo');
    const modalLineaSelect = document.getElementById('modal-linea-produccion');
    const modalLineaSugeridaText = document.getElementById('modal-linea-sugerida-text');

    // Listener para todos los botones "Iniciar Trabajo"
    document.querySelectorAll('.btn-iniciar-op').forEach(button => {
        button.addEventListener('click', function () {
            const opId = this.dataset.opId;
            const opSugerenciaLinea = this.dataset.opSugerenciaLinea;
            const opCard = this.closest('.kanban-card');
            const opCodigo = opCard.querySelector('code').textContent;

            // Poblar el modal
            modalOpIdInput.value = opId;
            modalOpCodigoSpan.textContent = opCodigo;

            if (opSugerenciaLinea) {
                modalLineaSelect.value = opSugerenciaLinea;
                modalLineaSugeridaText.textContent = `Línea sugerida por planificación: ${opSugerenciaLinea}`;
                modalLineaSugeridaText.style.display = 'block';
            } else {
                modalLineaSelect.value = '1'; // Default a línea 1 si no hay sugerencia
                modalLineaSugeridaText.textContent = '';
                modalLineaSugeridaText.style.display = 'none';
            }

            // Limpiar checkboxes
            formIniciarOp.querySelectorAll('input[type="checkbox"]').forEach(chk => chk.checked = false);

            modalIniciarOp.show();
        });
    });

    // Listener para el envío del formulario del modal
    formIniciarOp.addEventListener('submit', async function (event) {
        event.preventDefault();

        const opId = modalOpIdInput.value;
        const lineaSeleccionada = modalLineaSelect.value;

        const submitButton = formIniciarOp.querySelector('button[type="submit"]');
        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Iniciando...';

        try {
            const response = await fetch(`/tabla-produccion/api/${opId}/iniciar-trabajo`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ linea: parseInt(lineaSeleccionada) })
            });

            const result = await response.json();

            if (response.ok && result.success) {
                modalIniciarOp.hide();
                // Mostrar un feedback visual de éxito antes de recargar
                showNotificationModal('Éxito', `La orden ${modalOpCodigoSpan.textContent} se ha iniciado en la Línea ${lineaSeleccionada}.`, 'success');
                setTimeout(() => window.location.reload(), 2000); // Recargar la página para ver el cambio
            } else {
                // Mostrar error
                showNotificationModal('Error', result.error || 'No se pudo iniciar la orden.', 'error');
            }

        } catch (error) {
            console.error('Error de red al iniciar la orden:', error);
            showNotificationModal('Error de Red', 'No se pudo comunicar con el servidor. Inténtelo de nuevo.', 'error');
        } finally {
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="bi bi-play-fill me-1"></i>Iniciar Trabajo';
        }
    });

    // Función helper para mostrar notificaciones (asume que tienes un modal con id 'notificationModal')
    function showNotificationModal(title, message, type = 'info') {
        const modal = new bootstrap.Modal(document.getElementById('notificationModal'));
        const modalTitle = document.getElementById('notificationModalTitle');
        const modalBody = document.getElementById('notificationModalBody');
        
        modalTitle.textContent = title;
        modalBody.textContent = message;
        
        // Opcional: cambiar color del header según el tipo
        // ...

        modal.show();
    }
});