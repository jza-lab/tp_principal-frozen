
document.addEventListener('DOMContentLoaded', function () {
    // --- Referencias a Elementos del DOM ---
    const form = document.querySelector('form');
    const nombreInput = document.getElementById('nombre');
    const searchInput = document.getElementById('localidad-search');
    const availableList = document.getElementById('available-localities');
    const assignedList = document.getElementById('assigned-localities');
    const hiddenInput = document.getElementById('localidades_ids');
    const saveButton = document.querySelector('button[type="submit"]');
    
    // --- Estado ---
    // La variable 'zonaId' debe ser inyectada desde el template.
    // Buscamos un script tag que la contenga.
    const zonaIdElement = document.getElementById('zona-data');
    const zonaId = zonaIdElement ? JSON.parse(zonaIdElement.textContent).zonaId : null;

    let assignedIds = new Set();
    let debounceTimer;

    // --- Inicialización ---
    function initialize() {
        if (!form) return; // No ejecutar si no estamos en la página del formulario

        // Cargar los IDs de las localidades ya asignadas
        assignedList.querySelectorAll('li').forEach(item => {
            assignedIds.add(item.dataset.id);
        });
        updateHiddenInput();
        validateForm(); // Validar el estado inicial del formulario

        // --- Event Listeners ---
        nombreInput.addEventListener('input', validateForm);
        searchInput.addEventListener('input', onSearchInput);
        
        // Asignar evento para los botones de eliminar existentes
        assignedList.querySelectorAll('.remove-localidad-btn').forEach(btn => {
            btn.addEventListener('click', onRemoveLocalidad);
        });
    }

    // --- Lógica de Búsqueda ---
    function onSearchInput() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetchAvailableLocalities(searchInput.value.trim());
        }, 300); // Debounce de 300ms
    }

    async function fetchAvailableLocalities(term) {
        if (term.length < 3) {
            availableList.innerHTML = '<li class="list-group-item text-muted">Escriba al menos 3 letras para buscar...</li>';
            return;
        }

        try {
            const response = await fetch(`/admin/zonas/api/buscar-localidades?term=${encodeURIComponent(term)}`);
            if (!response.ok) throw new Error('Error en la red');
            const localidades = await response.json();
            renderAvailableLocalities(localidades);
        } catch (error) {
            console.error('Error al buscar localidades:', error);
            availableList.innerHTML = '<li class="list-group-item text-danger">Error al cargar localidades.</li>';
        }
    }

    function renderAvailableLocalities(localidades) {
        availableList.innerHTML = '';
        if (localidades.length === 0) {
            availableList.innerHTML = '<li class="list-group-item text-muted">No se encontraron localidades.</li>';
            return;
        }

        localidades.forEach(loc => {
            const li = document.createElement('li');
            li.className = 'list-group-item d-flex justify-content-between align-items-center';
            
            const isAssignedToCurrent = assignedIds.has(String(loc.id));
            const isAssignedToOther = loc.zona_asignada && loc.zona_id !== zonaId;

            let content = `${loc.localidad}, ${loc.provincia}`;
            if (isAssignedToOther) {
                content += ` <small class="text-muted fst-italic">(en ${loc.zona_asignada})</small>`;
                li.classList.add('disabled');
            } else if (isAssignedToCurrent) {
                li.classList.add('active'); // Ya está en la lista de asignadas
            } else {
                li.style.cursor = 'pointer';
                li.addEventListener('click', () => onAddLocalidad(loc));
            }
            
            li.innerHTML = content;
            availableList.appendChild(li);
        });
    }

    // --- Lógica de Asignación/Desasignación ---
    function onAddLocalidad(loc) {
        if (assignedIds.has(String(loc.id))) return;

        assignedIds.add(String(loc.id));
        
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.dataset.id = loc.id;
        li.textContent = `${loc.localidad}, ${loc.provincia}`;

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'btn btn-danger btn-sm remove-localidad-btn';
        removeBtn.innerHTML = '&times;';
        removeBtn.addEventListener('click', onRemoveLocalidad);

        li.appendChild(removeBtn);
        assignedList.appendChild(li);
        
        updateHiddenInput();
        validateForm();
        fetchAvailableLocalities(searchInput.value.trim()); // Refrescar la lista de disponibles
    }

    function onRemoveLocalidad(event) {
        const item = event.target.closest('li');
        const locId = item.dataset.id;
        
        assignedIds.delete(locId);
        item.remove();
        
        updateHiddenInput();
        validateForm();
        fetchAvailableLocalities(searchInput.value.trim()); // Refrescar la lista de disponibles
    }

    // --- Utilidades y Validación ---
    function updateHiddenInput() {
        // Filtramos para asegurarnos de que solo haya IDs válidos (no null/undefined)
        const validIds = Array.from(assignedIds).filter(id => id);
        hiddenInput.value = JSON.stringify(validIds);
    }

    function validateForm() {
        const isNombreValid = nombreInput.value.trim() !== '';
        
        if (isNombreValid) {
            nombreInput.classList.remove('is-invalid');
            saveButton.disabled = false;
        } else {
            nombreInput.classList.add('is-invalid');
            saveButton.disabled = true;
        }
    }

    // --- Ejecución ---
    initialize();
});
