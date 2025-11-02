// app/static/js/planificacion/foco_produccion.js
document.addEventListener('DOMContentLoaded', function () {
    // --- ELEMENTOS DEL DOM ---
    const focoContainer = document.getElementById('foco-container');
    const ordenId = focoContainer.dataset.opId;
    const timerDisplay = document.getElementById('timer');
    const pauseOverlay = document.getElementById('pause-overlay');
    const btnPausarReanudar = document.getElementById('btn-pausar-reanudar');
    const btnConfirmarPausa = document.getElementById('btn-confirmar-pausa');
    const btnConfirmarReporte = document.getElementById('btn-confirmar-reporte');
    const cantidadProducidaDisplay = document.getElementById('cantidad-producida');
    const cantidadDesperdicioDisplay = document.getElementById('cantidad-desperdicio');
    const progressBar = document.getElementById('progress-bar');
    const cantidadMalaInput = document.getElementById('cantidad-mala');
    const motivoDesperdicioContainer = document.getElementById('motivo-desperdicio-container');
    const motivoDesperdicioSelect = document.getElementById('motivo-desperdicio');

    // --- ESTADO ---
    let timerInterval;
    let segundosTranscurridos = 0;
    let isPaused = false;

    // --- LÓGICA DEL CRONÓMETRO ---
    function formatTime(seconds) {
        const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
        const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
        const s = (seconds % 60).toString().padStart(2, '0');
        return `${h}:${m}:${s}`;
    }

    function startTimer() {
        if (timerInterval) return;
        timerInterval = setInterval(() => {
            segundosTranscurridos++;
            timerDisplay.textContent = formatTime(segundosTranscurridos);
        }, 1000);
    }

    function stopTimer() {
        clearInterval(timerInterval);
        timerInterval = null;
    }

    // --- LÓGICA DE PAUSA / REANUDACIÓN ---
    function pausarProduccion() {
        stopTimer();
        isPaused = true;
        pauseOverlay.style.display = 'flex';
        btnPausarReanudar.innerHTML = '<i class="bi bi-play-fill me-2"></i>Reanudar Trabajo';
        btnPausarReanudar.classList.remove('btn-warning');
        btnPausarReanudar.classList.add('btn-success');
    }

    function reanudarProduccion() {
        startTimer();
        isPaused = false;
        pauseOverlay.style.display = 'none';
        btnPausarReanudar.innerHTML = '<i class="bi bi-pause-fill me-2"></i>Pausar Trabajo';
        btnPausarReanudar.classList.remove('btn-success');
        btnPausarReanudar.classList.add('btn-warning');
    }

    btnConfirmarPausa.addEventListener('click', async (e) => {
        e.preventDefault();
        const motivoId = document.getElementById('motivo-paro').value;
        if (!motivoId) {
            // Manejar error de validación
            return;
        }

        const response = await fetch(`/tabla-produccion/api/op/${ordenId}/pausar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ motivo_id: motivoId })
        });

        if (response.ok) {
            pausarProduccion();
            bootstrap.Modal.getInstance(document.getElementById('modalPausarProduccion')).hide();
        } else {
            // Manejar error
        }
    });
    
    btnPausarReanudar.addEventListener('click', async () => {
        if (isPaused) {
            const response = await fetch(`/tabla-produccion/api/op/${ordenId}/reanudar`, {
                method: 'POST'
            });
            if (response.ok) {
                reanudarProduccion();
            } else {
                // Manejar error
            }
        } else {
            bootstrap.Modal.getOrCreateInstance(document.getElementById('modalPausarProduccion')).show();
        }
    });

    // --- LÓGICA DE REPORTE DE AVANCE ---
    cantidadMalaInput.addEventListener('input', () => {
        const cantidadMala = parseFloat(cantidadMalaInput.value) || 0;
        if (cantidadMala > 0) {
            motivoDesperdicioContainer.style.display = 'block';
            motivoDesperdicioSelect.required = true;
        } else {
            motivoDesperdicioContainer.style.display = 'none';
            motivoDesperdicioSelect.required = false;
        }
    });

    btnConfirmarReporte.addEventListener('click', async (e) => {
        e.preventDefault();
        const form = document.getElementById('form-reportar');
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        const data = {
            cantidad_buena: document.getElementById('cantidad-buena').value,
            cantidad_desperdicio: cantidadMalaInput.value,
            motivo_desperdicio_id: motivoDesperdicioSelect.value,
            finalizar_orden: document.querySelector('input[name="tipo_reporte"]:checked').value === 'final'
        };

        const response = await fetch(`/tabla-produccion/api/op/${ordenId}/reportar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            if (data.finalizar_orden) {
                window.location.href = '/tabla-produccion/';
            } else {
                // Actualizar UI
                // Esta parte debería obtener los nuevos totales desde la respuesta de la API
                // Por simplicidad, lo calculamos en el frontend por ahora.
                const totalProducido = parseFloat(cantidadProducidaDisplay.textContent) + parseFloat(data.cantidad_buena);
                const totalDesperdicio = parseFloat(cantidadDesperdicioDisplay.textContent) + parseFloat(data.cantidad_desperdicio);
                cantidadProducidaDisplay.textContent = `${totalProducido.toFixed(2)} kg`;
                cantidadDesperdicioDisplay.textContent = `${totalDesperdicio.toFixed(2)} kg`;
                
                // Actualizar barra de progreso
                const cantidadPlanificada = parseFloat(document.querySelector('.display-4').textContent);
                const progress = (totalProducido / cantidadPlanificada) * 100;
                progressBar.style.width = `${progress}%`;
                progressBar.setAttribute('aria-valuenow', progress);
                
                bootstrap.Modal.getInstance(document.getElementById('modalReportarAvance')).hide();
                form.reset();
            }
        } else {
            // Manejar error
        }
    });


    // --- INICIALIZACIÓN ---
    startTimer();
});
