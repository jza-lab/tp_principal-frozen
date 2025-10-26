// app/static/js/orden_venta/formularioClientePasos.js

document.addEventListener('DOMContentLoaded', function () {
    // --- Referencias a elementos del DOM PRINCIPALES ---
    const form = document.getElementById('pedido-form');
    const step1Content = document.getElementById('step1Content');
    const step2Content = document.getElementById('step2Content');
    const step3Content = document.getElementById('step3Content');
    const step4Content = document.getElementById('step4Content');
    const resultIcon = document.getElementById('result-icon');
    const resultTitle = document.getElementById('result-title');
    const resultMessage = document.getElementById('result-message');
    const step1Actions = document.getElementById('step1Actions');
    const nextStep1Btn = document.getElementById('nextStep1');
    const prevStep2Btn = document.getElementById('prevStep2');
    const acceptOrderBtn = document.getElementById('acceptOrderBtn');
    const cancelOrderBtn = document.getElementById('cancelOrderBtn');
    const proformaContent = document.getElementById('proforma-content');
    const step1Indicator = document.getElementById('step1');
    const step2Indicator = document.getElementById('step2');
    const step3Indicator = document.getElementById('step3');

    // --- Elementos del Paso 3: Pago (Simulación) ---
    const paymentStepContent = document.getElementById('paymentStepContent');
    const paymentConfirmBtn = document.getElementById('paymentConfirmBtn');
    const paymentTotalAmount = document.getElementById('paymentTotalAmount');
    const prevStep3Btn = document.getElementById('prevStep3');

    // --- Elementos del Paso 4: Confirmación Final ---
    const confirmationStepContent = document.getElementById('confirmationStepContent');
    const paymentReceipt = document.getElementById('paymentReceipt');
    const downloadReceiptBtn = document.getElementById('downloadReceiptBtn');
    const newOrderBtn = document.getElementById('newOrderBtn');

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
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            const response = await fetch(CLIENTE_API_SEARCH_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ cuil: cuil, email: email })
            });

            const result = await response.json();

            if (response.ok && result.success) {

                rellenarDatosCliente(result.data);
                clienteMessage.textContent = `¡Datos de ${result.data.nombre || result.data.razon_social} precargados!`;
                clienteMessage.className = 'form-text mt-1 text-success';

                [datosClienteCard, productosCard, resumenCalculos].forEach(el => el.style.display = 'block');

                nextStep1Btn.disabled = false;
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
        this.dataset.active = isUsingAlternativeAddress;
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

        return isClientSelected && hasItems && isFormValid;
    }

    [form, itemsContainer].forEach(el => ['input', 'change', 'DOMSubtreeModified'].forEach(evt => el.addEventListener(evt, checkStep1Validity)));


    nextStep1Btn.addEventListener('click', (e) => { e.preventDefault(); goToStep(2); });
    prevStep2Btn.addEventListener('click', () => goToStep(1));

    addItemBtn.addEventListener('click', addItemRow);
    cancelOrderBtn.addEventListener('click', () => { showNotificationModal('Pedido Cancelado', 'El proceso fue cancelado.', 'warning', () => { window.location.href = LISTAR_URL; }); });

    async function goToStep(step) {
        step1Content.style.display = 'none';
        step2Content.style.display = 'none';
        paymentStepContent.style.display = 'none';
        confirmationStepContent.style.display = 'none';
        step1Actions.style.display = 'none';
        if (step === 1) {
            step1Content.style.display = 'block';
            step1Actions.style.display = 'flex';
            step1Indicator.classList.add('active');
            step1Indicator.classList.remove('completed');
            step2Indicator.classList.remove('active', 'completed');
            step3Indicator.classList.remove('active', 'completed');
        } else if (step === 2) {
            if (!checkStep1Validity()) {
                showNotificationModal('Validación Pendiente', 'Complete todos los campos requeridos y añada al menos un producto.', 'warning');
                goToStep(1); // Forzar regreso
                return;
            }
            if (isUsingAlternativeAddress) {
                const direccion = {
                    calle: calleAlternativaInput.value,
                    altura: alturaAlternativaInput.value,
                    localidad: localidadAlternativaInput.value,
                    provincia: provinciaAlternativaInput.value,
                };

                const csrfToken = document.querySelector('input[name="csrf_token"]').value;
                const response = await fetch('/api/validar/direccion', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify(direccion)
                });
                const result = await response.json();

                if (!result.success) {
                    showNotificationModal('Dirección Inválida', result.message || 'La dirección de entrega alternativa no pudo ser validada.', 'error');
                    return; // Detener el avance si la dirección es inválida
                }
            }

            let cantidadEsInvalida = false;
            let productoInvalido = '';
            const itemRows = itemsContainer.querySelectorAll('.item-row');

            itemRows.forEach(row => {
                const productoSelect = row.querySelector('select[name*="producto_id"]');
                const cantidadInput = row.querySelector('input[name*="cantidad"]');

                if (productoSelect && cantidadInput && !cantidadEsInvalida) {
                    const selectedOption = productoSelect.options[productoSelect.selectedIndex];
                    const unidad = selectedOption ? selectedOption.dataset.unidad : '';
                    const cantidad = parseFloat(cantidadInput.value);
                    const requiereEntero = unidad.startsWith('paquete') || unidad === 'unidades';

                    if (requiereEntero && (cantidad % 1 !== 0)) {
                        cantidadEsInvalida = true;
                        productoInvalido = selectedOption.textContent.trim().split('(')[0].trim();
                        cantidadInput.focus();
                    }
                }
            });

            if (cantidadEsInvalida) {
                showNotificationModal(
                    'Error en la Cantidad',
                    `La cantidad para el producto "${productoInvalido}" debe ser un número entero (sin decimales), ya que se mide por unidades o paquetes.`,
                    'error'
                );
                return; // Detener el avance
            }

            if (isUsingAlternativeAddress) {
                const direccion = {
                    calle: calleAlternativaInput.value,
                    altura: alturaAlternativaInput.value,
                    localidad: localidadAlternativaInput.value,
                    provincia: provinciaAlternativaInput.value,
                };
                const csrfToken = document.querySelector('input[name="csrf_token"]').value;
                const response = await fetch('/api/validar/direccion', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify(direccion)
                });
                const result = await response.json();

                if (!result.success) {
                    showNotificationModal('Dirección Inválida', result.message || 'La dirección de entrega alternativa no pudo ser validada.', 'error');
                    return;
                }
            }

            const payload = buildPayload();
            if (!payload || payload.items.length === 0) {
                showNotificationModal('Error', 'Debe haber al menos un producto.', 'warning');
                return;
            }
            pedidoDataTemp.value = JSON.stringify(payload);
            step1Actions.style.display = 'none'
            nextStep1Btn.style.display = 'none'
            step2Content.style.display = 'block';
            step1Indicator.classList.add('completed');
            step2Indicator.classList.add('active');
            step3Indicator.classList.remove('active', 'completed');
            loadProforma();
        } else if (step === 3) {
            // Lógica para el paso de pago
            paymentStepContent.style.display = 'block';
            step2Indicator.classList.add('completed');
            step3Indicator.classList.add('active');
            const total = document.getElementById('total-final').textContent;
            paymentTotalAmount.textContent = total;
        } else if (step === 4) {
            // Lógica para la confirmación final
            confirmationStepContent.style.display = 'block';
            step3Indicator.classList.add('completed');
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
        const csrfToken = document.querySelector('input[name="csrf_token"]').value;
        try {
            const response = await fetch(PROFORMA_GENERATION_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
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

    acceptOrderBtn.addEventListener('click', async function () {
        const condicionVenta = document.getElementById('condicion_venta').value;

        if (condicionVenta === 'contado') {
            goToStep(3);
        } else {
            await submitOrder(false);
        }
    });

    paymentConfirmBtn.addEventListener('click', async () => {
        await submitOrder(true);
    });

    prevStep3Btn.addEventListener('click', () => {
        goToStep(2);
    });

    async function submitOrder(isPayment = false) {
        const createButton = isPayment ? paymentConfirmBtn : acceptOrderBtn;
        const originalButtonText = createButton.innerHTML;

        if (createButton.disabled) return;

        createButton.disabled = true;
        createButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';

        if (isPayment) {
            await new Promise(resolve => setTimeout(resolve, 1500)); // Simula espera de pasarela
        }
        const csrfToken = document.querySelector('input[name="csrf_token"]').value;

        try {
            const response = await fetch(CREAR_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: pedidoDataTemp.value,
            });

            const result = await response.json();

            if (result.success && result.data && result.data.id) {
                if (isPayment) {
                    const comprobanteUrl = `/public/comprobante-pago/${result.data.id}`;
                    window.location.href = comprobanteUrl;
                } else {
                    showNotificationModal(
                        'Pedido Creado con Éxito',
                        'Su pedido a crédito ha sido recibido y será procesado a la brevedad.',
                        'success');
                    setTimeout(() => {
                        window.location.href = LISTAR_URL; 
                    }, 2500);
                }

            } else {
                showNotificationModal('Error al Crear el Pedido', result.message || 'No se pudo procesar la solicitud.', 'error');
                createButton.disabled = false;
                createButton.innerHTML = originalButtonText;
            }

        } catch (error) {
            console.error('Error en submitOrder:', error);
            showNotificationModal('Error de Conexión', 'Fallo de red al crear la orden. Por favor, intente de nuevo.', 'error');
            createButton.disabled = false;
            createButton.innerHTML = originalButtonText;
        }

    }


    if (itemsContainer.children.length === 0) { } addItemRow();
    updateResumen();
    checkStep1Validity();
    toggleDireccionEntregaBtn.click();

    newOrderBtn.addEventListener('click', (e) => {
        e.preventDefault();
        window.location.href = LISTAR_URL.replace('pedidos_cliente', 'hacer_pedido');
    });

    function printHtmlContent(htmlContent) {
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        iframe.id = 'proforma-print-frame';
        document.body.appendChild(iframe);
        const iframeDocument = iframe.contentWindow.document;
        const bootstrapCss = '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">';
        const bodyContent = `
            <div class="container-fluid p-4">
                ${htmlContent}
            </div>
        `;
        const fullHtml = `
            <!DOCTYPE html>
            <html lang="es">
            
                    <title>Factura Proforma</title>
                        ${bootstrapCss}
                    <style>
                        /* Estilos específicos para la impresión, si fueran necesarios */
                        body { font-family: sans-serif; }
                        @media print {
                            .no-print { display: none; }
                            body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
                        }
                    </style>
                </head>
                <body>           
                    ${bodyContent}
                </body>
            </html>
        `;
        iframeDocument.open();
        iframeDocument.write(fullHtml);
        iframeDocument.close();
        iframe.onload = function () {
            setTimeout(() => {
                iframe.contentWindow.focus();
                iframe.contentWindow.print();
                setTimeout(() => { document.body.removeChild(iframe); }, 1000);
            }, 500);
        }
    }

    const downloadProformaBtn = document.getElementById('downloadProformaBtn');
    if (downloadProformaBtn) {
        downloadProformaBtn.addEventListener('click', () => {
            const proformaHTML = proformaContent.innerHTML;
            if (proformaHTML && proformaHTML.trim().length > 0) {
                printHtmlContent(proformaHTML);
            } else {
                showNotificationModal('Error', 'No se ha generado la proforma para imprimir.', 'error');
            }
        });
    }

    // Nota: La descarga del recibo de pago sigue usando html2canvas, lo cual es adecuado para ese elemento más simple.
    downloadReceiptBtn.addEventListener('click', () => {
        const { jsPDF } = window.jspdf;
        const receiptElement = document.getElementById('paymentReceipt');
        if (receiptElement) {
            html2canvas(receiptElement, { scale: 2 }).then(canvas => {
                const imgData = canvas.toDataURL('image/png');
                const pdf = new jsPDF('p', 'mm', 'a4');
                const pdfWidth = pdf.internal.pageSize.getWidth();
                const imgProps = pdf.getImageProperties(imgData);
                const imgHeight = (imgProps.height * pdfWidth) / imgProps.width;
                pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, imgHeight);
                pdf.save('comprobante-pago.pdf');
            });
        }
    });
    // Show payment receipt container when it has content
    const observer = new MutationObserver(() => {
        const paymentReceiptContainer = document.getElementById('paymentReceiptContainer');
        if (paymentReceipt.innerHTML.trim() !== '') {
            paymentReceiptContainer.style.display = 'block';
        } else {
            paymentReceiptContainer.style.display = 'none';
        }
    });
    observer.observe(paymentReceipt, { childList: true, subtree: true });

    function showResult(type, title, message) {
        goToStep(4);
        if (type === 'success') {
            resultIcon.innerHTML = '<i class="bi bi-check-circle-fill text-success" style="font-size: 4rem;"></i>';
        } else {
            resultIcon.innerHTML = '<i class="bi bi-x-circle-fill text-danger" style="font-size: 4rem;"></i>';
        }
        resultTitle.textContent = title;
        resultMessage.textContent = message;
    }
});