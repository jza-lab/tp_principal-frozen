document.addEventListener('DOMContentLoaded', function () {
    // Tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    const itemsContainer = document.getElementById('itemsContainer');
    const ivaCheckbox = document.getElementById('iva');
    const porcentajeGananciaInput = document.getElementById('porcentaje_ganancia');
    const formulario = document.getElementById('formulario-producto');
    
    // Nuevos campos de display
    const displayCostoMateriaPrima = document.getElementById('display_costo_materia_prima');
    const displayCostoManoObra = document.getElementById('display_costo_mano_obra');
    const displayCostoFijos = document.getElementById('display_costo_fijos');
    const displayCostoTotalProduccion = document.getElementById('display_costo_total_produccion');
    const displayPrecioFinal = document.getElementById('display_precio_final');
    
    const insumosData = typeof INSUMOS_DATA !== 'undefined' && Array.isArray(INSUMOS_DATA) ? INSUMOS_DATA : [];
    const rolesData = typeof ROLES_DATA !== 'undefined' && Array.isArray(ROLES_DATA) ? ROLES_DATA : [];
    const recetaOperaciones = typeof RECETA_OPERACIONES !== 'undefined' && Array.isArray(RECETA_OPERACIONES) ? RECETA_OPERACIONES : [];
    const costosFijosData = typeof COSTOS_FIJOS_DATA !== 'undefined' && Array.isArray(COSTOS_FIJOS_DATA) ? COSTOS_FIJOS_DATA : [];

    // --- LÓGICA DE OPERACIONES (PASOS DE PRODUCCIÓN) ---
    const operacionesContainer = document.getElementById('operaciones-container');
    const FIXED_STEPS = ['Preparacion Previa', 'Coccion', 'Refrigeracion', 'Empaquetado'];

    function renderFixedSteps() {
        operacionesContainer.innerHTML = ''; // Limpiar cualquier contenido previo

        FIXED_STEPS.forEach((stepName, index) => {
            const secuencia = index + 1;
            
            // Buscar si ya existe este paso en los datos cargados (para edición)
            const existingStep = recetaOperaciones.find(op => op.nombre_operacion === stepName);
            
            // Valores por defecto o cargados
            const prepTime = existingStep ? existingStep.tiempo_preparacion : 0;
            const execTime = existingStep ? existingStep.tiempo_ejecucion_unitario : 0;
            const assignedRolesDetail = existingStep ? (existingStep.roles_detalle || []) : [];
            const assignedCostosFijos = existingStep ? (existingStep.costos_fijos_ids || []) : [];

            // Convert assigned roles to a map for easier lookup {rol_id: porcentaje}
            const assignedRolesMap = {};
            assignedRolesDetail.forEach(r => assignedRolesMap[r.rol_id] = r.porcentaje_participacion);

            // Construir opciones del select de roles y el HTML para porcentajes
            let roleOptions = '';
            let roleInputsHtml = '';
            
            rolesData.forEach(rol => {
                const isSelected = assignedRolesMap.hasOwnProperty(rol.id) ? 'selected' : '';
                const percent = assignedRolesMap.hasOwnProperty(rol.id) ? assignedRolesMap[rol.id] : 100;
                const displayStyle = isSelected ? 'block' : 'none';

                roleOptions += `<option value="${rol.id}" ${isSelected}>${rol.nombre}</option>`;
                
                // Input para porcentaje de este rol
                roleInputsHtml += `
                    <div class="role-percent-input mb-1" id="role-percent-${secuencia}-${rol.id}" style="display: ${displayStyle};">
                        <div class="d-flex justify-content-between">
                            <label class="small text-muted">${rol.nombre} (%):</label>
                        </div>
                        <input type="number" class="form-control form-control-sm role-percent" 
                               name="operacion_rol_pct_${secuencia}_${rol.id}" 
                               data-secuencia="${secuencia}"
                               value="${percent}" min="1" max="100" step="1">
                    </div>
                `;
            });

            // Construir opciones de Costos Fijos
            let costosFijosOptions = '';
            costosFijosData.forEach(cf => {
                const isSelected = assignedCostosFijos.includes(cf.id) ? 'selected' : '';
                // Updated: use nombre_costo based on listar.html and add Tipo
                const displayName = cf.nombre_costo || cf.nombre || cf.concepto || cf.descripcion || `Costo Fijo #${cf.id}`;
                const tipo = cf.tipo ? `(${cf.tipo})` : '';
                costosFijosOptions += `<option value="${cf.id}" ${isSelected}>${displayName} ${tipo}</option>`;
            });


            const row = document.createElement('div');
            row.className = 'list-group-item operacion-row mb-3';
            row.dataset.secuencia = secuencia;

            row.innerHTML = `
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">Paso ${secuencia}: 
                        <input type="text" class="form-control form-control-sm d-inline-block w-auto bg-light" 
                               name="operacion_nombre[]" value="${stepName}" readonly>
                    </h6>
                </div>
                <div class="row g-2 mt-2">
                    <div class="col-md-3">
                        <label class="form-label">Roles Asignados <span class="text-danger">*</span></label>
                        <select class="form-select select2-roles" name="operacion_roles_${secuencia}[]" multiple required data-secuencia="${secuencia}">
                            ${roleOptions}
                        </select>
                        <div class="mt-2 role-percentages-container">
                            ${roleInputsHtml}
                            <div class="small mt-1 fw-bold text-danger pct-warning" id="pct-warning-${secuencia}" style="display: none;">
                                La suma debe ser 100%
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                         <label class="form-label">
                            Costos Fijos Relacionados
                            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip" 
                               title="Seleccione costos fijos (ej. Energía, Gas) que se consumen durante este paso. El sistema calculará el costo proporcional usando el tiempo de este paso y la tasa horaria del costo fijo.">
                            </i>
                         </label>
                         <select class="form-select select2-cf" name="operacion_cf_${secuencia}[]" multiple>
                            ${costosFijosOptions}
                         </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">T. Preparación (min) <span class="text-danger">*</span></label>
                        <input type="number" class="form-control" name="operacion_prep[]" 
                               value="${prepTime}" min="0.01" max="120" step="0.01" required>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">T. Ejecución (min/u) <span class="text-danger">*</span></label>
                        <input type="number" class="form-control" name="operacion_ejec[]" 
                               value="${execTime}" min="0.01" max="120" step="0.01" required>
                    </div>
                    <div class="col-12 text-end">
                         <input type="hidden" name="operacion_secuencia[]" value="${secuencia}">
                    </div>
                </div>
            `;
            operacionesContainer.appendChild(row);
        });

        // Inicializar Select2 y Tooltips para elementos dinámicos
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $(operacionesContainer).find('.select2-roles').select2({
                placeholder: "Seleccionar roles...",
                allowClear: true
            }).on('change', function(e) {
                // Mostrar/Ocultar inputs de porcentaje basado en la selección
                const selectedValues = $(this).val() || [];
                const secuencia = $(this).data('secuencia');
                const container = $(this).closest('.col-md-3').find('.role-percentages-container');
                
                // Resetear todos los inputs a 0 o esconderlos
                container.find('.role-percent-input').hide();
                
                // Lógica de auto-distribución
                if (selectedValues.length > 0) {
                    const share = Math.floor(100 / selectedValues.length);
                    const remainder = 100 % selectedValues.length;
                    
                    selectedValues.forEach((rolId, index) => {
                        const inputDiv = container.find(`#role-percent-${secuencia}-${rolId}`);
                        inputDiv.show();
                        
                        // Solo auto-distribuir si estamos en una nueva selección o si se desea resetear
                        // Aquí implementamos una distribución simple al cambiar la selección
                        // Asignamos el remanente al primer elemento
                        const value = share + (index === 0 ? remainder : 0);
                        const input = inputDiv.find('input');
                        
                        // Opcional: Podríamos chequear si ya tenía valor manual, pero "auto-distribute" implica sobreescribir para facilitar.
                        input.val(value);
                    });
                }
                
                validarPorcentajes(secuencia);
                actualizarCostosDinamicos();
            });

            $(operacionesContainer).find('.select2-cf').select2({
                placeholder: "Seleccionar costos fijos...",
                allowClear: true
            }).on('change', function() {
                actualizarCostosDinamicos();
            });
        }

        // Re-inicializar tooltips para los nuevos elementos
        var newTooltipTriggerList = [].slice.call(operacionesContainer.querySelectorAll('[data-bs-toggle="tooltip"]'));
        newTooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    function validarPorcentajes(secuencia) {
        // Get the row for this sequence
        const row = operacionesContainer.querySelector(`.operacion-row[data-secuencia="${secuencia}"]`);
        if (!row) return true;

        const rolesSelect = row.querySelector('.select2-roles');
        let selectedRoles = [];
        if (typeof $ !== 'undefined') {
            selectedRoles = $(rolesSelect).val() || [];
        } else {
            selectedRoles = Array.from(rolesSelect.selectedOptions).map(o => o.value);
        }

        if (selectedRoles.length === 0) {
            row.querySelector(`#pct-warning-${secuencia}`).style.display = 'none';
            // Remove invalid class from all inputs in this row
            row.querySelectorAll('.role-percent').forEach(input => input.classList.remove('is-invalid'));
            return true;
        }

        let totalPct = 0;
        selectedRoles.forEach(rolId => {
            const input = row.querySelector(`input[name="operacion_rol_pct_${secuencia}_${rolId}"]`);
            totalPct += parseFloat(input ? input.value : 0) || 0;
        });

        const warningEl = row.querySelector(`#pct-warning-${secuencia}`);
        const isValid = Math.abs(totalPct - 100) <= 0.1;

        if (!isValid) {
            warningEl.textContent = `Suma actual: ${totalPct}% (Debe ser 100%)`;
            warningEl.style.display = 'block';
            // Add visual feedback to inputs
            selectedRoles.forEach(rolId => {
                const input = row.querySelector(`input[name="operacion_rol_pct_${secuencia}_${rolId}"]`);
                if(input) input.classList.add('is-invalid');
            });
            return false;
        } else {
            warningEl.style.display = 'none';
            // Remove visual feedback
            selectedRoles.forEach(rolId => {
                const input = row.querySelector(`input[name="operacion_rol_pct_${secuencia}_${rolId}"]`);
                if(input) input.classList.remove('is-invalid');
            });
            return true;
        }
    }

    // Listener para recalcular costos y validar porcentajes
    operacionesContainer.addEventListener('input', function(e) {
        if (e.target.classList.contains('role-percent')) {
            const secuencia = e.target.dataset.secuencia;
            validarPorcentajes(secuencia);
            actualizarCostosDinamicos();
        } else if (e.target.matches('input[name="operacion_prep[]"]') || 
                   e.target.matches('input[name="operacion_ejec[]"]')) {
            actualizarCostosDinamicos();
        }
    });
    
    // --- LÓGICA DEL MODAL DE BÚSQUEDA ---
    const insumoSearchModal = new bootstrap.Modal(document.getElementById('insumoSearchModal'));
    const searchFilterInput = document.getElementById('insumo-search-filter');
    const insumoSelect = document.getElementById('insumo-select');

    function poblarInsumosEnModal() {
        insumoSelect.innerHTML = '';
        insumosData.forEach(insumo => {
            const option = document.createElement('option');
            option.value = insumo.id;
            option.textContent = `${insumo.nombre} (${insumo.unidad_medida})`;
            option.dataset.id = insumo.id_insumo;
            option.dataset.unidad = insumo.unidad_medida;
            option.dataset.precio = insumo.precio_unitario;
            insumoSelect.appendChild(option);
        });
    }

    searchFilterInput.addEventListener('input', function () {
        const searchTerm = this.value.toLowerCase();
        Array.from(insumoSelect.options).forEach(option => {
            const text = option.textContent.toLowerCase();
            option.style.display = text.includes(searchTerm) ? '' : 'none';
        });
    });

    insumoSelect.addEventListener('dblclick', function () {
        const selectedOption = this.options[this.selectedIndex];
        if (!selectedOption || !selectedOption.value) return;
        
        const insumoSeleccionado = insumosData.find(i => i.id_insumo === selectedOption.dataset.id);
        if (insumoSeleccionado) {
            agregarItemAReceta(insumoSeleccionado);
        }
        insumoSearchModal.hide();
    });

    document.getElementById('insumoSearchModal').addEventListener('shown.bs.modal', function () {
        poblarInsumosEnModal();
        searchFilterInput.focus();
    });

    function agregarItemAReceta(insumo) {
        let itemExistente = false;
        const insumoIdAAgregar = insumo.id_insumo;

        itemsContainer.querySelectorAll('.item-row').forEach(row => {
            const selector = row.querySelector('.insumo-selector');
            const insumoIdActual = selector.value;
            if (insumoIdActual === insumoIdAAgregar) {
                const cantidadInput = row.querySelector('.cantidad');
                cantidadInput.value = (parseFloat(cantidadInput.value) || 0) + 1;
                itemExistente = true;
            }
        });

        if (itemExistente) {
            calcularTotales();
            return; 
        }

        const row = document.createElement('div');
        row.className = 'row g-3 align-items-end item-row mb-2';
        row.innerHTML = `
            <div class="col-md-4">
                <label class="form-label">Insumo</label>
                <select class="form-select insumo-selector" name="insumo_id[]" required>
                    <option value="${insumo.id_insumo}" data-unidad="${insumo.unidad_medida}" data-precio="${insumo.precio_unitario}" selected>${insumo.nombre}</option>
                </select>
            </div>
            <div class="col-md-2">
                <label class="form-label">Cantidad <span class="unidad-receta-display">(${insumo.unidad_medida})</span></label>
                <input type="number" min="0.01" step="0.01" max="5000" class="form-control cantidad" name="cantidad[]" value="1" required>
            </div>
            <div class="col-md-2">
                <label class="form-label">Precio Unitario</label>
                <input type="text" class="form-control precio_unitario" value="${formatearADinero(insumo.precio_unitario)}" readonly>
            </div>
            <div class="col-md-2">
                <label class="form-label">Subtotal</label>
                <input type="text" class="form-control subtotal-item" value="${formatearADinero(insumo.precio_unitario)}" readonly>
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-outline-danger removeItemBtn">Eliminar</button>
            </div>
        `;
        itemsContainer.appendChild(row);
        calcularTotales();
    }

    function limpiarFormatoDinero(valorConFormato) {
        if (!valorConFormato) return 0;
        let valorStr = valorConFormato.toString();
        if (valorStr.includes(',')) {
            const cleanString = valorStr.replace(/[$.]/g, '').replace(/[^\d,]/g, '').replace(',', '.');
            return parseFloat(cleanString) || 0;
        } else {
            const cleanString = valorStr.replace(/[^\d.]/g, '');
            return parseFloat(cleanString) || 0;
        }
    }

    function formatearADinero(numero) {
        if (isNaN(numero) || numero === null) return '$ 0,00';
        return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(numero);
    }
    
    function updateUnitDisplay(row) {
        const selector = row.querySelector('.insumo-selector');
        const unidadDisplay = row.querySelector('.unidad-receta-display');
        const selectedOption = selector.options[selector.selectedIndex];
        if (unidadDisplay && selectedOption) {
            unidadDisplay.textContent = `(${selectedOption.dataset.unidad || ''})`;
        }
    }

    function calcularTotales() {
        let costoMateriaPrima = 0;
        let detalleMateriaPrima = [];

        itemsContainer.querySelectorAll('.item-row').forEach(row => {
            const precio = limpiarFormatoDinero(row.querySelector('.precio_unitario').value);
            const cantidad = parseFloat(row.querySelector('.cantidad').value) || 0;
            const subtotal = cantidad * precio;
            
            const insumoSelector = row.querySelector('.insumo-selector');
            const insumoNombre = insumoSelector.options[insumoSelector.selectedIndex]?.text || 'Insumo';
            
            row.querySelector('.subtotal-item').value = formatearADinero(subtotal);
            costoMateriaPrima += subtotal;

            if (subtotal > 0) {
                detalleMateriaPrima.push(`${insumoNombre} (${formatearADinero(subtotal)})`);
            }
        });

        // Actualizar Tooltip de Materia Prima
        const tooltipMateriaPrima = document.getElementById('tooltip-materia-prima');
        if (tooltipMateriaPrima) {
            const nuevoTitulo = detalleMateriaPrima.length > 0 ? detalleMateriaPrima.join(' + ') : 'Sin insumos seleccionados';
            tooltipMateriaPrima.setAttribute('title', nuevoTitulo);
            bootstrap.Tooltip.getInstance(tooltipMateriaPrima)?.dispose();
            new bootstrap.Tooltip(tooltipMateriaPrima);
        }

        const costoManoObra = limpiarFormatoDinero(displayCostoManoObra.textContent);
        const costoFijos = limpiarFormatoDinero(displayCostoFijos.textContent);
        const costoTotalProduccion = costoMateriaPrima + costoManoObra + costoFijos;
        const porcentajeGanancia = parseFloat(porcentajeGananciaInput.value) || 0;
        let precioSinIva = costoTotalProduccion * (1 + (porcentajeGanancia / 100));

        if (ivaCheckbox.checked) {
            precioSinIva *= 1.21;
        }

        displayCostoMateriaPrima.textContent = formatearADinero(costoMateriaPrima);
        displayCostoTotalProduccion.textContent = formatearADinero(costoTotalProduccion);
        displayPrecioFinal.value = formatearADinero(precioSinIva);
    }

    async function actualizarCostosDinamicos() {
        const operaciones = [];
        operacionesContainer.querySelectorAll('.operacion-row').forEach(row => {
            const nombre = row.querySelector('input[name="operacion_nombre[]"]').value;
            const prep = row.querySelector('input[name="operacion_prep[]"]').value;
            const ejec = row.querySelector('input[name="operacion_ejec[]"]').value;
            const secuencia = row.querySelector('input[name="operacion_secuencia[]"]').value;
            
            // Recopilar roles y porcentajes
            const rolesSelect = row.querySelector('select[name^="operacion_roles"]');
            const rolesIds = Array.from(rolesSelect.selectedOptions).map(opt => parseInt(opt.value));
            const rolesData = [];
            
            rolesIds.forEach(id => {
                const pctInput = row.querySelector(`input[name="operacion_rol_pct_${secuencia}_${id}"]`);
                const pct = pctInput ? parseFloat(pctInput.value) || 100 : 100;
                rolesData.push({ rol_id: id, porcentaje_participacion: pct });
            });

            // Recopilar Costos Fijos
            const cfSelect = row.querySelector('select[name^="operacion_cf"]');
            const cfIds = Array.from(cfSelect.selectedOptions).map(opt => parseInt(opt.value));

            if (prep && ejec && rolesData.length > 0) {
                operaciones.push({
                    nombre_operacion: nombre,
                    tiempo_preparacion: parseFloat(prep),
                    tiempo_ejecucion_unitario: parseFloat(ejec),
                    roles: rolesData,
                    costos_fijos: cfIds
                });
            }
        });

        try {
            const response = await fetch('/api/catalogo/recalcular-costos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ operaciones: operaciones })
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    displayCostoManoObra.textContent = formatearADinero(result.data.costo_mano_obra);
                    displayCostoFijos.textContent = formatearADinero(result.data.costo_fijos_aplicado);
                    
                    const tooltipManoObra = document.getElementById('tooltip-mano-obra');
                    if (tooltipManoObra) {
                        tooltipManoObra.setAttribute('title', result.data.detalle_mano_obra || 'Calculando...');
                        bootstrap.Tooltip.getInstance(tooltipManoObra)?.dispose();
                        new bootstrap.Tooltip(tooltipManoObra);
                    }

                    const tooltipCostosFijos = document.getElementById('tooltip-costos-fijos');
                    if (tooltipCostosFijos) {
                        tooltipCostosFijos.setAttribute('title', result.data.detalle_costos_fijos || 'Calculando...');
                        bootstrap.Tooltip.getInstance(tooltipCostosFijos)?.dispose();
                        new bootstrap.Tooltip(tooltipCostosFijos);
                    }

                    calcularTotales();
                }
            }
        } catch (error) {
            console.error('Error al actualizar costos dinámicos:', error);
        }
    }

    itemsContainer.addEventListener('input', e => {
        if (e.target.classList.contains('cantidad')) {
            calcularTotales();
        }
    });

    itemsContainer.addEventListener('change', e => {
        if (e.target.classList.contains('insumo-selector')) {
            calcularTotales();
        }
    });
    
    porcentajeGananciaInput.addEventListener('input', calcularTotales);
    ivaCheckbox.addEventListener('change', calcularTotales);

    itemsContainer.addEventListener('click', e => {
        if (e.target.closest('.removeItemBtn')) {
            e.target.closest('.item-row').remove();
            calcularTotales();
        }
    });

    document.querySelectorAll('#itemsContainer .item-row').forEach(row => {
        updateUnitDisplay(row);
        const precioInput = row.querySelector('.precio_unitario');
        const subtotalInput = row.querySelector('.subtotal-item');
        precioInput.value = formatearADinero(limpiarFormatoDinero(precioInput.value));
        subtotalInput.value = formatearADinero(limpiarFormatoDinero(subtotalInput.value));
    });

    // Renderizar los pasos fijos al inicio
    renderFixedSteps();
    calcularTotales();
    actualizarCostosDinamicos();

    formulario.addEventListener('submit', async function (event) {
        event.preventDefault();
        event.stopPropagation();
        
        let isValid = true;
        let firstInvalidInput = null;

        // Validaciones personalizadas
        operacionesContainer.querySelectorAll('.operacion-row').forEach((row, index) => {
            const prepInput = row.querySelector('input[name="operacion_prep[]"]');
            const ejecInput = row.querySelector('input[name="operacion_ejec[]"]');
            const rolesSelect = row.querySelector('select[name^="operacion_roles"]');
            const roles = Array.from(rolesSelect.selectedOptions);

            const prepVal = parseFloat(prepInput.value);
            const ejecVal = parseFloat(ejecInput.value);

            if (roles.length === 0) {
                isValid = false;
            }

            if (isNaN(prepVal) || prepVal <= 0 || prepVal > 120) {
                prepInput.classList.add('is-invalid');
                isValid = false;
                if (!firstInvalidInput) firstInvalidInput = prepInput;
            } else {
                prepInput.classList.remove('is-invalid');
            }

            if (isNaN(ejecVal) || ejecVal <= 0 || ejecVal > 120) {
                ejecInput.classList.add('is-invalid');
                isValid = false;
                if (!firstInvalidInput) firstInvalidInput = ejecInput;
            } else {
                ejecInput.classList.remove('is-invalid');
            }
        });

        if (!formulario.checkValidity() || !isValid) {
            formulario.classList.add('was-validated');
            if (firstInvalidInput) firstInvalidInput.focus();
            if (!isValid) {
                showNotificationModal('Error de Validación', 'Verifique los pasos de producción:\n- Todos los tiempos deben ser mayores a 0 y hasta 120 minutos.\n- Debe asignar al menos un rol por paso.', 'warning');
            }
            return;
        }

        // Show loading state
        const submitButton = formulario.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.innerHTML;
        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Procesando...';

        const formData = new FormData(formulario);
        
        const productoData = {
            codigo: formData.get('codigo'),
            nombre: formData.get('nombre'),
            categoria: formData.get('categoria'),
            unidad_medida: formData.get('unidad_medida'),
            descripcion: formData.get('descripcion'),
            porcentaje_ganancia: formData.get('porcentaje_ganancia'),
            iva: formData.get('iva') === '1',
            precio_unitario: limpiarFormatoDinero(displayPrecioFinal.value) || 0,
            vida_util_dias: formData.get('vida_util_dias'),
            receta_items: [],
            operaciones: []
        };

        operacionesContainer.querySelectorAll('.operacion-row').forEach(row => {
            const nombre = row.querySelector('input[name="operacion_nombre[]"]').value;
            const prep = row.querySelector('input[name="operacion_prep[]"]').value;
            const ejec = row.querySelector('input[name="operacion_ejec[]"]').value;
            const secuencia = row.querySelector('input[name="operacion_secuencia[]"]').value;
            
            // Roles y Porcentajes
            const rolesSelect = row.querySelector('select[name^="operacion_roles"]');
            const rolesIds = Array.from(rolesSelect.selectedOptions).map(opt => parseInt(opt.value));
            const rolesData = [];
            rolesIds.forEach(id => {
                const pctInput = row.querySelector(`input[name="operacion_rol_pct_${secuencia}_${id}"]`);
                rolesData.push({
                    rol_id: id,
                    porcentaje_participacion: pctInput ? parseFloat(pctInput.value) : 100
                });
            });

            // Costos Fijos
            const cfSelect = row.querySelector('select[name^="operacion_cf"]');
            const cfIds = Array.from(cfSelect.selectedOptions).map(opt => parseInt(opt.value));
            
            productoData.operaciones.push({
                nombre_operacion: nombre,
                tiempo_preparacion: parseFloat(prep),
                tiempo_ejecucion_unitario: parseFloat(ejec),
                secuencia: parseInt(secuencia),
                roles: rolesData,
                costos_fijos: cfIds
            });
        });

        itemsContainer.querySelectorAll('.item-row').forEach(row => {
            const insumoId = row.querySelector('.insumo-selector').value;
            const cantidad = parseFloat(row.querySelector('.cantidad').value);
            const unidad = row.querySelector('.insumo-selector').selectedOptions[0].dataset.unidad;
            if (insumoId && cantidad) {
                productoData.receta_items.push({ id_insumo: insumoId, cantidad, unidad_medida: unidad });
            }
        });

        if (productoData.receta_items.length === 0) {
            showNotificationModal('Receta Vacía', 'Debe especificar al menos un ingrediente para la receta.', 'warning');
            submitButton.disabled = false;
            submitButton.innerHTML = originalButtonText;
            return;
        }

        const url = isEditBoolean ? `/catalogo/actualizar/${ID_producto}` : '/catalogo/nuevo';
        const method = isEditBoolean ? 'PUT' : 'POST';

        try {
            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(productoData)
            });
            const result = await response.json();

            if (response.ok && result.success) {
                showNotificationModal('Operación exitosa', isEditBoolean ? 'Producto actualizado.' : 'Producto creado.', 'success');
                setTimeout(() => { window.location.href = productoS_LISTA_URL; }, 1500);
            } else {
                submitButton.disabled = false;
                submitButton.innerHTML = originalButtonText;
                const errorMessage = result.error ? (typeof result.error === 'object' ? Object.values(result.error).flat().join('\n') : result.error) : 'Ocurrió un error.';
                showNotificationModal('Error al guardar', errorMessage, 'error');
            }
        } catch (error) {
            submitButton.disabled = false;
            submitButton.innerHTML = originalButtonText;
            showNotificationModal('Error de Conexión', 'No se pudo conectar con el servidor.', 'error');
        }
    });
});
