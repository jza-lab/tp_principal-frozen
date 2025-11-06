document.addEventListener('DOMContentLoaded', function () {
    // Aislamos toda la lógica en este nuevo módulo para evitar conflictos.

    const focoContainer = document.getElementById('foco-container');
    if (!focoContainer) return; // No ejecutar si no estamos en la página de foco

    const ordenId = focoContainer.dataset.opId;

    // Elementos del DOM específicos para el traspaso
    const btnConfirmarTraspaso = document.getElementById('btn-confirmar-traspaso');
    const btnAceptarTraspaso = document.getElementById('btn-aceptar-traspaso');
    const traspasoBanner = document.getElementById('traspaso-banner');
    const modalTraspasoElement = document.getElementById('modalTraspasoTurno');
    const modalTraspaso = modalTraspasoElement ? new bootstrap.Modal(modalTraspasoElement) : null;

    // Función para mostrar notificaciones (reutilizada de foco_produccion.js)
    function showNotification(message, type = 'info') {
        // ... (código de notificación omitido por brevedad, se asumirá que existe globalmente o se copiará)
        console.log(`[${type.toUpperCase()}] ${message}`);
    }

    // Listener para el botón de confirmar el traspaso (operario saliente)
    if (btnConfirmarTraspaso) {
        btnConfirmarTraspaso.addEventListener('click', async (e) => {
            e.preventDefault();
            const form = document.getElementById('form-traspaso-turno');
            if (!form.checkValidity()) {
                form.classList.add('was-validated');
                return;
            }

            // 1. Pausar formalmente la orden
            const motivoParoSelect = document.getElementById('motivo-paro');
            const motivoCambioDeTurnoId = Array.from(motivoParoSelect.options).find(opt => opt.text.toLowerCase().includes('cambio de turno')).value;
            
            const responsePausa = await fetch(`/produccion/kanban/api/op/${ordenId}/pausar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ motivo_id: motivoCambioDeTurnoId })
            });

            if (!responsePausa.ok) {
                showNotification('Error al iniciar el proceso de traspaso. No se pudo pausar la orden.', 'error');
                return;
            }

            // 2. Preparar y enviar el reporte de traspaso
            const payload = {
                notas_novedades: document.getElementById('traspaso-novedades').value,
                notas_insumos: document.getElementById('traspaso-insumos').value,
                resumen_produccion: {
                    unidades_ok: document.getElementById('traspaso-unidades-ok').textContent,
                    unidades_malas: document.getElementById('traspaso-unidades-malas').textContent
                }
            };

            try {
                const response = await fetch(`/produccion/kanban/api/op/${ordenId}/traspaso`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    if (modalTraspaso) modalTraspaso.hide();
                    showNotification('Traspaso registrado. La orden está en pausa.', 'success');
                    // Redirigir al tablero kanban para que el operario pueda ver el estado general
                    window.location.href = '/produccion/kanban';
                } else {
                    showNotification(`Error al registrar el traspaso: ${data.error || 'Error desconocido'}`, 'error');
                }
            } catch (error) {
                showNotification('Error de red al registrar el traspaso.', 'error');
            }
        });
    }

    // Listener para el botón de aceptar el traspaso (operario entrante)
    if (btnAceptarTraspaso) {
        btnAceptarTraspaso.addEventListener('click', async () => {
            const traspasoId = btnAceptarTraspaso.dataset.traspasoId;
            try {
                const response = await fetch(`/produccion/kanban/api/op/${ordenId}/traspaso/${traspasoId}/aceptar`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    if (traspasoBanner) traspasoBanner.style.display = 'none';
                    showNotification('Traspaso aceptado. Reanudando producción...', 'success');
                    // Recargar la página para que el estado de reanudación se cargue correctamente
                    window.location.reload();
                } else {
                    showNotification(`Error al aceptar el traspaso: ${data.error || 'Error desconocido'}`, 'error');
                }
            } catch (error) {
                showNotification('Error de red al aceptar el traspaso.', 'error');
            }
        });
    }

    // Exponer función para abrir el modal de traspaso globalmente
    // para que el otro script pueda llamarla
    window.abrirModalTraspaso = function() {
        // Llenar el resumen de producción justo antes de mostrar
        const cantidadProducida = document.getElementById('cantidad-producida')?.textContent || '0 kg';
        const cantidadDesperdicio = document.getElementById('cantidad-desperdicio')?.textContent || '0 kg';
        document.getElementById('traspaso-unidades-ok').textContent = cantidadProducida;
        document.getElementById('traspaso-unidades-malas').textContent = cantidadDesperdicio;

        if (modalTraspaso) modalTraspaso.show();
    }
});
