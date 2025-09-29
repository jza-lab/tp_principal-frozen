document.addEventListener('DOMContentLoaded', function() {
    // Variables para el manejo de pasos
    let currentStep = 1;
    const step1Element = document.getElementById('step1');
    const step2Element = document.getElementById('step2');
    const basicInfoSection = document.getElementById('basicInfo');
    const faceRegistrationSection = document.getElementById('faceRegistration');
    const nextStepBtn = document.getElementById('nextStep');
    const submitFormBtn = document.getElementById('submitForm');
    
    // Variables para la cámara
    let videoStream = null;
    let photoTaken = false;
    
    // Elementos de la cámara
    const startCameraBtn = document.getElementById('startCamera');
    const capturePhotoBtn = document.getElementById('capturePhoto');
    const confirmPhotoBtn = document.getElementById('confirmPhoto');
    const retakePhotoBtn = document.getElementById('retakePhoto');
    const retakePhotoBtn2 = document.getElementById('retakePhoto2');
    const videoElement = document.getElementById('videoElement');
    const canvasElement = document.getElementById('canvasElement');
    const capturedImage = document.getElementById('capturedImage');
    const faceDataInput = document.getElementById('faceData');
    
    // Pasar al siguiente paso
    nextStepBtn.addEventListener('click', function() {
        // Validar formulario básico
        const form = document.getElementById('userForm');
        const basicInputs = basicInfoSection.querySelectorAll('input[required], select[required]');
        let allValid = true;
        
        basicInputs.forEach(input => {
            if (!input.value.trim()) {
                allValid = false;
                input.focus();
                return;
            }
        });
        
        if (allValid) {
            // Cambiar a paso 2
            currentStep = 2;
            step1Element.classList.remove('active');
            step1Element.classList.add('completed');
            step2Element.classList.add('active');
            
            basicInfoSection.style.display = 'none';
            faceRegistrationSection.style.display = 'block';
            nextStepBtn.style.display = 'none';
            submitFormBtn.style.display = 'inline-block';
        }
    });
    
    // Iniciar cámara
    startCameraBtn.addEventListener('click', async function() {
        try {
            videoStream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    width: 320, 
                    height: 240,
                    facingMode: 'user'
                } 
            });
            videoElement.srcObject = videoStream;
            
            document.getElementById('cameraInactive').style.display = 'none';
            document.getElementById('cameraActive').style.display = 'block';
            document.getElementById('cameraSection').classList.add('active');
        } catch (error) {
            alert('Error al acceder a la cámara: ' + error.message);
        }
    });
    
    // Capturar foto
    capturePhotoBtn.addEventListener('click', function() {
        const canvas = canvasElement;
        const context = canvas.getContext('2d');
        
        canvas.width = videoElement.videoWidth;
        canvas.height = videoElement.videoHeight;
        
        context.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
        
        const imageData = canvas.toDataURL('image/jpeg', 0.8);
        capturedImage.src = imageData;
        faceDataInput.value = imageData;
        
        document.getElementById('cameraActive').style.display = 'none';
        document.getElementById('photoPreview').style.display = 'block';
        
        photoTaken = true;
    });
    
    // Confirmar foto
    confirmPhotoBtn.addEventListener('click', function() {
        // Detener stream de video
        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
        }
        
        step2Element.classList.remove('active');
        step2Element.classList.add('completed');
        
        alert('Rostro registrado exitosamente. Ahora puede crear el usuario.');
    });
    
    // Tomar otra foto
    function retakePhoto() {
        document.getElementById('photoPreview').style.display = 'none';
        document.getElementById('cameraActive').style.display = 'block';
        photoTaken = false;
        faceDataInput.value = '';
    }
    
    retakePhotoBtn.addEventListener('click', retakePhoto);
    retakePhotoBtn2.addEventListener('click', retakePhoto);
    
    // Validar antes de enviar
    document.getElementById('userForm').addEventListener('submit', function(e) {
        if (currentStep === 2 && !photoTaken) {
            e.preventDefault();
            alert('Por favor, registre su rostro antes de continuar.');
        }
    });
});

