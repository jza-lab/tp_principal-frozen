document.addEventListener('DOMContentLoaded', function() {
    // Elementos del DOM
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    const selectedFile = document.getElementById('selectedFile');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const removeFile = document.getElementById('removeFile');
    const submitBtn = document.getElementById('submitBtn');
    const loadingState = document.getElementById('loadingState');
    const resultsSection = document.getElementById('resultsSection');
    const errorAlert = document.getElementById('errorAlert');
    const successAlert = document.getElementById('successAlert');
    const statsContainer = document.getElementById('statsContainer');
    const detailsTable = document.getElementById('detailsTable');
    const resultBadge = document.getElementById('resultBadge');

    let currentFile = null;

    // Event Listeners
    browseBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelect);
    removeFile.addEventListener('click', clearFile);
    submitBtn.addEventListener('click', submitFile);

    // Drag and Drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    // Funciones
    function handleFileSelect(e) {
        if (e.target.files.length) {
            handleFile(e.target.files[0]);
        }
    }

    function handleFile(file) {
        // Validar tipo de archivo
        const validTypes = [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel'
        ];
        
        if (!validTypes.includes(file.type) && !file.name.match(/\.(xlsx|xls)$/)) {
            showError('Por favor, selecciona un archivo Excel válido (.xlsx o .xls)');
            return;
        }

        currentFile = file;
        
        // Mostrar información del archivo
        fileName.textContent = file.name;
        fileSize.textContent = formatFileSize(file.size);
        selectedFile.style.display = 'block';
        
        // Habilitar botón de enviar
        submitBtn.disabled = false;
        
        // Ocultar alertas y resultados anteriores
        hideAlerts();
        resultsSection.style.display = 'none';
    }

    function clearFile() {
        currentFile = null;
        fileInput.value = '';
        selectedFile.style.display = 'none';
        submitBtn.disabled = true;
        hideAlerts();
    }

    async function submitFile() {
if (!currentFile) {
showError('Por favor, selecciona un archivo primero');
return;
}

// Mostrar estado de carga
loadingState.style.display = 'block';
submitBtn.disabled = true;
hideAlerts();
resultsSection.style.display = 'none';

const formData = new FormData();
formData.append('archivo', currentFile);

try {
console.log('=== INICIANDO ENVÍO ===');
console.log('Archivo:', currentFile.name);
console.log('Tamaño:', currentFile.size);
console.log('Tipo:', currentFile.type);

const response = await fetch('/api/precios/cargar-archivo-proveedor', {
    method: 'POST',
    body: formData
});

console.log('=== RESPUESTA RECIBIDA ===');
console.log('Status:', response.status);
console.log('Status Text:', response.statusText);
console.log('Headers:', Object.fromEntries(response.headers.entries()));

const text = await response.text();
console.log('Response body:', text);

// Intentar parsear como JSON
let result;
try {
    result = JSON.parse(text);
    console.log('JSON parseado:', result);
} catch (e) {
    console.error('Error parseando JSON:', e);
    throw new Error('Respuesta no es JSON válido: ' + text.substring(0, 100));
}

if (!response.ok) {
    throw new Error(result.error || `Error ${response.status}: ${response.statusText}`);
}

// Mostrar resultados
showResults(result);
showSuccess(result.message || 'Archivo procesado exitosamente');

} catch (error) {
console.error('=== ERROR COMPLETO ===', error);
showError(error.message);
} finally {
loadingState.style.display = 'none';
submitBtn.disabled = false;
console.log('=== PROCESAMIENTO COMPLETADO ===');
}
}

    function showResults(result) {
        // Actualizar badge según éxito
        if (result.success) {
            resultBadge.className = 'result-badge badge-success';
            resultBadge.textContent = 'Éxito';
        } else {
            resultBadge.className = 'result-badge badge-error';
            resultBadge.textContent = 'Error';
        }

        // Mostrar estadísticas
        if (result.reporte) {
            const stats = result.reporte;
            statsContainer.innerHTML = `
                <div class="stat-item">
                    <div class="stat-value">${stats.total_filas}</div>
                    <div class="stat-label">Total Filas</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${stats.actualizados}</div>
                    <div class="stat-label">Actualizados</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${stats.sin_cambios}</div>
                    <div class="stat-label">Sin Cambios</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${stats.errores}</div>
                    <div class="stat-label">Errores</div>
                </div>
            `;
        }

        // Mostrar detalles
        if (result.detalles && result.detalles.length) {
            const tbody = detailsTable.querySelector('tbody');
            tbody.innerHTML = '';
            
            result.detalles.forEach(detalle => {
                const statusClass = getStatusClass(detalle.estado);
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${detalle.fila}</td>
                    <td>${detalle.codigo_interno}</td>
                    <td>${detalle.producto}</td>
                    <td>${detalle.proveedor}</td>
                    <td><span class="status-cell ${statusClass}">${detalle.estado}</span></td>
                    <td>${detalle.mensaje}</td>
                `;
                tbody.appendChild(row);
            });
        }

        resultsSection.style.display = 'block';
    }

    function getStatusClass(estado) {
        switch(estado) {
            case 'ACTUALIZADO':
                return 'status-actualizado';
            case 'SIN_CAMBIOS':
                return 'status-sin-cambios';
            case 'ERROR':
                return 'status-error';
            default:
                return '';
        }
    }

    function showError(message) {
        errorAlert.textContent = message;
        errorAlert.style.display = 'block';
        successAlert.style.display = 'none';
    }

    function showSuccess(message) {
        successAlert.textContent = message;
        successAlert.style.display = 'block';
        errorAlert.style.display = 'none';
    }

    function hideAlerts() {
        errorAlert.style.display = 'none';
        successAlert.style.display = 'none';
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
});