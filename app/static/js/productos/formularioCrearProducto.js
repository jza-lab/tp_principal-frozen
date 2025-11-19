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

    // --- LÓGICA DE MANO DE OBRA ---
    const manoDeObraContainer = document.getElementById('mano-obra-container');
    const addManoObraBtn = document.getElementById('add-mano-obra-btn');

    function agregarFilaManoDeObra() {
        const row = document.createElement('div');
        row.className = 'row g-3 align-items-end item-row mb-2';
        
        let options = '<option value="">Seleccione un rol...</option>';
        rolesData.forEach(rol => {
            options += `<option value="${rol.id}">${rol.nombre}</option>`;
        });

        row.innerHTML = `
            <div class="col-md-5">
                <label class="form-label">Rol</label>
                <select class="form-select mano-obra-rol" name="mano_obra_rol_id[]" required>
                    ${options}
                </select>
            </div>
            <div class="col-md-4">
                <label class="form-label">Horas Estimadas</label>
                <input type="number" step="0.25" min="0.25" class="form-control mano-obra-horas" name="mano_obra_horas[]" required>
            </div>
            <div class="col-md-3">
                <button type="button" class="btn btn-outline-danger remove-mano-obra-btn">Eliminar</button>
            </div>
        `;
        manoDeObraContainer.appendChild(row);
    }

    addManoObraBtn.addEventListener('click', agregarFilaManoDeObra);

    manoDeObraContainer.addEventListener('click', function(e) {
        if (e.target.closest('.remove-mano-obra-btn')) {
            e.target.closest('.item-row').remove();
            actualizarCostosDinamicos();
        }
    });

    manoDeObraContainer.addEventListener('input', function(e) {
        if (e.target.classList.contains('mano-obra-horas') || e.target.classList.contains('mano-obra-rol')) {
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

        // Comprueba si el string contiene una coma para decidir el tipo de parseo.
        if (valorStr.includes(',')) {
            // Asume formato de moneda local (ej: '$ 1.234,56')
            // Elimina el símbolo de peso, los separadores de miles (punto) y reemplaza la coma decimal por un punto.
            const cleanString = valorStr.replace(/[$.]/g, '').replace(/[^\d,]/g, '').replace(',', '.');
            return parseFloat(cleanString) || 0;
        } else {
            // Asume formato de número estándar (ej: '1234.56')
            // Simplemente elimina cualquier caracter que no sea un dígito o un punto.
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
        itemsContainer.querySelectorAll('.item-row').forEach(row => {
            const precio = limpiarFormatoDinero(row.querySelector('.precio_unitario').value);
            const cantidad = parseFloat(row.querySelector('.cantidad').value) || 0;
            const subtotal = cantidad * precio;
            row.querySelector('.subtotal-item').value = formatearADinero(subtotal);
            costoMateriaPrima += subtotal;
        });

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
        const manoDeObraItems = [];
        manoDeObraContainer.querySelectorAll('.item-row').forEach(row => {
            const rolId = row.querySelector('.mano-obra-rol').value;
            const horas = row.querySelector('.mano-obra-horas').value;
            if (rolId && horas) {
                manoDeObraItems.push({ rol_id: rolId, horas_estimadas: horas });
            }
        });

        try {
            const response = await fetch('/api/catalogo/recalcular-costos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mano_de_obra: manoDeObraItems })
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    displayCostoManoObra.textContent = formatearADinero(result.data.costo_mano_obra);
                    displayCostoFijos.textContent = formatearADinero(result.data.costo_fijos_aplicado);
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

    calcularTotales();
    actualizarCostosDinamicos();

    form.addEventListener('submit', async function (event) {
        event.preventDefault();
        event.stopPropagation();
        
        if (!form.checkValidity()) {
            form.classList.add('was-validated');
            return;
        }

        const formData = new FormData(form);
        const lineaCompatibleStr = document.querySelector('input[name="linea_compatible"]:checked')?.value || '2';

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
            mano_de_obra: []
        };

        manoDeObraContainer.querySelectorAll('.item-row').forEach(row => {
            const rolId = row.querySelector('.mano-obra-rol').value;
            const horas = row.querySelector('.mano-obra-horas').value;
            if (rolId && horas) {
                productoData.mano_de_obra.push({
                    rol_id: parseInt(rolId),
                    horas_estimadas: parseFloat(horas)
                });
            }
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
                const errorMessage = result.error ? (typeof result.error === 'object' ? Object.values(result.error).flat().join('\n') : result.error) : 'Ocurrió un error.';
                showNotificationModal('Error al guardar', errorMessage, 'error');
            }
        } catch (error) {
            showNotificationModal('Error de Conexión', 'No se pudo conectar con el servidor.', 'error');
        }
    });
});
