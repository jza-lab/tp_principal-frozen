document.addEventListener('DOMContentLoaded', function () {

    const cuilParte1 = document.getElementById('cuil_parte1');
    const cuilParte2 = document.getElementById('cuil_parte2');
    const cuilParte3 = document.getElementById('cuil_parte3');

    const clienteIdOculto = document.getElementById('id_cliente');

    const nombreCliente = document.getElementById('nombre_cliente');
    const telefono = document.getElementById('telefono');
    const email = document.getElementById('email');

    const calleFacturacion = document.getElementById('calle_facturacion');
    const alturaFacturacion = document.getElementById('altura_facturacion');
    const provinciaFacturacion = document.getElementById('provincia_facturacion');
    const localidadFacturacion = document.getElementById('localidad_facturacion');
    const pisoFacturacion = document.getElementById('piso_facturacion');
    const deptoFacturacion = document.getElementById('depto_facturacion');
    const cpFacturacion = document.getElementById('codigo_postal_facturacion');
    const condicionVenta = document.getElementById('condicion_venta');
    const costoEnvioInput = document.getElementById('costo_envio');

    const cpEntrega = document.getElementById('codigo_postal');


    function fetchCostoEnvio(codigoPostal) {
        if (!codigoPostal || codigoPostal.length < 4) {
            if(costoEnvioInput) costoEnvioInput.value = '0.00';
            return;
        }

        fetch(`/api/zonas/costo-por-cp?codigo_postal=${codigoPostal}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if(costoEnvioInput) costoEnvioInput.value = data.data.precio.toFixed(2);
                } else {
                    if(costoEnvioInput) costoEnvioInput.value = '0.00';
                }
            })
            .catch(error => {
                console.error('Error fetching shipping cost:', error);
                if(costoEnvioInput) costoEnvioInput.value = '0.00';
            });
    }

    // Helper para bloquear/desbloquear campos
    function toggleClientFields(isReadonly) {
        const fields = [
            nombreCliente, telefono, email,
            calleFacturacion, alturaFacturacion, provinciaFacturacion,
            localidadFacturacion, pisoFacturacion, deptoFacturacion,
            cpFacturacion
        ];

        fields.forEach(field => {
            if (field) {
                if (isReadonly) {
                    field.setAttribute('readonly', 'readonly');
                    // Para select, readonly no funciona igual que input, a veces se usa disabled
                    if (field.tagName === 'SELECT') {
                         // Bootstrap style: pointer-events none + bg-light appearance
                        field.style.pointerEvents = 'none';
                        field.classList.add('bg-light');
                        field.setAttribute('tabindex', '-1'); // Evita foco con tab
                    }
                } else {
                    field.removeAttribute('readonly');
                    if (field.tagName === 'SELECT') {
                        field.style.pointerEvents = 'auto';
                        field.classList.remove('bg-light');
                        field.removeAttribute('tabindex');
                    }
                }
            }
        });
    }

    // Helper para mostrar error visual
    function mostrarErrorBusqueda(mensaje) {
        // Busca si ya existe un mensaje de error previo y elimínalo
        limpiarErrorBusqueda();

        // Crear el elemento de alerta
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-warning mt-2 mb-0 py-1 px-2 small';
        alertDiv.id = 'search-error-msg';
        alertDiv.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i> ${mensaje}`;

        // Insertar después del input group del CUIL
        // El input group está en cuilParte1.parentNode.parentNode normalmente (col-md-6 > input-group)
        // Ojo: cuilParte1 está dentro de .input-group
        const inputGroup = cuilParte1.closest('.input-group');
        if (inputGroup) {
            inputGroup.parentNode.insertBefore(alertDiv, inputGroup.nextSibling);
        }
    }

    function limpiarErrorBusqueda() {
        const existingError = document.getElementById('search-error-msg');
        if (existingError) {
            existingError.remove();
        }
    }


    // Función para limpiar campos
    function limpiarDatosCliente() {
        if (clienteIdOculto) clienteIdOculto.value = '';

        nombreCliente.value = '';
        telefono.value = '';
        email.value = '';
        if (calleFacturacion) calleFacturacion.value = '';
        if (alturaFacturacion) alturaFacturacion.value = '';
        if (provinciaFacturacion) provinciaFacturacion.value = '';
        if (localidadFacturacion) localidadFacturacion.value = '';
        if (pisoFacturacion) pisoFacturacion.value = '';
        if (deptoFacturacion) deptoFacturacion.value = '';
        if (condicionVenta) condicionVenta.value = '';
        if (cpFacturacion) cpFacturacion.value = '';
        fetchCostoEnvio('');
        
        // Desbloquear campos para permitir escritura manual si no se encuentra cliente
        toggleClientFields(false);
    }

    // --- Función principal de búsqueda (CORREGIDA LA LÓGICA DE LIMPIEZA) ---
    function buscarCliente() {
        const cuilConGuiones = cuilParte1.value + "-" + cuilParte2.value + "-" + cuilParte3.value;
        const cuilSoloDigitos = cuilParte1.value + cuilParte2.value + cuilParte3.value;
        
        limpiarErrorBusqueda(); // Limpiar errores previos al intentar buscar

        if (cuilConGuiones.length === 13 && /^\d{11}$/.test(cuilSoloDigitos)) {

            const urlApiBase = window.CLIENTE_API_URL_BASE;
            const urlApi = urlApiBase.slice(0, -1) + cuilConGuiones;

            fetch(urlApi, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            })
                .then(response => {
                    if (response.status === 404) {
                        const msg = `No se encontró cliente con CUIT ${cuilConGuiones}.`;
                        console.log(msg);
                        mostrarErrorBusqueda(msg);
                        return null;
                    }

                    if (!response.ok) {
                        throw new Error(`Error ${response.status} del servidor al buscar cliente.`);
                    }

                    return response.json();
                })
                .then(cliente => {
                    if (cliente) {
                        console.log('Cliente encontrado');
                        limpiarErrorBusqueda(); // Éxito

                        if (clienteIdOculto) {
                            clienteIdOculto.value = cliente.id || '';
                        }
                        if (cliente.id) {
                            verificarCondicionVenta(cliente.id);
                        }

                        nombreCliente.value = cliente.nombre || '';
                        telefono.value = cliente.telefono || '';
                        email.value = cliente.email || '';

                        const dir = cliente.direccion || {};
                        if (calleFacturacion) calleFacturacion.value = dir.calle || '';
                        if (alturaFacturacion) alturaFacturacion.value = dir.altura || '';
                        if (localidadFacturacion) localidadFacturacion.value = dir.localidad || '';
                        if (pisoFacturacion) pisoFacturacion.value = dir.piso || '';
                        if (deptoFacturacion) deptoFacturacion.value = dir.depto || '';
                        if (cpFacturacion) cpFacturacion.value = dir.codigo_postal || '';
                        if (condicionVenta) condicionVenta.value = cliente.condicion_venta || '';
                        if (provinciaFacturacion) {
                            const valorProvincia = dir.provincia || '';

                            // 1. Asignar el valor
                            provinciaFacturacion.value = valorProvincia;

                            // 2. Forzar la re-asignación (a veces necesario para el DOM/Bootstrap)
                            // Esto asegura que el DOM reconozca el cambio de valor
                            provinciaFacturacion.dispatchEvent(new Event('change')); // Dispara un evento 'change'

                            console.log(`Provincia asignada: ${provinciaFacturacion.value}`); // Verifica en consola
                        }
                        
                        // Bloquear campos para evitar edición accidental de datos maestros
                        toggleClientFields(true);

                        //Direccion alternativa
                        const checkboxDireccion = document.getElementById('usar_direccion_alternativa');
                        if (checkboxDireccion) {
                            if (!checkboxDireccion.checked) {
                                fetchCostoEnvio(dir.codigo_postal);
                            }
                            // Si el cliente no tiene una calle principal, forzar la dirección alternativa
                            if (!dir.calle) {
                                checkboxDireccion.checked = true;
                                // Disparar el evento 'change' para que la otra lógica de UI reaccione
                                checkboxDireccion.dispatchEvent(new Event('change'));
                            }
                        } else {
                            fetchCostoEnvio(dir.codigo_postal);
                        }


                    } else {
                        // Si llegamos aqui con null (desde el 404), ya mostramos error arriba
                        limpiarDatosCliente();
                        actualizarCondicionVentaUI(false);
                    }
                })
                .catch(error => {
                    console.error('Error al procesar la búsqueda del cliente:', error.message);
                    mostrarErrorBusqueda("Error de conexión al buscar el cliente.");
                    limpiarDatosCliente();
                });

        } else if (cuilSoloDigitos.length < 11 && cuilSoloDigitos.length > 0) {
            limpiarDatosCliente();
            limpiarErrorBusqueda();
        } else if (cuilSoloDigitos.length === 0) {
            limpiarDatosCliente();
            limpiarErrorBusqueda();
        }
    }

    function verificarCondicionVenta(clienteId) {
        const urlApiCondVenta = `/orden-venta/cliente/cond_venta/${clienteId}`; // Ajusta la URL si es necesario

        fetch(urlApiCondVenta, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Error ${response.status} al verificar condición de venta.`);
                }
                return response.json(); // La API devuelve 'es_nuevo' (true/false)
            })
            .then(esNuevo => {
                // Llama a la función que modifica el DOM
                actualizarCondicionVentaUI(esNuevo);
            })
            .catch(error => {
                console.error('Error al verificar condición de venta:', error.message);
                // En caso de error, asumimos cliente existente o no limitamos
                actualizarCondicionVentaUI(false);
            });
    }
    function actualizarCondicionVentaUI(esNuevo) {
        const condicionVentaSelect = document.getElementById('condicion_venta');
        if (!condicionVentaSelect) return;

        const credito30Option = condicionVentaSelect.querySelector('option[value="credito_30"]');
        const credito90Option = condicionVentaSelect.querySelector('option[value="credito_90"]');
        const contadoOption = condicionVentaSelect.querySelector('option[value="contado"]');

        if (esNuevo) {
            // Ocultar las opciones de crédito
            if (credito30Option) credito30Option.style.display = 'none';
            if (credito90Option) credito90Option.style.display = 'none';

            // Seleccionar 'Al Contado'
            if (contadoOption) contadoOption.selected = true;
            condicionVentaSelect.dispatchEvent(new Event('change'));

        } else {
            // Mostrar las opciones de crédito
            if (credito30Option) credito30Option.style.display = 'block';
            if (credito90Option) credito90Option.style.display = 'block';
        }
    }

    // Llama a la función al inicio de gestionClientes.js (DOMContentLoaded)
    // para establecer el estado inicial si no hay un cliente precargado.
    actualizarCondicionVentaUI(false);

    //Para que cuando escribas y termines un campo pase al otro
    function handleCuilInput(e, maxLength, nextField, prevField) {
        const field = e.target;

        if (field.value.length > maxLength) {
            field.value = field.value.slice(0, maxLength);
        }

        if (field.value.length === maxLength && nextField) {
            nextField.focus();
        }

        if (field.value.length === 0 && e.inputType === 'deleteContentBackward' && prevField) {
            prevField.focus();
        }

        if (field === cuilParte3 && field.value.length === 1) {
            buscarCliente();
            if (nombreCliente) nombreCliente.focus();
        }

        if (field.value.length < maxLength && prevField) {
            buscarCliente();
        }
    }

    cuilParte1.addEventListener('input', (e) => handleCuilInput(e, 2, cuilParte2, null));
    cuilParte2.addEventListener('input', (e) => handleCuilInput(e, 8, cuilParte3, cuilParte1));
    cuilParte3.addEventListener('input', (e) => handleCuilInput(e, 1, null, cuilParte2));

    cuilParte1.addEventListener('blur', buscarCliente);
    cuilParte2.addEventListener('blur', buscarCliente);
    cuilParte3.addEventListener('blur', buscarCliente);

    if (cpFacturacion) {
        cpFacturacion.addEventListener('input', (e) => {
            const checkbox = document.getElementById('usar_direccion_alternativa');
            if (!checkbox || !checkbox.checked) {
                fetchCostoEnvio(e.target.value);
            }
        });
    }
    if (cpEntrega) {
        cpEntrega.addEventListener('input', (e) => {
            const checkbox = document.getElementById('usar_direccion_alternativa');
            if (checkbox && checkbox.checked) {
                fetchCostoEnvio(e.target.value);
            }
        });
    }

    const checkboxDireccion = document.getElementById('usar_direccion_alternativa');
    if (checkboxDireccion) {
        checkboxDireccion.addEventListener('change', function() {
            if (this.checked) {
                fetchCostoEnvio(cpEntrega.value);
            } else {
                fetchCostoEnvio(cpFacturacion.value);
            }
        });
    }
});
