from flask import Blueprint, render_template, flash
from app.controllers.envio_controller import EnvioController
from app.utils.decorators import permission_required

envio_bp = Blueprint('envio', __name__, url_prefix='/admin/gestion-envios')
envio_controller = EnvioController()

@envio_bp.route('/')
@permission_required('gestionar_flota')
@permission_required('consultar_zonas')
def gestion_envios():
    """
    Renderiza la página de gestión de envíos, que combina la gestión de vehículos y zonas.
    """
    response = envio_controller.obtener_datos_para_vista_gestion()
    
    if not response['success']:
        flash(response.get('error', 'Ocurrió un error al cargar los datos de envíos.'), 'danger')
        # Aún así renderizamos la página con los datos que se hayan podido obtener
        datos = response.get('data', {'vehiculos': [], 'zonas': []})
    else:
        datos = response['data']
        
    return render_template('envios/gestion.html', vehiculos=datos.get('vehiculos', []), zonas=datos.get('zonas', []))
