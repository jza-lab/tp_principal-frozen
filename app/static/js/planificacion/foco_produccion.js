document.addEventListener('DOMContentLoaded', function () {

    // --- ELEMENTOS DEL DOM ---
    const focoContainer = document.getElementById('foco-container');
    const opId = focoContainer.dataset.opId;

    const timerDisplay = document.getElementById('timer');
    const progressBar = document.getElementById('progress-bar');
    const cantidadProducidaSpan = document.getElementById('cantidad-producida');
    
    const btnReportarAvance = document.getElementById('btn-reportar-avance');
    const btnPausarReanudar = document.getElementById('btn-pausar-reanudar');
    const pauseOverlay = document.getElementById('pause-overlay');

    // Modales
    const modalReportarAvance = new bootstrap.Modal(document.getElementById('modalReportarAvance'));
    const modalPausarProduccion = new bootstrap.Modal(document.getElementById('modalPausarProduccion'));

    // Formularios de modales
    const formReportarAvance = document.getElementById('formReportarAvance');
    const formPausarProduccion = document.getElementById('formPausarProduccion');
    
    // --- ESTADO ---
    let timerInterval;
    let isPaused = false;
    let accumulatedTime = 0; // Tiempo en segundos
    let lastStartTime = Date.now();

    // --- INICIALIZACIÓN ---

    function init() {
        populateDropdowns();
        startTimer();
        setupEventListeners();
        // Chequear si ya está en pausa al cargar la página (lógica más avanzada)
    }

    function populateDropdowns() {
        const motivoDesperdicioSelect = document.getElementById('motivo-desperdicio');
        MOTIVOS_DESPERDICIO.forEach(motivo => {
            const option = new Option(motivo.descripcion, motivo.id);
            motivoDesperdicioSelect.add(option);
        });

        const motivoParoSelect = document.getElementById('motivo-paro');
        MOTIVOS_PARO.forEach(motivo => {
            const option = new Option(motivo.descripcion, motivo.id);
            motivoParoSelect.add(option);
        });
    }

    // --- LÓGICA DEL CRONÓMETRO ---

    function startTimer() {
        lastStartTime = Date.now();
        timerInterval = setInterval(updateTimer, 1000);
    }

    function stopTimer() {
        clearInterval(timerInterval);
        accumulatedTime += (Date.now() - lastStartTime) / 1000;
    }

    function updateTimer() {
        const elapsedTime = accumulatedTime + (Date.now() - lastStartTime) / 1000;
        const hours = Math.floor(elapsedTime / 3600);
        const minutes = Math.floor((elapsedTime % 3600) / 60);
        const seconds = Math.floor(elapsedTime % 60);
        timerDisplay.textContent = 
            `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }

    // --- MANEJADORES DE EVENTOS ---

    function setupEventListeners() {
        btnReportarAvance.addEventListener('click', () => {
            modalReportarAvance.show();
        });

        formReportarAvance.addEventListener('submit', handleReportarAvance);

        btnPausarReanudar.addEventListener('click', handlePausaReanudar);
        
        formPausarProduccion.addEventListener('submit', handleConfirmarPausa);

        // Mostrar/ocultar motivo de desperdicio
        document.getElementById('cantidad-desperdicio').addEventListener('input', function() {
            const container = document.getElementById('motivo-desperdicio-container');
            container.style.display = parseFloat(this.value) > 0 ? 'block' : 'none';
        });
    }

    // --- LÓGICA DE ACCIONES ---

    async function handleReportarAvance(event) {
        event.preventDefault();
        const btn = document.getElementById('btn-submit-reporte');
        btn.disabled = true;

        const data = {
            cantidad_buena: document.getElementById('cantidad-buena').value,
            cantidad_desperdicio: document.getElementById('cantidad-desperdicio').value || 0,
            motivo_desperdicio_id: document.getElementById('motivo-desperdicio').value,
            finalizar_orden: document.getElementById('finalizar-orden').checked,
            observaciones: document.getElementById('observaciones-reporte').value
        };

        try {
            const response = await fetch(`/tabla-produccion/api/op/${opId}/reportar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Error en el servidor');
            
            modalReportarAvance.hide();
            // TODO: Actualizar UI sin recargar
            if (data.finalizar_orden) {
                alert('¡Orden Finalizada! Redirigiendo al tablero...');
                window.location.href = '/tabla-produccion';
            } else {
                window.location.reload(); // Recarga simple por ahora para ver el progreso
            }

        } catch (error) {
            alert(`Error al reportar avance: ${error.message}`);
        } finally {
            btn.disabled = false;
        }
    }

    function handlePausaReanudar() {
        if (isPaused) {
            // Lógica para reanudar
            handleReanudar();
        } else {
            // Lógica para pausar
            modalPausarProduccion.show();
        }
    }
    
    async function handleConfirmarPausa(event) {
        event.preventDefault();
        const btn = document.getElementById('btn-submit-pausa');
        btn.disabled = true;
        
        const motivoId = document.getElementById('motivo-paro').value;
        if (!motivoId) {
            alert('Debe seleccionar un motivo de pausa.');
            btn.disabled = false;
            return;
        }

        try {
            const response = await fetch(`/tabla-produccion/api/op/${opId}/pausar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ motivo_id: motivoId })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Error en el servidor');

            modalPausarProduccion.hide();
            isPaused = true;
            stopTimer();
            pauseOverlay.style.display = 'flex';
            btnPausarReanudar.innerHTML = '<i class="bi bi-play-fill me-2"></i>Reanudar Trabajo';
            btnPausarReanudar.classList.replace('btn-warning', 'btn-success');
            btnReportarAvance.disabled = true;

        } catch (error) {
            alert(`Error al pausar la producción: ${error.message}`);
        } finally {
            btn.disabled = false;
        }
    }

    async function handleReanudar() {
        btnPausarReanudar.disabled = true;
        try {
            const response = await fetch(`/tabla-produccion/api/op/${opId}/reanudar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Error en el servidor');
            
            isPaused = false;
            startTimer();
            pauseOverlay.style.display = 'none';
            btnPausarReanudar.innerHTML = '<i class="bi bi-pause-fill me-2"></i>Pausar Trabajo';
            btnPausarReanudar.classList.replace('btn-success', 'btn-warning');
            btnReportarAvance.disabled = false;

        } catch (error) {
            alert(`Error al reanudar la producción: ${error.message}`);
        } finally {
            btnPausarReanudar.disabled = false;
        }
    }

    // --- INICIAR TODO ---
    init();
});
