from flask import Blueprint, request, jsonify
from app.controllers.inventario_controller import InventarioController
from app.utils.validators import validate_uuid
from marshmallow import ValidationError
import logging

logger = logging.getLogger(__name__)

# Blueprint
inventario_bp = Blueprint('inventario_api', __name__, url_prefix='/api/inventario')

# Controlador
inventario_controller = InventarioController()

@inventario_bp.route('/lotes', methods=['POST'])
def crear_lote():
    """
    Crear un nuevo lote de inventario
    """
    try:
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Content-Type debe ser application/json'
            }), 415

        if not request.json:
            return jsonify({'success': False, 'error': 'Body JSON requerido'}), 400

        # Obtener respuesta del controlador
        response, status = inventario_controller.crear_lote(request.json)

        # ✅ CORREGIDO: Pasar solo el objeto de respuesta, no kwargs
        return jsonify(response), status

    except ValidationError as e:
        error_response = {
            'success': False,
            'error': 'Datos inválidos',
            'details': e.messages
        }
        return jsonify(error_response), 400

    except Exception as e:
        logger.error(f"Error inesperado en crear_lote: {str(e)}")
        error_response = {
            'success': False,
            'error': 'Error interno del servidor'
        }
        return jsonify(error_response), 500

@inventario_bp.route('/insumo/<string:id_insumo>/lotes', methods=['GET'])
def obtener_lotes_por_insumo(id_insumo):
    """
    Obtener lotes de un insumo específico
    ---
    GET /api/inventario/insumo/{id_insumo}/lotes?disponibles=true
    """
    try:
        if not validate_uuid(id_insumo):
            return jsonify({
                'success': False,
                'error': 'ID de insumo inválido'
            }), 400

        solo_disponibles = request.args.get('disponibles', 'true').lower() == 'true'

        response, status = inventario_controller.obtener_lotes_por_insumo(id_insumo, solo_disponibles)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_lotes_por_insumo: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

# ✅ AGREGAR ESTA RUTA FALTANTE
@inventario_bp.route('/lotes', methods=['GET'])
def obtener_lotes():
    """
    Obtener todos los lotes de inventario con filtros opcionales
    ---
    GET /api/inventario/lotes?estado=disponible&id_insumo=uuid
    """
    try:
        # Recoger parámetros de consulta
        filtros = {
            'estado': request.args.get('estado'),
            'id_insumo': request.args.get('id_insumo'),
            'ubicacion_fisica': request.args.get('ubicacion'),
            'f_vencimiento_desde': request.args.get('f_vencimiento_desde'),
            'f_vencimiento_hasta': request.args.get('f_vencimiento_hasta')
        }

        # Limpiar filtros: eliminar aquellos que son None o vacíos
        filtros = {k: v for k, v in filtros.items() if v is not None and v != ''}

        # Validar UUID si se proporciona id_insumo
        if 'id_insumo' in filtros and not validate_uuid(filtros['id_insumo']):
            return jsonify({
                'success': False,
                'error': 'ID de insumo inválido'
            }), 400

        # Llamar al controlador
        response, status = inventario_controller.obtener_lotes(filtros)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_lotes: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@inventario_bp.route('/lote/<string:id_lote>', methods=['PATCH'])
def actualizar_lote_parcial(id_lote):
    """
    Actualizar campos específicos de un lote
    ---
    PATCH /api/inventario/lote/{id_lote}
    Content-Type: application/json

    Body (actualización parcial - enviar solo los campos a modificar):
    {
        "cantidad_actual": 95.5,
        "ubicacion_fisica": "Nueva ubicación",
        "precio_unitario": 22.50,
        "f_vencimiento": "2024-12-31",
        "observaciones": "Lote reubicado"
    }
    """
    try:
        if not validate_uuid(id_lote):
            return jsonify({
                'success': False,
                'error': 'ID de lote inválido'
            }), 400

        if not request.json:
            return jsonify({'success': False, 'error': 'Body JSON requerido'}), 400

        # Validar que al menos un campo esté presente
        campos_permitidos = ['cantidad_actual', 'ubicacion_fisica', 'precio_unitario',
                           'numero_lote_proveedor', 'f_vencimiento', 'observaciones']

        campos_presentes = [campo for campo in campos_permitidos if campo in request.json]

        if not campos_presentes:
            return jsonify({
                'success': False,
                'error': f'Debe proporcionar al menos uno de estos campos: {", ".join(campos_permitidos)}'
            }), 400

        response, status = inventario_controller.actualizar_lote_parcial(id_lote, request.json)
        return jsonify(response), status

    except ValidationError as e:
        return jsonify({
            'success': False,
            'error': 'Datos inválidos',
            'details': e.messages
        }), 400
    except Exception as e:
        logger.error(f"Error inesperado en actualizar_lote_parcial: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@inventario_bp.route('/stock', methods=['GET'])
def obtener_stock_consolidado():
    """
    Obtener stock consolidado
    ---
    GET /api/inventario/stock?estado_stock=BAJO
    """
    try:
        filtros = {
            'estado_stock': request.args.get('estado_stock'),
            'es_critico': request.args.get('es_critico', '').lower() == 'true' if request.args.get('es_critico') else None
        }

        # Limpiar filtros vacíos
        filtros = {k: v for k, v in filtros.items() if v is not None and v != ''}

        response, status = inventario_controller.obtener_stock_consolidado(filtros)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_stock_consolidado: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@inventario_bp.route('/alertas', methods=['GET'])
def obtener_alertas():
    """
    Obtener alertas de inventario
    ---
    GET /api/inventario/alertas
    """
    try:
        response, status = inventario_controller.obtener_alertas()
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_alertas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500
