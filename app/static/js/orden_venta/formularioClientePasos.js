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

    // Elementos de Datos del Cliente y Productos
    const datosClienteCard = document.getElementById('datosClienteCard');
    const productosCard = document.getElementById('productosCard');
    const resumenCalculos = document.getElementById('resumenCalculos');
    const idClienteInput = document.getElementById('id_cliente');
    const itemsContainer = document.getElementById('items-container');
    const addItemBtn = document.getElementById('addItemBtn');
    const fechaEntregaInput = document.getElementById('fecha_requerido');
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
    const costoEnvioSpan = document.getElementById('resumen-flete');

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
    let dirPrincipal = cliente.direccion || (cliente.direcciones && (cliente.direcciones.find(d => d.es_principal) || cliente.direcciones[0]));
    if (!dirPrincipal && cliente.direcciones && cliente.direcciones.length > 0) {
        dirPrincipal = cliente.direcciones.find(d => d.es_principal) || cliente.direcciones[0];
    }

    function fetchCostoEnvio(codigoPostal) {
        if (!codigoPostal || codigoPostal.length < 4) {
            costoEnvioSpan.textContent = '$0.00';
            costoEnvioSpan.dataset.costo = '0';
            updateResumen();
            return;
        }

        fetch(`/api/zonas/costo-por-cp?codigo_postal=${codigoPostal}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const precio = data.data.precio.toFixed(2);
                    costoEnvioSpan.textContent = `$${precio}`;
                    costoEnvioSpan.dataset.costo = precio;
                } else {
                    costoEnvioSpan.textContent = '$0.00';
                    costoEnvioSpan.dataset.costo = '0';
                }
                updateResumen();
            })
            .catch(error => {
                console.error('Error fetching shipping cost:', error);
                costoEnvioSpan.textContent = '$0.00';
                costoEnvioSpan.dataset.costo = '0';
                updateResumen();
            });
    }


    function inicializarFormularioCliente() {
        const clienteId = idClienteInput.value;

        if (clienteId) {
            // Cliente logueado: comportamiento original
            isUsingAlternativeAddress = true;
            toggleDireccionEntregaBtn.click()
            actualizarCondicionVenta(clienteId);

            const ivaCode = String(cliente.condicion_iva);
            const ivaData = CONDICION_IVA_MAP[ivaCode] || { text: 'Consumidor Final', factura: 'B' };
            condicionIvaDisplay.value = ivaData.text;
            tipoFacturaInput.value = ivaData.factura;
            condicionIvaValue.value = ivaCode;
            
            nextStep1Btn.disabled = true; // Se habilita al añadir items
            fetchCostoEnvio(cpFacturacionInput.value);
        } else {
            // Cliente anónimo: inicialización suave
            // No deshabilitar el botón, solo esperar a que se cumplan las condiciones (cliente + items)
            // La validación se hará en el evento 'input' del formulario.
            condicionIvaDisplay.value = 'Consumidor Final'; // Valor por defecto
            tipoFacturaInput.value = 'B';
            nextStep1Btn.disabled = true; // Se habilita al añadir items
        }
        goToStep(1); // Siempre ir al paso 1 al inicio
    }


    toggleDireccionEntregaBtn.addEventListener('click', function () {
        isUsingAlternativeAddress = !isUsingAlternativeAddress;
        this.dataset.active = isUsingAlternativeAddress;
        const camposAlternativos = ['calle', 'altura', 'provincia', 'localidad', 'codigo_postal', 'piso', 'depto'];
        facturacionAddressFields.style.display = isUsingAlternativeAddress ? 'none' : 'block';
        direccionEntregaAlternativaContainer.style.display = isUsingAlternativeAddress ? 'block' : 'none';
        toggleDireccionEntregaBtn.innerHTML = isUsingAlternativeAddress
            ? '<i class="bi bi-house-door-fill me-1"></i> Usar Dirección de Facturación'
            : '<i class="bi bi-truck me-1"></i> Usar otra dirección';
        idDireccionEntregaInput.value = isUsingAlternativeAddress ? '' : (idDireccionEntregaInput.dataset.facturacionId || '');
        camposAlternativos.forEach(f => {
            const campo = document.getElementById(`${f}_alternativa`);
            if (campo) {
                const esRequerido = ['calle', 'altura', 'provincia', 'localidad', 'codigo_postal'].includes(f);
                campo.required = isUsingAlternativeAddress && esRequerido;

                // Si se oculta la dirección alternativa, limpiar los campos
                if (!isUsingAlternativeAddress) {
                    campo.value = '';
                    campo.classList.remove('is-invalid');
                }
            }
        });
        if (isUsingAlternativeAddress) {
            fetchCostoEnvio(cpAlternativaInput.value);
        } else {
            fetchCostoEnvio(cpFacturacionInput.value);
        }
    });

    if (cpAlternativaInput) {
        cpAlternativaInput.addEventListener('input', (e) => {
            if (isUsingAlternativeAddress) {
                fetchCostoEnvio(e.target.value);
            }
        });
    }

    // --- LÓGICA DE VALIDACIÓN DEL PASO 1 ---

    function validateAndHighlightFields(container) {
        let firstInvalidField = null;
        const fields = container.querySelectorAll('input:not([type="hidden"]), select, textarea');

        fields.forEach(field => {
            if (!field.checkValidity()) {
                field.classList.add('is-invalid');
                if (!firstInvalidField) {
                    firstInvalidField = field;
                }
            } else {
                field.classList.remove('is-invalid');
            }
        });

        return {
            isValid: firstInvalidField === null,
            firstInvalidField: firstInvalidField
        };
    }

    // --- LÓGICA DE HABILITACIÓN DEL BOTÓN "VER PROFORMA" ---
    window.updateProformaButtonState = function() {
        const clienteId = idClienteInput.value;
        const cuit = document.getElementById('cuil_cuit_cliente').value.trim();
        const email = document.getElementById('email_cliente').value.trim();
        const isClientDataPresent = clienteId || (cuit.length >= 11 && email.includes('@'));
        const hasItems = itemsContainer.querySelectorAll('.item-row').length > 0;
        nextStep1Btn.disabled = !(isClientDataPresent && hasItems);
    };

    // Escuchar cambios en el formulario para reevaluar el estado del botón.
    form.addEventListener('input', window.updateProformaButtonState);
    form.addEventListener('change', window.updateProformaButtonState);


    nextStep1Btn.addEventListener('click', (e) => { e.preventDefault(); goToStep(2); });
    prevStep2Btn.addEventListener('click', () => goToStep(1));

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
            nextStep1Btn.style.display = 'block';
            step1Indicator.classList.add('active');
            step1Indicator.classList.remove('completed');
            step2Indicator.classList.remove('active', 'completed');
            step3Indicator.classList.remove('active', 'completed');
        } else if (step === 2) {

            // 2. Validar que haya al menos un ítem en el pedido
            if (itemsContainer.querySelectorAll('.item-row').length === 0) {
                goToStep(1)
                showNotificationModal('Sin Productos', 'Debe añadir al menos un producto al pedido.', 'warning');
                addItemBtn.focus();
            }

            const validationResult = validateAndHighlightFields(step1Content);
            if (!validationResult.isValid) {
                goToStep(1)
                showNotificationModal('Campos Incompletos', 'Por favor, corrija los campos marcados en rojo antes de continuar.', 'warning');
                validationResult.firstInvalidField.focus();
                validationResult.firstInvalidField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }

            if (isUsingAlternativeAddress) {
                const isValid = await validateAlternativeAddress();
                if (!isValid) {
                    goToStep(1)
                    goToStep(1)
                    return;
                };
            }

            let cantidadEsInvalida = false;
            let productoInvalido = '';
            itemsContainer.querySelectorAll('.item-row').forEach(row => {
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
                )
                return;
            }

            const payload = buildPayload();
            if (!payload || payload.items.length === 0) {
                showNotificationModal('Error', 'Debe haber al menos un producto.', 'warning');
                return;
            }
            pedidoDataTemp.value = JSON.stringify(payload);
            step1Actions.style.display = 'none';
            nextStep1Btn.style.display = 'none';
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
    
            if (response.ok && result.success) {
                const pedidoId = result.data.id;
                const redirectUrl = isPayment ? `/public/comprobante-pago/${pedidoId}` : LISTAR_URL;

                // Si es un pago (flujo público), enviar el correo automáticamente en segundo plano
                if (isPayment) {
                    fetch(`/api/pedidos/${pedidoId}/enviar-qr`, {
                        method: 'POST',
                        headers: { 'X-CSRFToken': csrfToken }
                    }).catch(error => console.error('Error en el envío automático de correo:', error));
                }

                window.location.href = redirectUrl;
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

    updateResumen();
    inicializarFormularioCliente();

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

    // --- NUEVA FUNCIÓN PARA BÚSQUEDA DE CLIENTE POR CUIT ---
    const cuitInput = document.getElementById('cuil_cuit_cliente');
    cuitInput.addEventListener('blur', async function() {
        const cuit = this.value.trim();
        if (cuit.length >= 11) {
            try {
                const response = await fetch(`/public/api/buscar-cliente?cuit=${cuit}`);
                const result = await response.json();

                if (response.ok && result.success) {
                    const cliente = result.data;
                    // Rellenar campos del cliente
                    document.getElementById('id_cliente').value = cliente.id;
                    document.getElementById('email_cliente').value = cliente.email;
                    document.getElementById('nombre_cliente').value = cliente.nombre || cliente.razon_social;
                    document.getElementById('telefono').value = cliente.telefono;
                    
                    // --- CORRECCIÓN: Lógica robusta para Condición IVA ---
                    let ivaKey = cliente.condicion_iva;
                    let ivaData = CONDICION_IVA_MAP[ivaKey];
                    
                    // Si no se encuentra por clave (ej. viene "Responsable Inscripto" en vez de "1")
                    if (!ivaData) {
                        const foundEntry = Object.entries(CONDICION_IVA_MAP).find(([key, data]) => data.text === ivaKey);
                        if (foundEntry) {
                            ivaKey = foundEntry[0]; // Corregimos al key numérico
                            ivaData = foundEntry[1];
                        }
                    }

                    // Fallback final si todo falla
                    if (!ivaData) {
                        ivaKey = '4';
                        ivaData = CONDICION_IVA_MAP[ivaKey];
                    }

                    condicionIvaDisplay.value = ivaData.text;
                    tipoFacturaInput.value = ivaData.factura;
                    condicionIvaValue.value = ivaKey; // Usar siempre la clave numérica correcta

                    // Actualizar dirección si existe
                    if (cliente.direccion) {
                        calleFacturacionInput.value = cliente.direccion.calle;
                        alturaFacturacionInput.value = cliente.direccion.altura;
                        provinciaFacturacionInput.value = cliente.direccion.provincia;
                        localidadFacturacionInput.value = cliente.direccion.localidad;
                        cpFacturacionInput.value = cliente.direccion.codigo_postal;
                        fetchCostoEnvio(cliente.direccion.codigo_postal);
                    }
                    actualizarCondicionVenta(cliente.id);
                } else {
                    // Limpiar campos si el cliente no se encuentra
                    document.getElementById('id_cliente').value = '';
                    document.getElementById('nombre_cliente').value = '';
                    document.getElementById('telefono').value = '';
                    condicionIvaDisplay.value = 'Consumidor Final';
                    tipoFacturaInput.value = 'B';
                    condicionIvaValue.value = '4'; // Consumidor Final por defecto
                    // Limpiar dirección
                    calleFacturacionInput.value = '';
                    alturaFacturacionInput.value = '';
                    provinciaFacturacionInput.value = '';
                    localidadFacturacionInput.value = '';
                    cpFacturacionInput.value = '';
                }
            } catch (error) {
                console.error('Error al buscar cliente:', error);
                showNotificationModal('Error de Red', 'No se pudo conectar con el servidor para buscar el cliente.', 'error');
            }
        }
    });

    async function actualizarCondicionVenta(clienteId) {
        const condicionVentaSelect = document.getElementById('condicion_venta');
        if (!clienteId) {
            condicionVentaSelect.innerHTML = '<option value="contado">Al Contado</option>';
            condicionVentaSelect.disabled = true;
            return;
        }

        try {
            const response = await fetch(`/public/api/cliente/${clienteId}/condicion-pago`);
            const result = await response.json();

            if (result.success) {
                condicionVentaSelect.innerHTML = '';
                result.condiciones_pago.forEach(condicion => {
                    const option = document.createElement('option');
                    option.value = condicion.valor;
                    option.textContent = condicion.texto;
                    condicionVentaSelect.appendChild(option);
                });
                condicionVentaSelect.disabled = false;
            } else {
                showNotificationModal('Error', 'No se pudo determinar la condición de pago del cliente.', 'error');
            }
        } catch (error) {
            console.error('Error al obtener la condición de venta:', error);
            showNotificationModal('Error de Red', 'No se pudo conectar con el servidor para verificar la condición de pago.', 'error');
        }
    }

    async function validateAlternativeAddress() {
        const direccion = {
            calle: calleAlternativaInput.value,
            altura: alturaAlternativaInput.value,
            localidad: localidadAlternativaInput.value,
            provincia: provinciaAlternativaInput.value,
        };

        if (!direccion.calle || !direccion.altura || !direccion.localidad || !direccion.provincia) {
            showNotificationModal('Campos Incompletos', 'Por favor, complete todos los campos de la dirección de entrega.', 'warning');
            return false;
        }

        try {
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

            if (result.success) {
                return true;
            } else {
                showNotificationModal('Dirección Inválida', result.message || 'La dirección de entrega alternativa no pudo ser validada.', 'error');
                return false;
            }
        } catch (error) {
            console.error('Error en la validación de dirección:', error);
            showNotificationModal('Error de Red', 'No se pudo conectar con el servidor para validar la dirección.', 'error');
            return false;
        }
    }
});
