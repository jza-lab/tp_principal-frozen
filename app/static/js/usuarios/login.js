
class ModernLogin {
    constructor() {
        this.video = document.getElementById('video');
        this.canvas = document.getElementById('canvas');
        this.botonVerificarRostro = document.getElementById('botonVerificarRostro');
        this.areaReconocimientoFacial = document.getElementById('areaReconocimientoFacial');
        this.credenciales = document.getElementById('credenciales');
        this.manualLoginBtn = document.getElementById('manualLoginBtn');
        this.retryFacialBtn = document.getElementById('retryFacialBtn');
        this.backToFacialBtn = document.getElementById('backToFacialBtn');
        this.facialResultDiv = document.getElementById('facialResult');
        this.alternativeOptions = document.getElementById('alternativeOptions');
        this.stream = null;
        this.failedAttempts = 0;
        this.maxAttempts = 2;

        this.init();
    }

    async init() {
        try {
            await this.activarCamara();
            this.botonVerificarRostro.addEventListener('click', () => this.iniciarSesionFacial());
            this.manualLoginBtn.addEventListener('click', () => this.mostrarCredenciales());
            this.retryFacialBtn.addEventListener('click', () => this.reintentar());
            this.backToFacialBtn.addEventListener('click', () => this.volverAFacial());
        } catch (error) {
            console.error("Error fatal durante la inicialización:", error);
            this.mostrarMensajeFacial("Ocurrió un error al iniciar. Por favor, use el acceso manual.", "error");
            this.mostrarOpcionesAlternativas();
        }
    }

    async activarCamara() {
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
            console.error('Error al acceder a la cámara:', err);
            this.mostrarMensajeFacial('No se pudo acceder a la cámara. Use el acceso manual.', 'warning');
            this.mostrarOpcionesAlternativas();
        }
    }

    async iniciarSesionFacial() {
        if (!this.stream) {
            this.mostrarMensajeFacial('Cámara no disponible', 'error');
            this.mostrarOpcionesAlternativas();
            return;
        }

        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;
        const ctx = this.canvas.getContext('2d');
        ctx.drawImage(this.video, 0, 0);
        
        const imageData = this.canvas.toDataURL('image/jpeg', 0.8);
        
        this.botonVerificarRostro.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Verificando...';
        this.botonVerificarRostro.disabled = true;
        
        try {
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;

            const response = await fetch('/auth/identificar_rostro', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ image: imageData })
            });
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.message || `Error del servidor: ${response.status}`);
            }

            if (result.success) {
                this.mostrarMensajeFacial(`${result.message || 'Acceso concedido'}`, 'success');
                if (this.stream) {
                    this.stream.getTracks().forEach(track => track.stop());
                }
                setTimeout(() => {
                    window.location.href = result.redirect;
                }, 1500);
            } else {
                throw new Error(result.message || 'No se pudo verificar el rostro.');
            }
        } catch (error) {
            this.failedAttempts++;
            console.error('Error en reconocimiento facial:', error.message);
            this.mostrarMensajeFacial(error.message, 'error');
            
            if (this.failedAttempts >= this.maxAttempts) {
                this.mostrarOpcionesAlternativas();
            }
        } finally {
            this.botonVerificarRostro.innerHTML = '<i class="bi bi-camera me-2"></i>Iniciar Sesión';
            this.botonVerificarRostro.disabled = false;
        }
    }

    mostrarOpcionesAlternativas() {
        this.alternativeOptions.style.display = 'block';
        document.getElementById('guiaFacial').innerHTML = '<span class="text-warning"><i class="bi bi-exclamation-triangle me-1"></i>No se pudo verificar el rostro</span>';
    }

    reintentar() {
        this.failedAttempts = 0;
        this.alternativeOptions.style.display = 'none';
        this.facialResultDiv.innerHTML = '';
        document.getElementById('guiaFacial').textContent = 'Posiciona tu rostro en el centro para iniciar sesión';
        
        if (!this.stream) {
            this.activarCamara();
        }
    }

    mostrarCredenciales() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        this.areaReconocimientoFacial.style.display = 'none';
        this.credenciales.style.display = 'block';
    }

    volverAFacial() {
        this.credenciales.style.display = 'none';
        this.areaReconocimientoFacial.style.display = 'block';
        
        this.reintentar();
        this.activarCamara();
    }

    mostrarMensajeFacial(message, type) {
        const alertClass = type === 'success' ? 'alert-success' : 
                          type === 'error' ? 'alert-danger' : 
                          type === 'warning' ? 'alert-warning' : 'alert-info';
        
        this.facialResultDiv.innerHTML = `
            <div class="alert ${alertClass} alert-dismissible fade show">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

        if (type === 'error' || type === 'warning') {
            setTimeout(() => {
                const alert = this.facialResultDiv.querySelector('.alert');
                if (alert) {
                    alert.classList.remove('show');
                    setTimeout(() => {
                        this.facialResultDiv.innerHTML = '';
                    }, 150);
                }
            }, 5000);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ModernLogin();
});
