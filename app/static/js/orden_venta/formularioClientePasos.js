// app/static/js/orden_venta/formularioClientePasos.js

document.addEventListener('DOMContentLoaded', function () {
    // --- Referencias a elementos del DOM PRINCIPALES ---
    const form = document.getElementById('pedido-form');
    const step1Content = document.getElementById('step1Content');
    const step2Content = document.getElementById('step2Content');
    const step1Actions = document.getElementById('step1Actions');
    const nextStep1Btn = document.getElementById('nextStep1');
    const prevStep2Btn = document.getElementById('prevStep2');
    const acceptOrderBtn = document.getElementById('acceptOrderBtn');
    const cancelOrderBtn = document.getElementById('cancelOrderBtn');
    const proformaContent = document.getElementById('proforma-content');
    const step1Indicator = document.getElementById('step1');
    const step2Indicator = document.getElementById('step2');

    // Elementos de Identificación
    const cuilCuitInput = document.getElementById('cuil_cuit_cliente');
    const emailInput = document.getElementById('email_cliente');
    const buscarClienteBtn = document.getElementById('buscarClienteBtn');
    const searchSpinner = document.getElementById('searchSpinner');
    const clienteMessage = document.getElementById('clienteMessage');

    // Elementos de Datos del Cliente y Productos
    const datosClienteCard = document.getElementById('datosClienteCard');
    const productosCard = document.getElementById('productosCard');
    const resumenCalculos = document.getElementById('resumenCalculos');
    const idClienteInput = document.getElementById('id_cliente');
    const itemsContainer = document.getElementById('items-container');
    const addItemBtn = document.getElementById('addItemBtn');
    const fechaEntregaInput = document.getElementById('fecha_entrega');
    const pedidoDataTemp = document.getElementById('pedido_data_temp');

    // CAMPOS DE CLIENTE
    const nombreInput = document.getElementById('nombre_cliente');
    const telefonoInput = document.getElementById('telefono');
    const condicionIvaDisplay = document.getElementById('condicion_iva_display');
    const condicionIvaValue = document.getElementById('condicion_iva_value');
    const tipoFacturaInput = document.getElementById('tipo_factura');

    // --- REFERENCIAS DE DIRECCIÓN ---
    const toggleDireccionEntregaBtn = document.getElementById('usar_direccion_alternativa');
    const facturacionAddressFields = document.getElementById('facturacionAddressFields');
    const direccionEntregaAlternativaContainer = document.getElementById('direccionEntregaAlternativaContainer');
    const idDireccionEntregaInput = document.getElementById('id_direccion_entrega');

    // CAMPOS DE FACTURACIÓN (ReadOnly)
    const calleFacturacionInput = document.getElementById('calle_facturacion');
    const alturaFacturacionInput = document.getElementById('altura_facturacion');
    const provinciaFacturacionInput = document.getElementById('provincia_facturacion');
    const localidadFacturacionInput = document.getElementById('localidad_facturacion');
    const cpFacturacionInput = document.getElementById('codigo_postal_facturacion');

    // CAMPOS DE ALTERNATIVA (Editable)
    const calleAlternativaInput = document.getElementById('calle_alternativa');
    const alturaAlternativaInput = document.getElementById('altura_alternativa');
    const provinciaAlternativaInput = document.getElementById('provincia_alternativa');
    const localidadAlternativaInput = document.getElementById('localidad_alternativa');
    const cpAlternativaInput = document.getElementById('codigo_postal_alternativa');

    // --- MAPEO Y ESTADO ---

    // Funciones globales (capturadas con un fallback robusto)
    const updateResumen = window.calculateOrderTotals || (() => { });
    const addItemRow = window.addItemRow || (() => { showNotificationModal('Error de Carga', 'No se pudo cargar la función para añadir productos.', 'error'); });
    const showNotificationModal = window.showNotificationModal || alert;

    // Mapeo de Condición IVA
    const CONDICION_IVA_MAP = {
        '1': { text: 'Responsable Inscripto', factura: 'A' },
        '2': { text: 'Monotributista', factura: 'B' },
        '3': { text: 'IVA Exento', factura: 'B' },
        '4': { text: 'Consumidor Final', factura: 'B' },
    };

    let isUsingAlternativeAddress = false;

    // --- LÓGICA DE BÚSQUEDA DE CLIENTE SEGURA ---

    function buildClientOrderPayload() {
        const getAddressData = (prefix) => ({
            calle: document.getElementById(`calle_${prefix}`).value,
            altura: document.getElementById(`altura_${prefix}`).value,
            piso: document.getElementById(`piso_${prefix}`).value || null,
            depto: document.getElementById(`depto_${prefix}`).value || null,
            localidad: document.getElementById(`localidad_${prefix}`).value,
            provincia: document.getElementById(`provincia_${prefix}`).value,
            codigo_postal: document.getElementById(`codigo_postal_${prefix}`).value
        });

        const payload = {
            id_cliente: parseInt(idClienteInput.value, 10),
            fecha_entrega: document.getElementById('fecha_entrega').value,
            items: [],
            direccion_entrega: isUsingAlternativeAddress ? getAddressData('alternativa') : getAddressData('facturacion'),
            usar_direccion_alternativa: isUsingAlternativeAddress,
            id_direccion_entrega: isUsingAlternativeAddress ? null : idDireccionEntregaInput.value
        };

        document.querySelectorAll('#items-container .item-row').forEach(row => {
            const productoSelect = row.querySelector('.producto-selector');
            const cantidadInput = row.querySelector('.item-quantity');
            const precioUnitarioInput = row.querySelector('.item-price-unit-value');
            if (productoSelect && cantidadInput && precioUnitarioInput && productoSelect.value) {
                payload.items.push({
                    producto_id: parseInt(productoSelect.value, 10),
                    cantidad: parseFloat(cantidadInput.value) || 0,
                    precio_unitario: parseFloat(precioUnitarioInput.value) || 0
                });
            }
        });
        return payload;
    }

    // --- LÓGICA DE BÚSQUEDA DE CLIENTE ---
    cuilCuitInput.addEventListener('input', function (e) {
        let value = e.target.value.replace(/\D/g, '');
        if (value.length > 2) value = value.substring(0, 2) + '-' + value.substring(2);
        if (value.length > 11) value = value.substring(0, 11) + '-' + value.substring(11);
        e.target.value = value.substring(0, 13);
        checkStep1Validity();
    });

    buscarClienteBtn.addEventListener('click', async function () {
        const cuil = cuilCuitInput.value;
        const email = emailInput.value;

        if (cuil.length !== 13 || !email) {
            showNotificationModal('Advertencia', 'Ingrese un CUIL/CUIT de 11 dígitos y un Email válidos.', 'warning');
            return;
        }

        buscarClienteBtn.disabled = true;
        searchSpinner.style.display = 'inline-block';
        clienteMessage.textContent = 'Buscando cliente...';
        clienteMessage.className = 'form-text mt-1 text-muted';

        limpiarDatosCliente(false);

        try {
            const response = await fetch(CLIENTE_API_SEARCH_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cuil: cuil, email: email })
            });

            const result = await response.json();

            if (response.ok && result.success) {

                rellenarDatosCliente(result.data);
                clienteMessage.textContent = `¡Datos de ${result.data.nombre || result.data.razon_social} precargados!`;
                clienteMessage.className = 'form-text mt-1 text-success';

                [datosClienteCard, productosCard, resumenCalculos].forEach(el => el.style.display = 'block');

                checkStep1Validity();
                updateResumen();

            } else {
                limpiarDatosCliente(true);
                clienteMessage.textContent = result.error || 'Cliente no encontrado.';
                clienteMessage.className = 'form-text mt-1 text-danger';
            }

        } catch (error) {
            console.error('Error en la búsqueda:', error);
            limpiarDatosCliente(true);
            clienteMessage.textContent = 'Error de conexión con el servidor.';
            clienteMessage.className = 'form-text mt-1 text-danger';
        } finally {
            buscarClienteBtn.disabled = false;
            searchSpinner.style.display = 'none';
        }
    })

    // Función auxiliar para establecer/quitar el atributo 'required'
    function setRequiredAttribute(element, isRequired) {
        if (isRequired) {
            element.setAttribute('required', 'required');
        } else {
            element.removeAttribute('required');
        }
    }

    function limpiarCamposDireccion() {
        [calleFacturacionInput, alturaFacturacionInput, provinciaFacturacionInput, localidadFacturacionInput, cpFacturacionInput, document.getElementById('piso_facturacion'), document.getElementById('depto_facturacion')].forEach(input => input.value = '');
        [calleAlternativaInput, alturaAlternativaInput, provinciaAlternativaInput, localidadAlternativaInput, cpAlternativaInput, document.getElementById('piso_alternativa'), document.getElementById('depto_alternativa')].forEach(input => { input.value = ''; input.classList.remove('is-invalid', 'is-valid'); });
    }



    function rellenarDatosCliente(cliente) {

        idClienteInput.value = cliente.id;
        nombreInput.value = cliente.nombre || cliente.razon_social || '';
        telefonoInput.value = cliente.telefono || '';

        // Mapeo de Condición IVA 
        const ivaCode = String(cliente.condicion_iva);
        const ivaData = CONDICION_IVA_MAP[ivaCode] || { text: 'N/A', factura: 'B' };

        condicionIvaDisplay.value = ivaData.text;
        condicionIvaValue.value = ivaCode;
        tipoFacturaInput.value = ivaData.factura;

        // --- Lógica de Dirección Detallada (Facturación) ---
        limpiarCamposDireccion();

        let dirPrincipal = cliente.direccion || (cliente.direcciones && (cliente.direcciones.find(d => d.es_principal) || cliente.direcciones[0]));
        if (!dirPrincipal && cliente.direcciones && cliente.direcciones.length > 0) {
            dirPrincipal = cliente.direcciones.find(d => d.es_principal) || cliente.direcciones[0];
        }

        if (dirPrincipal) {
            // Rellenar campos de Facturación (ReadOnly)
            Object.keys(dirPrincipal).forEach(key => {
                const el = document.getElementById(`${key}_facturacion`);
                if (el) el.value = dirPrincipal[key] || '';
            });
            idDireccionEntregaInput.value = dirPrincipal.id;
            idDireccionEntregaInput.dataset.facturacionId = dirPrincipal.id;
        }
        isUsingAlternativeAddress = true;
        toggleDireccionEntregaBtn.click();
    }

    function limpiarDatosCliente(shouldResetAddress = true) {

        idDireccionEntregaInput.dataset.facturacionId = '';
        [idClienteInput, nombreInput, telefonoInput, condicionIvaDisplay, condicionIvaValue, tipoFacturaInput, idDireccionEntregaInput].forEach(el => el.value = '');

        if (shouldResetAddress) {
            isUsingAlternativeAddress = true;
            toggleDireccionEntregaBtn.click();
        }

        [datosClienteCard, productosCard, resumenCalculos].forEach(el => el.style.display = 'none');
        itemsContainer.innerHTML = '';
        document.getElementById('id_items-TOTAL_FORMS').value = 0;
        updateResumen();
    }


    // --- LÓGICA DE TOGGLE DE DIRECCIÓN ---

    toggleDireccionEntregaBtn.addEventListener('click', function () {
        isUsingAlternativeAddress = !isUsingAlternativeAddress;
        facturacionAddressFields.style.display = isUsingAlternativeAddress ? 'none' : 'block';
        direccionEntregaAlternativaContainer.style.display = isUsingAlternativeAddress ? 'block' : 'none';
        toggleDireccionEntregaBtn.innerHTML = isUsingAlternativeAddress ? '<i class="bi bi-house-door-fill me-1"></i> Usar Dirección de Facturación' : '<i class="bi bi-truck me-1"></i> Usar otra dirección';
        idDireccionEntregaInput.value = isUsingAlternativeAddress ? '' : (idDireccionEntregaInput.dataset.facturacionId || '');
        ['calle', 'altura', 'provincia', 'localidad', 'codigo_postal'].forEach(f => {
            document.getElementById(`${f}_alternativa`).required = isUsingAlternativeAddress;
        });
        checkStep1Validity();
    });

    // --- LÓGICA DE VALIDACIÓN DEL PASO 1 ---

    function checkStep1Validity() {

        const isClientSelected = !!idClienteInput.value;
        const hasItems = itemsContainer.querySelectorAll('.item-row').length > 0;
        const isFormValid = form.checkValidity();

        const isValid = isClientSelected && hasItems && isFormValid;
        nextStep1Btn.disabled = !isValid;
        return isValid;
    }

    [form, itemsContainer].forEach(el => ['input', 'change', 'DOMSubtreeModified'].forEach(evt => el.addEventListener(evt, checkStep1Validity)));


    nextStep1Btn.addEventListener('click', (e) => { e.preventDefault(); goToStep(2); });
    prevStep2Btn.addEventListener('click', () => goToStep(1));

    addItemBtn.addEventListener('click', addItemRow);
    cancelOrderBtn.addEventListener('click', () => { showNotificationModal('Pedido Cancelado', 'El proceso fue cancelado.', 'warning', () => { window.location.href = LISTAR_URL; }); });

    function goToStep(step) {
        if (step === 1) {
            step1Content.style.display = 'block';
            step2Content.style.display = 'none';
            step1Actions.style.display = 'flex';
            step1Indicator.classList.add('active');
            step1Indicator.classList.remove('completed');
            step2Indicator.classList.remove('active');
        } else if (step === 2) {
            if (!checkStep1Validity()) {
                showNotificationModal('Validación Pendiente', 'Complete todos los campos requeridos y añada al menos un producto.', 'warning');
                return;
            }

            const payload = buildPayload();
            if (!payload || payload.items.length === 0) {
                showNotificationModal('Error', 'Debe haber al menos un producto.', 'warning');
                return;
            }
            pedidoDataTemp.value = JSON.stringify(payload);

            step1Content.style.display = 'none';
            step2Content.style.display = 'block';
            step1Actions.style.display = 'none';
            step1Indicator.classList.add('completed');
            step2Indicator.classList.add('active');
            loadProforma();
        }
    }

    async function loadProforma() {
        const payloadString = pedidoDataTemp.value;
        if (!payloadString) {
            proformaContent.innerHTML = '<p class="text-danger">Error: No se encontró la data del pedido.</p>';
            return;
        }

        proformaContent.innerHTML = `<div class="p-5"><span class="spinner-border text-primary"></span><p class="text-muted mt-3">Generando factura proforma...</p></div>`;
        acceptOrderBtn.disabled = true;

        try {
            const response = await fetch(PROFORMA_GENERATION_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: payloadString
            });
            const result = await response.json();

            if (response.ok && result.success) {
                proformaContent.innerHTML = result.html;
                acceptOrderBtn.disabled = false;
            } else {
                proformaContent.innerHTML = `<div class="p-5 text-center"><p class="text-danger"><i class="bi bi-x-circle me-1"></i>Error: ${result.error || 'Fallo de API.'}</p></div>`;
            }

        } catch (error) {
            proformaContent.innerHTML = '<div class="p-5 text-center"><p class="text-danger"><i class="bi bi-plug me-1"></i>Error de red.</p></div>';
        }
    }

    form.addEventListener('submit', async function (e) {
        e.preventDefault();

        if (acceptOrderBtn.disabled) return;

        acceptOrderBtn.disabled = true;
        acceptOrderBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Creando Pedido...';

        try {
            const response = await fetch(CREAR_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: pedidoDataTemp.value,
            });

            const result = await response.json();

            if (response.ok && result.success) {
                showNotificationModal('Pedido Creado', result.message || 'La orden ha sido registrada.', 'success', () => { window.location.href = LISTAR_URL; });
            } else {
                showNotificationModal('Error', result.message || result.error || 'No se pudo crear la orden.', 'error');
                acceptOrderBtn.disabled = false;
                acceptOrderBtn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Aceptar y Crear Pedido';
            }

        } catch (error) {
            showNotificationModal('Error de Conexión', 'Fallo de red al crear la orden.', 'error');
            acceptOrderBtn.disabled = false;
            acceptOrderBtn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Aceptar y Crear Pedido';
        }

    });

    if (itemsContainer.children.length === 0) { } addItemRow();
    updateResumen();
    checkStep1Validity();
    toggleDireccionEntregaBtn.click();
});