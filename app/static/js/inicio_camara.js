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
    const area_reconocimientoFacial= document.getElementById("areaRecoFacial")
    const boton_verificarRostro=document.getElementById("botonVerificarRostro")
    const mensajeGuia=this.getElementById("guia")

    boton_inicioSesionCamara.addEventListener('click', ()=> {
        boton_inicioSesionCamara.style.display = 'none';
        area_reconocimientoFacial.style.display = 'block';
    })
    boton_verificarRostro.addEventListener('click',()=>{
        area_reconocimientoFacial.style.display = 'none';
        mensajeGuia.style.display='none'

        //Ingresar función/Codigo para que inicio o no sesión
        formulario_inicioSesion.style.display= 'block';


    })
})