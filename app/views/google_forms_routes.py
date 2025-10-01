from flask import Blueprint, request, jsonify, current_app
from app.controllers.pedido_controller import PedidoController
from datetime import datetime
import logging

google_forms_bp = Blueprint('google_forms', __name__)
logger = logging.getLogger(__name__)

# Instancia del controlador existente
pedido_controller = PedidoController()

@google_forms_bp.route('/api/google-forms/pedido', methods=['POST'])
def recibir_pedido_google_forms():
    """
    Endpoint para recibir pedidos desde Google Forms vía webhook
    Usa el controlador existente de pedidos
    """
    try:
        data = request.get_json()

        # 🔍 DEBUG: Ver qué está llegando realmente
        logger.info(f"📥 Datos recibidos de Google Forms: {data}")

        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibieron datos JSON'
            }), 400

        # Validar datos mínimos requeridos por tu estructura de DB
        required_fields = ['nombre_cliente', 'productos']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Campo requerido faltante: {field}'
                }), 400

        # Transformar datos de Google Forms al formato que espera tu controlador
        form_data = transformar_datos_para_controlador(data)

        # Usar el controlador existente para crear el pedido
        resultado = pedido_controller.crear_pedido_con_items(form_data)

        # El controlador retorna una tupla (response, status_code)
        response_data, status_code = resultado

        if status_code == 201:
            logger.info(f"Pedido creado exitosamente desde Google Forms: {response_data.get_json().get('data', {}).get('id')}")

        return response_data

    except Exception as e:
        logger.error(f"Error procesando pedido desde Google Forms: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno del servidor: {str(e)}'
        }), 500

def transformar_datos_para_controlador(google_data):
    """
    Transforma los datos de Google Forms al formato que espera tu controlador
    """
    # Estructura base del formulario
    form_data = {
        'nombre_cliente': google_data['nombre_cliente'],
        'fecha_solicitud': google_data.get('fecha_solicitud', datetime.now().strftime('%Y-%m-%d')),
        'estado': google_data.get('estado', 'PENDIENTE'),
        'items': []
    }

    # Campos opcionales de tu DB
    optional_fields = ['cliente_email', 'cliente_telefono', 'cliente_direccion', 'notas']
    for field in optional_fields:
        if field in google_data:
            form_data[field] = google_data[field]

    # Transformar productos/items
    productos = google_data['productos']
    if isinstance(productos, list):
        for producto in productos:
            item = {
                'producto_id': producto.get('producto_id'),
                'producto_nombre': producto.get('producto_nombre', ''),
                'cantidad': producto.get('cantidad', 1),
                'precio_unitario': producto.get('precio', 0),
                'estado': producto.get('estado', 'PENDIENTE')
            }
            # Solo agregar si tiene producto_id y cantidad válida
            if item['producto_id'] and item['cantidad'] > 0:
                form_data['items'].append(item)

    return form_data

@google_forms_bp.route('/api/google-forms/pedidos', methods=['GET'])
def listar_pedidos_google_forms():
    """Listar pedidos recibidos desde Google Forms usando el controlador existente"""
    try:
        # Usar el controlador existente con filtro por origen
        resultado = pedido_controller.obtener_pedidos(filtros={'origen': 'google_forms'})
        response_data, status_code = resultado

        return response_data

    except Exception as e:
        logger.error(f"Error obteniendo pedidos de Google Forms: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Endpoint de health check específico para Google Forms
@google_forms_bp.route('/api/google-forms/health', methods=['GET'])
def health_check_google_forms():
    """Health check para verificar que la integración está funcionando"""
    return jsonify({
        'status': 'ok',
        'service': 'google_forms_integration',
        'timestamp': datetime.now().isoformat(),
        'message': 'Integración con Google Forms funcionando correctamente'
    })