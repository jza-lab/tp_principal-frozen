from flask import Blueprint, jsonify, request
from app.controllers.usuario_controller import UsuarioController
from app.controllers.facial_controller import FacialController
from app.controllers.trazabilidad_controller import TrazabilidadController
from app.utils.decorators import permission_any_of, permission_required

# Blueprint para endpoints de API interna
api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/usuarios/actividad_totem', methods=['GET'])
@permission_required(accion='consultar_logs_o_auditoria')
def obtener_actividad_totem():
    """Devuelve la actividad del tótem en formato JSON."""
    filtros = {
        'sector_id': request.args.get('sector_id') if request.args.get('sector_id') else None,
        'fecha_desde': request.args.get('fecha_desde') if request.args.get('fecha_desde') else None,
        'fecha_hasta': request.args.get('fecha_hasta') if request.args.get('fecha_hasta') else None,
    }
    usuario_controller = UsuarioController()
    resultado = usuario_controller.obtener_actividad_totem(filtros)
    if resultado.get('success'):
        return jsonify(success=True, data=resultado.get('data', []))
    return jsonify(success=False, error=resultado.get('error')), 500

@api_bp.route('/usuarios/actividad_web', methods=['GET'])
@permission_required(accion='consultar_logs_o_auditoria')
def obtener_actividad_web():
    """Devuelve la actividad web en formato JSON."""
    filtros = {
        'sector_id': request.args.get('sector_id') if request.args.get('sector_id') else None,
        'fecha_desde': request.args.get('fecha_desde') if request.args.get('fecha_desde') else None,
        'fecha_hasta': request.args.get('fecha_hasta') if request.args.get('fecha_hasta') else None,
    }
    usuario_controller = UsuarioController()
    resultado = usuario_controller.obtener_actividad_web(filtros)
    if resultado.get('success'):
        return jsonify(success=True, data=resultado.get('data', []))
    return jsonify(success=False, error=resultado.get('error')), 500

@api_bp.route('/usuarios/actividad_unificada', methods=['GET'])
@permission_required(accion='consultar_logs_o_auditoria')
def obtener_actividad_unificada():
    """Devuelve la actividad unificada en formato JSON."""
    filtros = {
        'sector_id': request.args.get('sector_id') if request.args.get('sector_id') else None,
        'fecha_desde': request.args.get('fecha_desde') if request.args.get('fecha_desde') else None,
        'fecha_hasta': request.args.get('fecha_hasta') if request.args.get('fecha_hasta') else None,
        'rol_id': request.args.get('rol_id') if request.args.get('rol_id') else None,
    }
    usuario_controller = UsuarioController()
    resultado = usuario_controller.obtener_actividad_unificada(filtros)
    if resultado.get('success'):
        return jsonify(success=True, data=resultado.get('data', []))
    return jsonify(success=False, error=resultado.get('error')), 500

@api_bp.route('/validar/campo_usuario', methods=['POST'])
@permission_any_of('crear_empleado', 'modificar_empleado')
def validar_campo_usuario():
    """Valida de forma asíncrona si un campo de usuario ya existe."""
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')
    user_id = data.get('user_id')

    if not field or not value:
        return jsonify({'valid': False, 'error': 'Campo o valor no proporcionado.'}), 400

    usuario_controller = UsuarioController()
    resultado = usuario_controller.validar_campo_unico(field, value, user_id)
    return jsonify(resultado)

@api_bp.route('/validar/rostro', methods=['POST'])
@permission_required(accion='crear_empleado')
def validar_rostro():
    """Valida si el rostro en una imagen es válido y no está duplicado."""
    data = request.get_json()
    image_data = data.get('image')
    
    if not image_data:
        return jsonify({'valid': False, 'message': 'No se proporcionó imagen.'}), 400
    
    facial_controller = FacialController()
    resultado = facial_controller.validar_y_codificar_rostro(image_data)
    if resultado.get('success'):
        return jsonify({'valid': True, 'message': 'Rostro válido y disponible.'})
    
    return jsonify({'valid': False, 'message': resultado.get('message')})

@api_bp.route('/validar/direccion', methods=['POST'])
def validar_direccion():
    """Verifica una dirección en tiempo real usando Georef."""
    data = request.get_json()
    calle = data.get('calle')
    altura = data.get('altura')
    localidad = data.get('localidad')
    provincia = data.get('provincia')

    if not all([calle, altura, localidad, provincia]):
        return jsonify(success=False, message='Todos los campos son requeridos.'), 400

    usuario_controller = UsuarioController()
    georef_controller = usuario_controller.usuario_direccion_controller
    full_street = f"{calle} {altura}"
    
    resultado = georef_controller.normalizar_direccion(
        direccion=full_street,
        localidad=localidad,
        provincia=provincia
    )
    return jsonify(resultado)

@api_bp.route('/turnos_para_autorizacion', methods=['GET'])
@permission_required(accion='consultar_empleados') 
def get_turnos_para_autorizacion():
    """
    Obtiene una lista de turnos filtrada según el tipo de autorización.
    """
    tipo_autorizacion = request.args.get('tipo', '')
    if not tipo_autorizacion:
        return jsonify({'success': False, 'error': 'El parámetro "tipo" es requerido.'}), 400

    usuario_controller = UsuarioController()
    resultado = usuario_controller.obtener_turnos_para_autorizacion(tipo_autorizacion)
    
    if resultado.get('success'):
        return jsonify(resultado)
    
    return jsonify({'success': False, 'error': resultado.get('error', 'Error interno del servidor')}), 500

@api_bp.route('/usuarios/buscar', methods=['GET'])
@permission_required(accion='consultar_empleados')
def buscar_usuario_por_legajo():
    """
    Busca un usuario por su legajo y devuelve sus datos básicos.
    Utilizado para la búsqueda dinámica en el formulario de autorizaciones.
    """
    legajo = request.args.get('legajo')
    if not legajo:
        return jsonify({'success': False, 'error': 'El parámetro "legajo" es requerido.'}), 400

    usuario_controller = UsuarioController()
    resultado = usuario_controller.buscar_por_legajo_para_api(legajo)
    
    if resultado.get('success'):
        return jsonify(resultado)
    
    return jsonify({'success': False, 'error': resultado.get('error', 'Usuario no encontrado')}), 404

@api_bp.route('/orden_produccion/<int:orden_id>/trazabilidad', methods=['GET'])
@permission_required(accion='consultar_trazabilidad')
def get_trazabilidad_op(orden_id):
    """Devuelve la traza completa de una orden de producción."""
    controller = TrazabilidadController()
    resultado = controller.get_trazabilidad_orden_produccion(orden_id)
    if resultado.get('success'):
        return jsonify(success=True, data=resultado.get('data'))
    return jsonify(success=False, error=resultado.get('error')), 500


from app.controllers.nota_credito_controller import NotaCreditoController

@api_bp.route('/notas-credito/<int:nc_id>/detalles', methods=['GET'])
@permission_required(accion='consultar_documentos')
def get_nota_credito_detalles(nc_id):
    """
    Devuelve los detalles completos de una Nota de Crédito para usar en reportes o PDFs.
    """
    controller = NotaCreditoController()
    resultado, status_code = controller.obtener_detalles_para_pdf(nc_id)
    return jsonify(resultado), status_code