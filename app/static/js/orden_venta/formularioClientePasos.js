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
    const nombreInput = document.getElementById('nombre');
    const telefonoInput = document.getElementById('telefono');
    const condicionIvaDisplay = document.getElementById('condicion_iva_display');
    const condicionIvaValue = document.getElementById('condicion_iva_value');
    const tipoFacturaInput = document.getElementById('tipo_factura');

    // --- REFERENCIAS DE DIRECCIÓN ---
    const toggleDireccionEntregaBtn = document.getElementById('toggleDireccionEntregaBtn');
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
    const buildPayload = window.buildPayload || (() => { console.error("BuildPayload no definida."); return { items: [] }; });
    const updateResumen = window.updateResumen || window.calculateOrderTotals || (() => { });
    const addItemRow = window.addItemRow || (() => {
        console.error("Error FATAL: addItemRow no está definida en window. Debe corregir formularioVenta.js.");
        showNotificationModal('Error de Carga', 'No se pudo cargar la función de añadir productos. Revise formularioVenta.js.', 'error');
    });
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

    cuilCuitInput.addEventListener('input', function (e) {
        let value = e.target.value.replace(/\D/g, '');
        if (value.length > 2) value = value.substring(0, 2) + '-' + value.substring(2);
        if (value.length > 11) value = value.substring(0, 11) + '-' + value.substring(11);
        e.target.value = value.substring(0, 13);
        checkStep1Validity();
    });

    buscarClienteBtn.addEventListener('click', buscarClienteSeguro);

    async function buscarClienteSeguro() {
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
                const cliente = result.data;
                rellenarDatosCliente(cliente);
                clienteMessage.textContent = `¡Datos de ${cliente.nombre || cliente.razon_social} precargados con éxito!`;
                clienteMessage.className = 'form-text mt-1 text-success';

                datosClienteCard.style.display = 'block';
                productosCard.style.display = 'block';
                resumenCalculos.style.display = 'block';

                checkStep1Validity();
                updateResumen();

            } else {
                limpiarDatosCliente(true);
                clienteMessage.textContent = result.error || 'Cliente no encontrado o credenciales incorrectas.';
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
    }

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

        let dirPrincipal = cliente.direccion;
        if (!dirPrincipal && cliente.direcciones && cliente.direcciones.length > 0) {
            dirPrincipal = cliente.direcciones.find(d => d.es_principal) || cliente.direcciones[0];
        }

        if (dirPrincipal) {
            // Rellenar campos de Facturación (ReadOnly)
            calleFacturacionInput.value = dirPrincipal.calle || '';
            alturaFacturacionInput.value = dirPrincipal.altura || '';
            provinciaFacturacionInput.value = dirPrincipal.provincia || '';
            localidadFacturacionInput.value = dirPrincipal.localidad || '';
            document.getElementById('piso_facturacion').value = dirPrincipal.piso || '';
            document.getElementById('depto_facturacion').value = dirPrincipal.depto || '';
            cpFacturacionInput.value = dirPrincipal.codigo_postal || '';

            idDireccionEntregaInput.value = dirPrincipal.id;
            idDireccionEntregaInput.dataset.facturacionId = dirPrincipal.id;
        } else {
            idDireccionEntregaInput.value = '';
            idDireccionEntregaInput.dataset.facturacionId = '';
        }

        // Asegurarse de volver al estado inicial (usando dirección de facturación)
        isUsingAlternativeAddress = true;
        toggleDireccionEntregaBtn.click();
    }

    function limpiarDatosCliente(shouldResetAddress = true) {

        idClienteInput.value = '';
        nombreInput.value = '';
        telefonoInput.value = '';
        condicionIvaDisplay.value = '';
        condicionIvaValue.value = '';
        tipoFacturaInput.value = '';

        limpiarCamposDireccion();
        idDireccionEntregaInput.value = '';
        idDireccionEntregaInput.dataset.facturacionId = '';

        if (shouldResetAddress) {
            isUsingAlternativeAddress = true;
            toggleDireccionEntregaBtn.click();
        }

        datosClienteCard.style.display = 'none';
        productosCard.style.display = 'none';
        resumenCalculos.style.display = 'none';

        // Limpiar productos
        itemsContainer.innerHTML = '';
        document.getElementById('id_items-TOTAL_FORMS').value = 0;
        updateResumen();
    }


    // --- LÓGICA DE TOGGLE DE DIRECCIÓN ---

    toggleDireccionEntregaBtn.addEventListener('click', function () {
        isUsingAlternativeAddress = !isUsingAlternativeAddress;

        if (isUsingAlternativeAddress) {
            // MOSTRAR DIRECCIÓN ALTERNATIVA
            facturacionAddressFields.style.display = 'none';
            direccionEntregaAlternativaContainer.style.display = 'block';
            toggleDireccionEntregaBtn.innerHTML = '<i class="bi bi-house-door-fill me-1"></i> Usar Dirección de Facturación';
            toggleDireccionEntregaBtn.classList.remove('btn-outline-info');
            toggleDireccionEntregaBtn.classList.add('btn-outline-secondary');

            idDireccionEntregaInput.value = '';

            setRequiredAttribute(calleAlternativaInput, true);
            setRequiredAttribute(alturaAlternativaInput, true);
            setRequiredAttribute(provinciaAlternativaInput, true);
            setRequiredAttribute(localidadAlternativaInput, true);
            setRequiredAttribute(cpAlternativaInput, true);

        } else {
            // MOSTRAR DIRECCIÓN DE FACTURACIÓN
            facturacionAddressFields.style.display = 'block';
            direccionEntregaAlternativaContainer.style.display = 'none';
            toggleDireccionEntregaBtn.innerHTML = '<i class="bi bi-truck me-1"></i> Usar otra dirección de entrega';
            toggleDireccionEntregaBtn.classList.remove('btn-outline-secondary');
            toggleDireccionEntregaBtn.classList.add('btn-outline-info');

            idDireccionEntregaInput.value = idDireccionEntregaInput.dataset.facturacionId || '';

            setRequiredAttribute(calleAlternativaInput, false);
            setRequiredAttribute(alturaAlternativaInput, false);
            setRequiredAttribute(provinciaAlternativaInput, false);
            setRequiredAttribute(localidadAlternativaInput, false);
            setRequiredAttribute(cpAlternativaInput, false);
        }
        checkStep1Validity();
    });

    // --- LÓGICA DE VALIDACIÓN DEL PASO 1 ---

    function checkStep1Validity() {

        const isClientSelected = idClienteInput.value.length > 0;
        const hasItems = itemsContainer.querySelectorAll('.item-row').length > 0;
        // Solo valida los campos visibles y con atributo required
        const isFormValid = form.checkValidity();

        let isAddressValid = false;

        if (!isClientSelected) {
            isAddressValid = false;
        } else if (!isUsingAlternativeAddress) {
            isAddressValid = !!idDireccionEntregaInput.value; // Debe haber un ID de dirección de facturación
        } else {
            // Si está usando la alternativa, debe estar llena
            isAddressValid = (
                calleAlternativaInput.value.trim() &&
                alturaAlternativaInput.value.trim() &&
                provinciaAlternativaInput.value.trim() &&
                localidadAlternativaInput.value.trim() &&
                cpAlternativaInput.value.trim() &&
                isFormValid // Usa la validación HTML5 para la alternativa
            );
        }

        const isValid = isClientSelected && hasItems && isFormValid && isAddressValid;
        nextStep1Btn.disabled = !isValid;

        // AÑADIR ESTA LÍNEA PARA FORZAR EL RECÁLCULO
        if (isClientSelected && hasItems) { // Opcional: solo calcular si hay cliente y ítems
            updateResumen(); // Llama a window.calculateOrderTotals
        }

        return isValid;
    }

    // Escucha cambios en los campos y la tabla de productos
    form.addEventListener('input', checkStep1Validity);
    form.addEventListener('change', checkStep1Validity);
    itemsContainer.addEventListener('DOMSubtreeModified', checkStep1Validity);

    // Asignación de event listeners de acción
    nextStep1Btn.addEventListener('click', (e) => { e.preventDefault(); goToStep(2); });
    prevStep2Btn.addEventListener('click', () => goToStep(1));
    addItemBtn.addEventListener('click', addItemRow); // LLAMADA CORREGIDA

    cancelOrderBtn.addEventListener('click', () => {
        showNotificationModal(
            'Pedido Cancelado',
            'El proceso de pedido fue cancelado y no se guardó.',
            'warning',
            () => { window.location.href = LISTAR_URL; }
        );
    });

    // --- LÓGICA DE NAVEGACIÓN DE PASOS Y ENVÍO FINAL (loadProforma y submit) ---

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
                showNotificationModal('Validación Pendiente', 'Complete la identificación, la dirección y añada al menos un producto al pedido.', 'warning');
                return;
            }

            const payload = buildPayload();
            if (!payload || payload.items.length === 0) {
                showNotificationModal('Error', 'Debe haber al menos un producto en la lista.', 'warning');
                return;
            }
            pedidoDataTemp.value = JSON.stringify(payload);

            step1Content.style.display = 'none';
            step2Content.style.display = 'block';
            step1Actions.style.display = 'none';
            step1Indicator.classList.remove('active');
            step1Indicator.classList.add('completed');
            step2Indicator.classList.add('active');

            loadProforma();
        }
    }


    async function loadProforma() {
        const payloadString = pedidoDataTemp.value;
        if (!payloadString) {
            proformaContent.innerHTML = '<p class="text-danger">Error: No se encontró la data temporal del pedido.</p>';
            acceptOrderBtn.disabled = true;
            return;
        }

        proformaContent.innerHTML = `<div class="p-5"><span class="spinner-border text-primary"></span><p class="text-muted mt-3">Generando factura proforma...</p></div>`;
        acceptOrderBtn.disabled = true;

        try {
            const tempPayload = JSON.parse(payloadString);
            const tempClienteId = tempPayload.id_cliente || 0;

            const urlApi = PROFORMA_API_URL.replace('/0/generar_factura_html', `/${tempClienteId}/generar_factura_html`);

            const response = await fetch(urlApi, { method: 'GET' });
            const result = await response.json();

            if (response.ok && result.success && result.html) {
                proformaContent.innerHTML = result.html;
                acceptOrderBtn.disabled = false;
            } else {
                proformaContent.innerHTML = `<div class="p-5"><p class="text-danger"><i class="bi bi-x-circle me-1"></i>Error al generar la proforma: ${result.error || 'Fallo de API.'}</p></div>`;
            }

        } catch (error) {
            console.error('Error al cargar proforma:', error);
            proformaContent.innerHTML = '<div class="p-5"><p class="text-danger"><i class="bi bi-plug me-1"></i>Error de red al conectar con el servidor.</p></div>';
        }
    }

    form.addEventListener('submit', async function (e) {
        e.preventDefault();

        if (acceptOrderBtn.disabled) return;

        const payload = JSON.parse(pedidoDataTemp.value);

        acceptOrderBtn.disabled = true;
        const originalHtml = acceptOrderBtn.innerHTML;
        acceptOrderBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Creando Pedido...';

        try {
            const response = await fetch(CREAR_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            const result = await response.json();

            if (response.ok && result.success) {
                showNotificationModal(
                    'Pedido Creado',
                    result.message || 'La orden de venta ha sido registrada.',
                    'success',
                    () => { window.location.href = LISTAR_URL; }
                );
            } else {
                showNotificationModal(
                    'Error de Creación',
                    result.message || result.error || 'No se pudo crear la orden.',
                    'error'
                );
            }
        } catch (error) {
            showNotificationModal(
                'Error de Conexión',
                'Fallo de red al intentar crear la orden.',
                'error'
            );
        } finally {
            acceptOrderBtn.disabled = false;
            acceptOrderBtn.innerHTML = originalHtml;
        }
    });

    // --- Inicialización ---
    // Agrega una fila inicial si el contenedor está vacío.
    if (itemsContainer.children.length === 0) {
        addItemRow();
    }

    // Ejecutar cálculo inicial para productos precargados o la fila recién añadida.
    updateResumen(); // LLAMADA CLAVE: Asegura que la fila inicial tenga sus valores.

    // Establecer el estado inicial de la dirección (Muestra Facturación por defecto)
    // El 'click' en el botón llama a checkStep1Validity() lo que también dispara updateResumen().
    toggleDireccionEntregaBtn.click();
});