
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
    const zonaIdElement = document.getElementById('zona-data');
    const zonaId = zonaIdElement ? JSON.parse(zonaIdElement.textContent).zonaId : null;
    let assignedIds = new Set();
    let allLocalidades = []; // Almacenará todas las localidades cargadas inicialmente

    // --- Inicialización ---
    async function initialize() {
        if (!form) return;

        assignedList.querySelectorAll('li').forEach(item => {
            assignedIds.add(item.dataset.id);
        });
        updateHiddenInput();
        validateForm();

        // Cargar todas las localidades al inicio
        await fetchAllLocalities();

        // --- Event Listeners ---
        nombreInput.addEventListener('input', validateForm);
        searchInput.addEventListener('input', onSearchInput);
        
        assignedList.querySelectorAll('.remove-localidad-btn').forEach(btn => {
            btn.addEventListener('click', onRemoveLocalidad);
        });
    }

    // --- Lógica de Búsqueda y Filtrado ---
    async function fetchAllLocalities() {
        try {
            // Hacemos una búsqueda inicial sin término para obtener todo
            const response = await fetch(`/admin/zonas/api/buscar-localidades?term=`);
            if (!response.ok) throw new Error('Error en la red');
            allLocalidades = await response.json();
            renderAvailableLocalities(allLocalidades); // Renderizar la lista completa
        } catch (error) {
            console.error('Error al cargar todas las localidades:', error);
            availableList.innerHTML = '<li class="list-group-item text-danger">Error al cargar la lista de localidades.</li>';
        }
    }

    function onSearchInput() {
        const searchTerm = searchInput.value.trim().toLowerCase();
        const filteredLocalidades = allLocalidades.filter(loc => {
            const locName = `${loc.localidad}, ${loc.provincia}`.toLowerCase();
            return locName.includes(searchTerm);
        });
        renderAvailableLocalities(filteredLocalidades);
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
                li.classList.add('active');
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
        onSearchInput(); // Refrescar la lista para marcar el item como activo
    }

    function onRemoveLocalidad(event) {
        const item = event.target.closest('li');
        const locId = item.dataset.id;
        
        assignedIds.delete(locId);
        item.remove();
        
        updateHiddenInput();
        validateForm();
        onSearchInput(); // Refrescar la lista para desmarcar el item
    }

    // --- Utilidades y Validación ---
    function updateHiddenInput() {
        const validIds = Array.from(assignedIds).filter(id => id);
        hiddenInput.value = JSON.stringify(validIds);
    }

    function validateForm() {
        const isNombreValid = nombreInput.value.trim() !== '';
        saveButton.disabled = !isNombreValid;
        
        if (isNombreValid) {
            nombreInput.classList.remove('is-invalid');
        } else {
            nombreInput.classList.add('is-invalid');
        }
    }

    // --- Ejecución ---
    initialize();
});
