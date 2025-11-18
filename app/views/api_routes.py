import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from app.controllers.usuario_controller import UsuarioController
from app.controllers.facial_controller import FacialController
from app.controllers.trazabilidad_controller import TrazabilidadController
from app.controllers.pago_controller import PagoController
from app.controllers.reclamo_proveedor_controller import ReclamoProveedorController
from app.utils.decorators import permission_any_of, permission_required

# Blueprint para endpoints de API interna
api_bp = Blueprint('api', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)

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

@api_bp.route('/productos/filter', methods=['GET'])
@permission_required(accion='consultar_catalogo_de_productos')
def api_filter_productos():
    """
    Endpoint de API para el filtrado dinámico de productos.
    """
    try:
        from app.controllers.producto_controller import ProductoController
        producto_controller = ProductoController()
        
        filtros = {k: v for k, v in request.args.items() if v}
        
        response, status = producto_controller.obtener_todos_los_productos(filtros)
        
        return jsonify(response), status
            
    except Exception as e:
        logger.error(f"Error en api_filter_productos: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@api_bp.route('/orden_produccion/<int:orden_id>/trazabilidad', methods=['GET'])
@permission_required(accion='consultar_trazabilidad_completa')
def get_trazabilidad_op(orden_id):
    """Devuelve la traza completa de una orden de producción."""
    controller = TrazabilidadController()
    resultado = controller.get_trazabilidad_orden_produccion(orden_id)
    if resultado.get('success'):
        return jsonify(success=True, data=resultado.get('data'))
    return jsonify(success=False, error=resultado.get('error')), 500


from app.controllers.nota_credito_controller import NotaCreditoController
from app.controllers.insumo_controller import InsumoController

@api_bp.route('/notas-credito/<int:nc_id>/detalles', methods=['GET'])
@permission_required(accion='consultar_documentos')
def get_nota_credito_detalles(nc_id):
    """
    Devuelve los detalles completos de una Nota de Crédito para usar en reportes o PDFs.
    """
    controller = NotaCreditoController()
    resultado, status_code = controller.obtener_detalles_para_pdf(nc_id)
    return jsonify(resultado), status_code

@api_bp.route('/insumos/buscar', methods=['GET'])
@permission_required(accion='registrar_ingreso_de_materia_prima')
def buscar_insumos():
    """
    Busca insumos por término de búsqueda (nombre o código) y devuelve una lista.
    Utilizado para autocompletar en formularios.
    """
    search_term = request.args.get('search', '')
    is_active = request.args.get('activo', 'true').lower() == 'true'
    
    if len(search_term) < 2:
        return jsonify({'success': False, 'error': 'El término de búsqueda debe tener al menos 2 caracteres'}), 400

    controller = InsumoController()
    filtros = {
        'search': search_term,
        'activo': is_active
    }
    
    resultado, status_code = controller.obtener_insumos(filtros)
    
    if resultado.get('success'):
        # Aseguramos que la info del proveedor venga incluida
        insumos_con_proveedor = []
        for insumo in resultado.get('data', []):
            proveedor_info, _ = controller.proveedor_model.find_by_id(insumo.get('id_proveedor'))
            if proveedor_info:
                insumo['proveedor'] = {
                    'id': proveedor_info.get('id'),
                    'nombre': proveedor_info.get('nombre')
                }
            else:
                insumo['proveedor'] = None
            insumos_con_proveedor.append(insumo)
        
        resultado['data'] = insumos_con_proveedor
    
    return jsonify(resultado), status_code

@api_bp.route('/proveedores/<int:proveedor_id>/resumen-reclamos', methods=['GET'])
@permission_required(accion='consultar_ordenes_de_compra')
def get_resumen_reclamos_proveedor(proveedor_id):
    """
    Devuelve un resumen de los reclamos de un proveedor, agrupados por motivo.
    """
    controller = ReclamoProveedorController()
    resultado, status_code = controller.get_resumen_reclamos_por_proveedor(proveedor_id)
    return jsonify(resultado), status_code

from app.controllers.orden_compra_controller import OrdenCompraController

@api_bp.route('/proveedores/<int:proveedor_id>/ordenes-compra', methods=['GET'])
@permission_required(accion='crear_reclamo_proveedor')
def get_ordenes_por_proveedor(proveedor_id):
    """
    Devuelve las órdenes de compra de un proveedor específico.
    """
    orden_controller = OrdenCompraController()
    response, _ = orden_controller.get_all_ordenes({'proveedor_id': proveedor_id})
    if response.get("success"):
        return jsonify(response.get("data", []))
    return jsonify([]), 500

@api_bp.route('/proveedores/<int:proveedor_id>/insumos', methods=['GET'])
@permission_required(accion='crear_reclamo_proveedor')
def get_insumos_por_proveedor(proveedor_id):
    """
    Devuelve los insumos asociados a un proveedor.
    Si se pasan 'orden_ids' como parámetro, filtra los insumos por esas órdenes.
    """
    insumo_controller = InsumoController()
    orden_ids = request.args.getlist('orden_ids[]')
    
    filtros = {'proveedor_id': proveedor_id}
    if orden_ids:
        filtros['orden_ids'] = orden_ids

    response, _ = insumo_controller.obtener_insumos_para_reclamo(filtros)
    
    if response.get("success"):
        return jsonify(response.get("data", []))
    
    return jsonify([]), 500

from app.controllers.pedido_controller import PedidoController

@api_bp.route('/pedidos/<int:pedido_id>/enviar-qr', methods=['POST'])
@permission_required(accion='modificar_orden_de_venta')
def enviar_qr_pedido(pedido_id):
    """
    Envía el código QR de seguimiento de un pedido por correo electrónico al cliente.
    """
    controller = PedidoController()
    resultado, status_code = controller.enviar_qr_por_email(pedido_id)
    return jsonify(resultado), status_code
@api_bp.route('/pagos/registrar', methods=['POST'])
@permission_required(accion='crear_documentos')
def registrar_pago():
    """
    Endpoint para registrar un nuevo pago para un pedido.
    """
    try:
        current_user_id = get_jwt_identity()
        if not current_user_id:
            return jsonify(success=False, error="Se requiere autenticación."), 401

        pago_data = request.form.to_dict()
        file = request.files.get('comprobante_pago')

        # El schema espera enteros, pero el form envía strings
        pago_data['id_pedido'] = int(pago_data['id_pedido'])
        pago_data['id_usuario_registro'] = int(current_user_id)
        
        # Eliminar el token CSRF antes de la validación del schema
        pago_data.pop('csrf_token', None)

        pago_controller = PagoController()
        response, status_code = pago_controller.registrar_pago(pago_data, file)
        
        return jsonify(response), status_code

    except Exception as e:
        logger.error(f"Error en endpoint registrar_pago: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Error interno del servidor al registrar el pago."}), 500
