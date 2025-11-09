document.addEventListener('DOMContentLoaded', function () {
    const panel = document.getElementById('panel-control-calidad');
    if (!panel) return;

    const modalElement = document.getElementById('modal-inspeccion-accion');
    const modal = new bootstrap.Modal(modalElement);
    const form = document.getElementById('form-inspeccion-accion');
    const btnFinalizar = document.getElementById('btn-finalizar-inspeccion');
    const ordenId = panel.dataset.ordenId;

    const estadoLoteConfig = {
        'disponible': { 'class': 'bg-success-soft text-success', 'icon': 'check-circle-fill', 'text': 'Aceptado' },
        'cuarentena': { 'class': 'bg-warning-soft text-warning', 'icon': 'exclamation-triangle-fill', 'text': 'En Cuarentena' },
        'RECHAZADO': { 'class': 'bg-danger-soft text-danger', 'icon': 'x-circle-fill', 'text': 'Rechazado' }
    };

    document.querySelectorAll('.btn-inspeccion').forEach(button => {
        button.addEventListener('click', function (event) {
            const action = this.dataset.action;
            const loteId = this.dataset.loteId;

            if (action === 'aceptar') {
                realizarAccion(loteId, action, null, this);
            } else {
                const loteNombre = this.dataset.loteNombre;
                const loteCard = document.querySelector(`.lote-card[data-lote-id='${loteId}']`);
                const cantidadInicial = loteCard.querySelector('small').textContent.split('| Cantidad: ')[1].split(' ')[0];
                configurarModal(loteId, action, loteNombre, cantidadInicial);
            }
        });
    });

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        const loteId = document.getElementById('modal-lote-id').value;
        const action = document.getElementById('modal-action').value;
        const submitButton = document.getElementById('modal-btn-confirmar');
        realizarAccion(loteId, action, new FormData(form), submitButton);
        modal.hide();
    });

    btnFinalizar.addEventListener('click', function () {
        finalizarInspeccion(this);
    });

    function configurarModal(loteId, action, loteNombre, cantidadDisponible) {
        const modalTitle = document.getElementById('modalInspeccionLabel');
        const modalBtnConfirmar = document.getElementById('modal-btn-confirmar');
        const modalCantidadInput = document.getElementById('modal-cantidad');
        const modalCantidadDisponible = document.getElementById('modal-cantidad-disponible');
        const selectResultado = document.getElementById('modal-resultado-inspeccion');
        const textareaComentarios = document.getElementById('modal-comentarios');
        
        document.getElementById('modal-lote-id').value = loteId;
        document.getElementById('modal-action').value = action;
        document.getElementById('modal-lote-nombre').textContent = loteNombre;
        
        modalCantidadInput.max = cantidadDisponible;
        modalCantidadInput.value = cantidadDisponible;
        modalCantidadDisponible.textContent = cantidadDisponible;
        form.reset();

        // Lógica de validación condicional
        selectResultado.addEventListener('change', function() {
            if (this.value === 'Otro') {
                textareaComentarios.required = true;
                textareaComentarios.previousElementSibling.textContent = 'Comentarios (Requerido):';
            } else {
                textareaComentarios.required = false;
                textareaComentarios.previousElementSibling.textContent = 'Comentarios:';
            }
        });

        if (action === 'cuarentena') {
            modalTitle.textContent = 'Poner Lote en Cuarentena';
            modalBtnConfirmar.className = 'btn btn-warning';
            modalBtnConfirmar.textContent = 'Confirmar Cuarentena';
        } else if (action === 'rechazar') {
            modalTitle.textContent = 'Rechazar Lote';
            modalBtnConfirmar.className = 'btn btn-danger';
            modalBtnConfirmar.textContent = 'Confirmar Rechazo';
        }
    }

    async function realizarAccion(loteId, action, formData = null, btnElement) {
        const originalBtnHTML = btnElement.innerHTML;
        btnElement.disabled = true;
        btnElement.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Procesando...`;

        const url = `/control-calidad/api/lote/${loteId}/${action}`;
        const options = {
            method: 'POST',
            headers: {},
        };
        if (formData) {
            options.body = formData;
        }

        try {
            const response = await fetch(url, options);
            const result = await response.json();

            if (response.ok && result.success) {
                actualizarFilaLote(loteId, result.data.estado);
                showNotificationModal('Éxito', result.message, 'success');
            } else {
                showNotificationModal('Error', result.error || 'Ocurrió un error inesperado.', 'danger');
            }
        } catch (error) {
            showNotificationModal('Error de Conexión', 'No se pudo conectar con el servidor.', 'danger');
        } finally {
            btnElement.disabled = false;
            btnElement.innerHTML = originalBtnHTML;
        }
    }

    async function finalizarInspeccion(btnElement) {
        const originalBtnHTML = btnElement.innerHTML;
        btnElement.disabled = true;
        btnElement.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Finalizando...`;

        const url = `/control-calidad/api/orden/${ordenId}/finalizar`;
        try {
            const response = await fetch(url, { method: 'POST' });
            const result = await response.json();

            if (response.ok && result.success) {
                showNotificationModal('Inspección Finalizada', 'La orden ha sido cerrada correctamente. Redirigiendo...', 'success');
                setTimeout(() => {
                    window.location.href = '/compras/'; 
                }, 2000);
            } else {
                showNotificationModal('Error', result.error || 'No se pudo finalizar la inspección.', 'danger');
                btnElement.disabled = false;
                btnElement.innerHTML = originalBtnHTML;
            }
        } catch (error) {
            showNotificationModal('Error de Conexión', 'No se pudo conectar con el servidor.', 'danger');
            btnElement.disabled = false;
            btnElement.innerHTML = originalBtnHTML;
        }
    }

    function actualizarFilaLote(loteId, nuevoEstado) {
        const accionesDiv = document.getElementById(`acciones-lote-${loteId}`);
        const config = estadoLoteConfig[nuevoEstado] || { class: 'bg-secondary', icon: 'question-circle-fill', text: nuevoEstado };
        
        accionesDiv.innerHTML = `
            <span class="badge ${config.class} fs-6">
                <i class="bi bi-${config.icon} me-1"></i> ${config.text}
            </span>
        `;

        const loteCard = document.querySelector(`.lote-card[data-lote-id='${loteId}']`);
        loteCard.dataset.estadoInicial = nuevoEstado;

        verificarEstadoGeneral();
    }

    function verificarEstadoGeneral() {
        const todosProcesados = [...document.querySelectorAll('.lote-card')].every(
            card => card.dataset.estadoInicial !== 'EN REVISION'
        );

        if (todosProcesados) {
            btnFinalizar.classList.remove('d-none');
        }
    }

    // Comprobación inicial al cargar la página
    verificarEstadoGeneral();
});
