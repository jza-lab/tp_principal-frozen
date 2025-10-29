class TotemLogin {
    constructor() {
        // Elementos de la cámara y login
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

        // Elementos del Modal 2FA
        this.modal2FA = new bootstrap.Modal(document.getElementById('modal2FA'));
        this.verifyTokenBtn = document.getElementById('verifyTokenBtn');
        this.resendTokenBtn = document.getElementById('resendTokenBtn');
        this.result2FADiv = document.getElementById('result2FA');
        this.timer2FAElement = document.getElementById('timer2FA');
        this.resendTimerElement = document.getElementById('resendTimer');
        this.token2FAInput = document.getElementById('token2FA');
        this.cancel2FABtn = document.getElementById('cancel2FABtn');

        // Estado y Timers
        this.stream = null;
        this.failedAttempts = 0;
        this.maxAttempts = 3;
        this.mainTimerInterval = null;
        this.resendTimerInterval = null;
        
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
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            const response = await fetch('/totem/process_access', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json', 
                    'Accept': 'application/json',
                    'X-CSRFToken': csrfToken
                },
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
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            const response = await fetch('/totem/manual_access', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json', 
                    'Accept': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(Object.fromEntries(formData))
            });
            const result = await response.json();
            if (response.ok && result.success) {
                if (result.requires_2fa) {
                    this.show2FAModal();
                } else {
                    this.handleSuccess(result);
                }
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

    // --- Métodos para 2FA ---
    show2FAModal() {
        this.modal2FA.show();
        this.startMainTimer(300); // 5 minutos
        this.startResendTimer(30);
        
        // Limpiar listeners previos para evitar duplicados
        this.verifyTokenBtn.removeEventListener('click', this.verifyTokenHandler);
        this.resendTokenBtn.removeEventListener('click', this.resendTokenHandler);
        this.cancel2FABtn.removeEventListener('click', this.cancel2FAHandler);

        // Crear handlers bindeados para mantener el contexto de 'this'
        this.verifyTokenHandler = this.handleVerifyToken.bind(this);
        this.resendTokenHandler = this.handleResendToken.bind(this);
        this.cancel2FAHandler = this.handleCancel2FA.bind(this);

        this.verifyTokenBtn.addEventListener('click', this.verifyTokenHandler);
        this.resendTokenBtn.addEventListener('click', this.resendTokenHandler);
        this.cancel2FABtn.addEventListener('click', this.cancel2FAHandler);
    }

    handleCancel2FA() {
        clearInterval(this.mainTimerInterval);
        clearInterval(this.resendTimerInterval);
        this.token2FAInput.value = '';
        this.result2FADiv.innerHTML = '';
        this.manualLoginForm.reset();
    }

    async handleVerifyToken() {
        const token = this.token2FAInput.value;
        const legajo = document.getElementById('legajo').value;
        if (token.length !== 6 || !/^\d{6}$/.test(token)) {
            this.showResult('Por favor, ingresa un código de 6 dígitos.', 'error', this.result2FADiv);
            return;
        }

        this.setLoading(this.verifyTokenBtn, true, 'Verificando...');

        try {
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            const response = await fetch('/totem/verify_2fa', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ legajo, token })
            });
            const result = await response.json();
            if (response.ok && result.success) {
                this.handleSuccess(result);
            } else {
                this.showResult(result.error || result.message || 'Error de verificación.', 'error', this.result2FADiv);
            }
        } catch (error) {
            this.showResult('Error de conexión con el servidor.', 'error', this.result2FADiv);
        } finally {
            this.setLoading(this.verifyTokenBtn, false, 'Verificar y Fichar');
        }
    }

    async handleResendToken() {
        const legajo = document.getElementById('legajo').value;
        this.setLoading(this.resendTokenBtn, true, 'Enviando...');
        
        try {
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            const response = await fetch('/totem/resend_2fa', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ legajo })
            });
            const result = await response.json();
            this.showResult(result.message, result.success ? 'success' : 'error', this.result2FADiv);
            if (result.success) {
                this.startResendTimer(30);
            }
        } catch (error) {
            this.showResult('Error de conexión al reenviar.', 'error', this.result2FADiv);
        } finally {
             this.setLoading(this.resendTokenBtn, false, 'Reenviar Código');
        }
    }

    startMainTimer(duration) {
        clearInterval(this.mainTimerInterval);
        let timer = duration;
        this.mainTimerInterval = setInterval(() => {
            const minutes = String(Math.floor(timer / 60)).padStart(2, '0');
            const seconds = String(timer % 60).padStart(2, '0');
            this.timer2FAElement.textContent = `${minutes}:${seconds}`;

            if (--timer < 0) {
                clearInterval(this.mainTimerInterval);
                this.showResult('El código ha expirado. Por favor, solicita uno nuevo.', 'error', this.result2FADiv);
                this.verifyTokenBtn.disabled = true;
            }
        }, 1000);
    }

    startResendTimer(duration) {
        this.resendTokenBtn.disabled = true;
        let timer = duration;
        
        // Ocultar el span del contador estático
        if (this.resendTimerElement) {
            this.resendTimerElement.style.display = 'none';
        }

        const originalText = this.resendTokenBtn.innerHTML;
        
        const updateButtonText = () => {
            if (timer > 0) {
                this.resendTokenBtn.innerHTML = `<i class="bi bi-hourglass-split me-2"></i>Reenviar en (${timer}s)`;
            } else {
                this.resendTokenBtn.innerHTML = originalText;
                this.resendTokenBtn.disabled = false;
                clearInterval(this.resendTimerInterval);
            }
        };

        updateButtonText(); // Llamada inicial

        clearInterval(this.resendTimerInterval);
        this.resendTimerInterval = setInterval(() => {
            timer--;
            updateButtonText();
        }, 1000);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new TotemLogin();
});