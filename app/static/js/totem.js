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
            this.showResult('Error al acceder a la cámara: ' + err.message, 'error');
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
        this.showResult('🔄 Procesando reconocimiento facial...', 'info');
    }

    async sendFaceData(imageData) {
        try {
            const response = await fetch('/totem/login_face', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ image: imageData })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            
            if (result.success) {
                this.showAccessResult(result);
            } else {
                this.failedAttempts++;
                this.showResult(` ${result.message || 'No se pudo verificar la identidad'}`, 'error');
                
                if (this.failedAttempts >= this.maxAttempts) {
                    this.showManualLoginOption();
                }
            }
        } catch (error) {
            this.failedAttempts++;
            console.error('Error en reconocimiento facial:', error);
            this.showResult('Error de conexión: ' + error.message, 'error');
            
            if (this.failedAttempts >= this.maxAttempts) {
                this.showManualLoginOption();
            }
        }
    }

    async handleManualLogin(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        
        submitBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Verificando...';
        submitBtn.disabled = true;

        try {
            const response = await fetch('/totem/login_manual', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    legajo: formData.get('legajo'),
                    password: formData.get('password')
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            
            if (result.success) {
                this.showAccessResult(result);
            } else {
                this.showResult(` ${result.message || 'Credenciales incorrectas'}`, 'error');
            }
        } catch (error) {
            console.error('Error en login manual:', error);
            this.showResult('Error de conexión: ' + error.message, 'error');
        } finally {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    }

    retryCapture() {
        this.resultDiv.innerHTML = '';
        this.captureBtn.style.display = 'inline-flex';
        this.retryBtn.style.display = 'none';
        
        // Reset del texto de guía
        document.getElementById('guiaFacial').textContent = 'Mire directamente a la cámara y presione el botón para registrar su acceso';
    }

    showManualLogin() {
        this.areaFacial.style.display = 'none';
        this.loginManual.style.display = 'block';
        
        // Detener cámara si está activa
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }
    }

    showFacialLogin() {
        this.loginManual.style.display = 'none';
        this.areaFacial.style.display = 'block';
        this.failedAttempts = 0;
        this.retryCapture();
        
        // Reiniciar cámara
        this.init();
    }

    showManualLoginOption() {
        document.getElementById('guiaFacial').innerHTML = `
            <span class="text-warning">
                <i class="bi bi-exclamation-triangle me-1"></i>
                Reconocimiento no disponible. Use el acceso manual.
            </span>
        `;
        this.manualLoginBtn.style.display = 'block';
    }

    showResult(message, type) {
        const alertClass = type === 'success' ? 'alert-success' : 
                          type === 'error' ? 'alert-danger' : 'alert-info';
        
        this.resultDiv.innerHTML = `
            <div class="alert ${alertClass} alert-dismissible fade show">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

        // Auto-hide después de 5 segundos para errores
        if (type === 'error') {
            setTimeout(() => {
                if (this.resultDiv.innerHTML) {
                    this.resultDiv.innerHTML = '';
                }
            }, 5000);
        }
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    new TotemLogin();
});