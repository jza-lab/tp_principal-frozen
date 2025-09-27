// Establecer fecha mínima como hoy
document.addEventListener('DOMContentLoaded', function() {
    const fechaInput = document.getElementById('fecha_planificada');
    if (!fechaInput.value) {
        const today = new Date().toISOString().split('T')[0];
        fechaInput.value = today;
    }
    fechaInput.min = new Date().toISOString().split('T')[0];
});

// Simulación de validaciones dinámicas
function mostrarValidaciones() {
    const validacionesContainer = document.getElementById('validaciones-container');
    validacionesContainer.innerHTML = `
        <div class="alert alert-success border-success p-3">
            <div class="d-flex align-items-center mb-2">
                <i class="bi bi-check-circle-fill text-success me-2"></i>
                <strong>Stock Suficiente</strong>
            </div>
            <small class="text-muted">
                • Carne molida: 15kg disponibles<br>
                • Cebolla: 8kg disponibles<br>
                • Masa: 200 unidades disponibles
            </small>
        </div>
    `;
}

function mostrarEstimaciones() {
    const estimacionesContainer = document.getElementById('estimaciones-container');
    estimacionesContainer.innerHTML = `
        <div class="row text-center">
            <div class="col-6">
                <div class="border-end pe-3">
                    <div class="h5 mb-0">~3.5h</div>
                    <small class="text-muted">Tiempo Estimado</small>
                </div>
            </div>
            <div class="col-6">
                <div class="h5 mb-0">~2.1%</div>
                <small class="text-muted">Merma Estimada</small>
            </div>
        </div>
    `;
}
