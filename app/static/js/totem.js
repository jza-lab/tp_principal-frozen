class TotemLogin {
    constructor() {
        this.video = document.getElementById('video');
        this.captureBtn = document.getElementById('captureBtn');
        this.retryBtn = document.getElementById('retryBtn');
        this.resultDiv = document.getElementById('result');
        this.manualLoginBtn = document.getElementById('manualLoginBtn');
        this.backToFacialBtn = document.getElementById('backToFacialBtn');
        this.areaFacial = document.getElementById('areaReconocimientoFacial');
        this.loginManual = document.getElementById('loginManual');
        this.manualLoginForm = document.getElementById('manualLoginForm');
        this.manualResultDiv = document.getElementById('manualResult');
        this.stream = null;
        this.failedAttempts = 0;
        this.maxAttempts = 3;
        
        this.init();
    }

    async init() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    width: { ideal: 640 }, 
                    height: { ideal: 480 },
                    facingMode: 'user'
                } 
            });
            this.video.srcObject = this.stream;
        } catch (err) {
            this.showResult('Error al acceder a la cámara: ' + err.message, 'error', this.resultDiv);
            this.showManualLoginOption();
        }

        // Event listeners
        this.captureBtn.addEventListener('click', () => this.captureFace());
        this.retryBtn.addEventListener('click', () => this.retryCapture());
        this.manualLoginBtn.addEventListener('click', () => this.showManualLogin());
        this.backToFacialBtn.addEventListener('click', () => this.showFacialLogin());
        this.manualLoginForm.addEventListener('submit', (e) => this.handleManualLogin(e));
    }

    captureFace() {
        const canvas = document.createElement('canvas');
        canvas.width = this.video.videoWidth;
        canvas.height = this.video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(this.video, 0, 0);
        
        const imageData = canvas.toDataURL('image/jpeg', 0.8);
        this.sendFaceData(imageData);
        
        this.captureBtn.style.display = 'none';
        this.retryBtn.style.display = 'inline-flex';
        this.showResult('Procesando reconocimiento facial...', 'info', this.resultDiv);
    }

    async sendFaceData(imageData) {
        try {
            const response = await fetch('/totem/process_access', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify({ image: imageData })
            });
            const result = await response.json();
            if (response.ok && result.success) {
                this.handleSuccess(result);
            } else {
                this.handleFailure(result);
            }
        } catch (error) {
            this.handleFailure({ message: 'Error de conexión con el servidor.' });
        }
    }

    async handleManualLogin(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const submitBtn = e.target.querySelector('button[type="submit"]');
        this.setLoading(submitBtn, true, 'Verificando...');

        try {
            const response = await fetch('/totem/manual_access', { // Este será el nuevo endpoint
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify(Object.fromEntries(formData))
            });
            const result = await response.json();
            if (response.ok && result.success) {
                this.handleSuccess(result);
            } else {
                this.showResult(result.message || 'Credenciales incorrectas.', 'error', this.manualResultDiv);
            }
        } catch (error) {
            this.showResult('Error de conexión con el servidor.', 'error', this.manualResultDiv);
        } finally {
            this.setLoading(submitBtn, false, 'Registrar Acceso');
        }
    }
    
    handleSuccess(result) {
        sessionStorage.setItem('totemMessage', result.message);
        window.location.href = result.redirect_url;
    }

    handleFailure(result) {
        this.failedAttempts++;
        this.showResult(result.message || 'No se pudo verificar la identidad.', 'error', this.resultDiv);
        if (this.failedAttempts >= this.maxAttempts) {
            this.showManualLoginOption();
        }
    }
    
    retryCapture() {
        this.resultDiv.innerHTML = '';
        this.captureBtn.style.display = 'inline-flex';
        this.retryBtn.style.display = 'none';
        document.getElementById('guiaFacial').textContent = 'Mire directamente a la cámara y presione el botón para registrar su acceso';
    }

    showManualLogin() {
        this.areaFacial.style.display = 'none';
        this.loginManual.style.display = 'block';
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }
    }

    showFacialLogin() {
        this.loginManual.style.display = 'none';
        this.areaFacial.style.display = 'block';
        this.failedAttempts = 0;
        this.retryCapture();
        this.init(); // Reiniciar la cámara
    }

    showManualLoginOption() {
        document.getElementById('guiaFacial').innerHTML = `
            <span class="text-warning"><i class="bi bi-exclamation-triangle me-1"></i>Si tiene problemas, use el acceso manual.</span>`;
    }

    showResult(message, type, element) {
        const alertClass = type === 'success' ? 'alert-success' : type === 'error' ? 'alert-danger' : 'alert-info';
        element.innerHTML = `<div class="alert ${alertClass} alert-dismissible fade show">${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
        if (type === 'error') {
            setTimeout(() => { element.innerHTML = ''; }, 5000);
        }
    }
    
    setLoading(button, isLoading, text) {
        button.disabled = isLoading;
        button.innerHTML = isLoading ? `<i class="bi bi-hourglass-split me-2"></i>${text}` : text;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new TotemLogin();
});