document.addEventListener('DOMContentLoaded', function () {
    video = document.getElementById("video");

    navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        .then(function (stream) {

            video.srcObject = stream;
            video.setPointerCapture(0);
            video.play();
        })
        .catch(function (err) {
            console.log("An error occurred! " + err);
        });

    const boton_inicioSesionCamara = document.getElementById("botonCamara")
    const formulario_inicioSesion = document.getElementById("credenciales")
    const area_reconocimientoFacial = document.getElementById("areaRecoFacial")
    const boton_verificarRostro = document.getElementById("botonVerificarRostro")
    const mensajeGuia = this.getElementById("guia")

    boton_inicioSesionCamara.addEventListener('click', () => {
        boton_inicioSesionCamara.style.display = 'none';
        area_reconocimientoFacial.style.display = 'block';
    })

    boton_verificarRostro.addEventListener('click', () => {
        area_reconocimientoFacial.style.display = 'none';
        mensajeGuia.style.display = 'none'
        const canvas = document.getElementById("canvas");
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Convertir a dataURL (base64)
        const imageDataUrl = canvas.toDataURL("image/jpeg");

        // Enviar al backend
        fetch("/auth/identificar_rostro", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image: imageDataUrl })
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                       window.location.href = data.redirect
                } else {
                    boton_inicioSesionCamara.style.display = 'none';
                    area_reconocimientoFacial.style.display='none'
                    formulario_inicioSesion.style.display = 'block';
                    alert(data.message);
                }
            })
            .catch(err => {
                console.error("Error:", err);
            });

            

        


    })
})