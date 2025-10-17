document.addEventListener('DOMContentLoaded', function() {
    // --- Referencias a elementos del DOM ---
    const tipoSelect = document.getElementById('tipo');
    const fechaInput = document.getElementById('fecha_autorizada');
    const legajoInput = document.getElementById('legajo_empleado');
    const nombreInput = document.getElementById('nombre_empleado');
    const turnoAsignadoInput = document.getElementById('turno_asignado');
    const usuarioIdInput = document.getElementById('usuario_id');
    const legajoErrorDiv = document.getElementById('legajo-error');
    const turnoAutorizadoNombreInput = document.getElementById('turno_autorizado_nombre');
    const turnoAutorizadoIdInput = document.getElementById('turno_autorizado_id');

    // --- Estado de la aplicación ---
    let debounceTimer;
    let usuarioEncontrado = null;

    // --- Validación de Fecha ---
    const fechaErrorDiv = document.createElement('div');
    fechaErrorDiv.className = 'invalid-feedback';
    fechaInput.parentNode.insertBefore(fechaErrorDiv, fechaInput.nextSibling);

    function validateFecha() {
        const selectedDateStr = fechaInput.value;
        if (!selectedDateStr) return;
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const selectedDate = new Date(selectedDateStr + 'T00:00:00');
        if (selectedDate < today) {
            fechaInput.classList.add('is-invalid');
            fechaErrorDiv.textContent = 'La fecha no puede ser anterior a la actual.';
            fechaErrorDiv.style.display = 'block';
        } else {
            fechaInput.classList.remove('is-invalid');
            fechaErrorDiv.style.display = 'none';
        }
    }
    fechaInput.addEventListener('change', validateFecha);
    validateFecha();

    // --- Lógica de Determinación de Turno Autorizado ---
    function determinarTurnoAutorizado() {
        const tipoAutorizacion = tipoSelect.value;
        turnoAutorizadoNombreInput.value = '';
        turnoAutorizadoIdInput.value = '';

        if (!usuarioEncontrado || !usuarioEncontrado.turno) {
            turnoAutorizadoNombreInput.placeholder = 'Primero busque un empleado con turno asignado.';
            return;
        }

        const turnoEmpleado = usuarioEncontrado.turno.nombre.toLowerCase();

        if (tipoAutorizacion === 'LLEGADA_TARDIA') {
            turnoAutorizadoNombreInput.value = usuarioEncontrado.turno.nombre;
            turnoAutorizadoIdInput.value = usuarioEncontrado.turno.id;
        } else if (tipoAutorizacion === 'HORAS_EXTRAS') {
            let turnoOpuesto = null;
            if (turnoEmpleado.includes('mañana')) {
                turnoOpuesto = TODOS_LOS_TURNOS.find(t => t.nombre.toLowerCase().includes('tarde'));
            } else if (turnoEmpleado.includes('tarde')) {
                turnoOpuesto = TODOS_LOS_TURNOS.find(t => t.nombre.toLowerCase().includes('mañana'));
            }
            
            if (turnoOpuesto) {
                turnoAutorizadoNombreInput.value = turnoOpuesto.nombre;
                turnoAutorizadoIdInput.value = turnoOpuesto.id;
            } else {
                turnoAutorizadoNombreInput.placeholder = 'No se encontró un turno opuesto válido.';
            }
        }
    }

    tipoSelect.addEventListener('change', determinarTurnoAutorizado);

    // --- Lógica de Búsqueda de Empleado por Legajo ---
    async function buscarEmpleado() {
        const legajo = legajoInput.value.trim();
        
        // Resetear campos antes de una nueva búsqueda
        nombreInput.value = '';
        turnoAsignadoInput.value = '';
        usuarioIdInput.value = '';
        turnoAutorizadoNombreInput.value = '';
        turnoAutorizadoIdInput.value = '';
        usuarioEncontrado = null;
        legajoInput.classList.remove('is-invalid');
        legajoErrorDiv.textContent = '';

        if (legajo.length < 3) {
            return;
        }

        nombreInput.value = 'Buscando...';

        try {
            const response = await fetch(`/api/usuarios/buscar?legajo=${legajo}`);
            const resultado = await response.json();

            if (resultado.success) {
                usuarioEncontrado = resultado.data;
                nombreInput.value = `${usuarioEncontrado.nombre} ${usuarioEncontrado.apellido}`;
                turnoAsignadoInput.value = usuarioEncontrado.turno ? usuarioEncontrado.turno.nombre : 'No asignado';
                usuarioIdInput.value = usuarioEncontrado.id;
                determinarTurnoAutorizado(); // Determinar turno autorizado después de encontrar al usuario
            } else {
                nombreInput.value = '';
                nombreInput.placeholder = 'Empleado no encontrado.';
                legajoInput.classList.add('is-invalid');
                legajoErrorDiv.textContent = resultado.error || 'No se encontró un usuario con ese legajo.';
            }
        } catch (error) {
            console.error('Error al buscar empleado:', error);
            nombreInput.value = '';
            nombreInput.placeholder = 'Error en la búsqueda.';
            legajoInput.classList.add('is-invalid');
            legajoErrorDiv.textContent = 'Error al conectar con el servidor.';
        }
    }

    legajoInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(buscarEmpleado, 500);
    });

    // Determinar el turno autorizado al cargar la página si ya hay un tipo seleccionado
    determinarTurnoAutorizado();
});