from flask import Blueprint, request, jsonify, current_app
from app.controllers.pedido_controller import PedidoController
from datetime import datetime
import logging
import traceback  # ⬅️ AGREGAR ESTA IMPORTACIÓN
import json

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

        # 🔍 DEBUG DETALLADO
        logger.info("=" * 50)
        logger.info("📥 DATOS RECIBIDOS DE GOOGLE FORMS")
        logger.info("=" * 50)
        logger.info(f"Tipo de datos: {type(data)}")
        logger.info(f"Keys disponibles: {list(data.keys()) if data else 'No data'}")
        logger.info(f"Contenido completo: {data}")

        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibieron datos JSON'
            }), 400

        # Validar datos mínimos
        if 'nombre_cliente' not in data:
            logger.error("❌ FALTA: nombre_cliente")
            return jsonify({
                'success': False,
                'error': 'Campo requerido faltante: nombre_cliente'
            }), 400

        # Transformar datos
        form_data = transformar_datos_para_controlador(data)

        logger.info("🔄 DATOS TRANSFORMADOS:")
        logger.info(f"Form data: {form_data}")
        logger.info(f"Items count: {len(form_data.get('items', []))}")

        # 🔍 DEBUG: Verificar el schema ANTES de llamar al controlador
        debug_schema_validation(form_data)

        # Usar el controlador existente para crear el pedido
        resultado = pedido_controller.crear_pedido_con_items(form_data)

        # 🔍 DEBUG MEJORADO de la respuesta del controlador
        logger.info(f"📤 RESPUESTA DEL CONTROLADOR:")
        logger.info(f"Tipo de resultado: {type(resultado)}")

        # Manejar diferentes tipos de retorno del controlador
        if isinstance(resultado, tuple):
            response_data, status_code = resultado
            logger.info(f"Status: {status_code}")
            if hasattr(response_data, 'get_json'):
                logger.info(f"Data: {response_data.get_json()}")
            else:
                logger.info(f"Data: {response_data}")
            return response_data
        else:
            # Si el controlador retorna solo un dict
            logger.info(f"Data (dict): {resultado}")
            return jsonify(resultado)

    except Exception as e:
        logger.error(f"❌ ERROR GENERAL: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'Error interno del servidor: {str(e)}'
        }), 500

def transformar_datos_para_controlador(google_data):
    """
    Transforma los datos de Google Forms al formato que espera tu controlador
    SOLO incluye campos que el schema permite
    """
    logger.info("🎯 INICIANDO TRANSFORMACIÓN")

    # 🔥 SOLO campos que el schema permite
    form_data = {
        'nombre_cliente': google_data.get('nombre_cliente', ''),
        'fecha_solicitud': google_data.get('fecha_solicitud', datetime.now().strftime('%Y-%m-%d')),
        'estado': google_data.get('estado', 'PENDIENTE'),
        'items': []
    }

    # 🔥 Campos que el schema NO permite - los omitimos
    # 'cliente_email', 'cliente_telefono', 'cliente_direccion', 'notas'
    # 'items-TOTAL_FORMS', etc. - NO los incluyas

    # Procesar productos - SOLO campos permitidos en items
    if 'productos' in google_data:
        productos = google_data['productos']
        logger.info(f"🛍️ PRODUCTOS ENCONTRADOS: {len(productos)}")

        for i, producto in enumerate(productos):
            logger.info(f"   Producto {i+1}: {producto}")

            if not producto.get('producto_id') or not producto.get('cantidad'):
                continue

            try:
                cantidad = int(producto.get('cantidad', 0))
                if cantidad <= 0:
                    continue

                # 🔥 SOLO campos que el schema permite en items
                item = {
                    'producto_id': producto['producto_id'],
                    'cantidad': cantidad
                    # ❌ NO incluir: 'estado', 'producto_nombre', 'precio_unitario'
                }

                form_data['items'].append(item)
                logger.info(f"   ✅ Item agregado (solo campos schema): {item}")

            except (ValueError, TypeError) as e:
                logger.error(f"   ❌ Error procesando producto: {e}")
                continue
    else:
        logger.warning("⚠️ NO se encontró el campo 'productos'")

    logger.info(f"📋 FORMATO FINAL - Items: {len(form_data['items'])}")
    logger.info(f"📋 Campos finales: {list(form_data.keys())}")
    return form_data

def debug_schema_validation(form_data):
    """
    Función para debug del schema de validación
    """
    try:
        logger.info("🔍 VALIDANDO SCHEMA...")

        # Probar la validación directamente
        from marshmallow import ValidationError

        try:
            # Intentar validar con el schema del controlador
            validated_data = pedido_controller.schema.load(form_data)
            logger.info("✅ SCHEMA VALIDACIÓN: Datos son válidos")
            logger.info(f"   Datos validados: {validated_data}")
            return True

        except ValidationError as e:
            logger.error(f"❌ ERROR VALIDACIÓN SCHEMA: {e.messages}")
            logger.error(f"   Datos que fallaron: {form_data}")
            return False

    except Exception as e:
        logger.error(f"❌ ERROR EN DEBUG SCHEMA: {str(e)}")
        return False

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