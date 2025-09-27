import json
from flask import Blueprint, redirect, render_template, request, jsonify, url_for
from app.controllers.insumo_controller import InsumoController
from app.utils.validators import validate_uuid, validate_pagination
from marshmallow import ValidationError
import logging

logger = logging.getLogger(__name__)

# Blueprint
insumos_bp = Blueprint('insumos_api', __name__, url_prefix='/api/insumos')

# Controlador
insumo_controller = InsumoController()

@insumos_bp.route('/catalogo/nuevo', methods=['GET','PUT' ,'POST'])
def crear_insumo():
    """
    Crear un nuevo insumo en el catálogo
    ---
    POST /api/insumos/catalogo
    Content-Type: application/json

    Body:
    {
        "nombre": "string (required)",
        "codigo_interno": "string (optional)",
        "unidad_medida": "string (required)",
        "categoria": "string (optional)",
        "stock_min": "integer (default: 0)"
    }
    """
    try:

        if(request.method == 'POST' or request.method == 'PUT'):
            datos_json = request.get_json(silent=True) 
            if(datos_json is None):
                logger.error("Error: Se esperaba JSON, pero se recibió un cuerpo vacío o sin Content-Type: application/json")
                return jsonify({'success': False, 'error': 'No se recibieron datos JSON válidos (verifique Content-Type)'}), 400
    

            response, status = insumo_controller.crear_insumo(request.json)
            return jsonify(response), status
        
        insumo=None
        return render_template('insumos/formulario.html', insumo=insumo)

    except ValidationError as e:
        return jsonify({
            'success': False,
            'error': 'Datos inválidos',
            'details': e.messages
        }), 400
    except Exception as e:
        logger.error(f"Error inesperado en crear_insumo: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@insumos_bp.route('/catalogo', methods=['GET'])
def obtener_insumos():
    """
    Obtener lista de insumos con filtros opcionales
    ---
    GET /api/insumos/catalogo?activo=true&categoria=string&busqueda=string
    """
    try:
        filtros = {
            'activo': request.args.get('activo', 'true').lower() == 'true',
            'categoria': request.args.get('categoria'),
            'es_critico': request.args.get('es_critico', '').lower() == 'true' if request.args.get('es_critico') else None,
            'busqueda': request.args.get('busqueda')
        }

        # Limpiar filtros vacíos
        filtros = {k: v for k, v in filtros.items() if v is not None and v != ''}
        response, status= insumo_controller.obtener_insumos(filtros)
        insumos=response['data']

        return render_template('insumos/listar.html', insumos=insumos)

    except Exception as e:
        logger.error(f"Error inesperado en obtener_insumos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@insumos_bp.route('/catalogo/<string:id_insumo>', methods=['GET'])
def obtener_insumo_por_id(id_insumo):
    """
    Obtener un insumo específico por ID
    ---
    GET /api/insumos/catalogo/{id_insumo}
    """
    try:
        if not validate_uuid(id_insumo):
            return jsonify({
                'success': False,
                'error': 'ID de insumo inválido'
            }), 400

        response, status = insumo_controller.obtener_insumo_por_id(id_insumo)
        insumo = response['data']
        return render_template('insumos/perfil_insumo.html', insumo=insumo)

    except Exception as e:
        logger.error(f"Error inesperado en obtener_insumo_por_id: {str(e)}")
        return redirect(url_for('insumos_api.obtener_insumos'))

@insumos_bp.route('/catalogo/actualizar/<string:id_insumo>', methods=['GET', 'POST' , 'PUT'])
def actualizar_insumo(id_insumo):
    """
    Actualizar un insumo del catálogo
    ---
    PUT /api/insumos/catalogo/{id_insumo}
    Content-Type: application/json
    """
    try:
        if not validate_uuid(id_insumo):
            return jsonify({
                'success': False,
                'error': 'ID de insumo inválido'
            }), 400
        
        if(request.method == 'POST' or request.method == 'PUT'):
            datos_json = request.get_json(silent=True) 
            if(datos_json is None):
                logger.error("Error: Se esperaba JSON, pero se recibió un cuerpo vacío o sin Content-Type: application/json")
                return jsonify({'success': False, 'error': 'No se recibieron datos JSON válidos (verifique Content-Type)'}), 400
    
            response, status = insumo_controller.actualizar_insumo(id_insumo, datos_json)
            return jsonify(response), status

        response, status = insumo_controller.obtener_insumo_por_id(id_insumo)
        insumo = response['data']
        return render_template('insumos/formulario.html', insumo=insumo)

    except ValidationError as e:
        return jsonify({
            'success': False,
            'error': 'Datos inválidos',
            'details': e.messages
        }), 400
    except Exception as e:
        logger.error(f"Error inesperado en actualizar_insumo: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@insumos_bp.route('/catalogo/eliminar/<string:id_insumo>', methods=['DELETE'])
def eliminar_insumo(id_insumo):
    """
    Eliminar un insumo del catálogo
    ---
    DELETE /api/insumos/catalogo/eliminar/{id_insumo}?forzar=false
    """
    try:
        if not validate_uuid(id_insumo):
            return jsonify({
                'success': False,
                'error': 'ID de insumo inválido'
            }), 400

        forzar = request.args.get('forzar', 'false').lower() == 'true'

        response, status = insumo_controller.eliminar_insumo_logico(id_insumo)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en eliminar_insumo: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@insumos_bp.route('/stock', methods=['GET'])
def obtener_stock_consolidado():
    """
    Obtener stock consolidado con alertas
    ---
    GET /api/insumos/stock?estado_stock=BAJO&es_critico=true
    """
    try:
        filtros = {
            'estado_stock': request.args.get('estado_stock'),
            'es_critico': request.args.get('es_critico', '').lower() == 'true' if request.args.get('es_critico') else None
        }

        # Limpiar filtros vacíos
        filtros = {k: v for k, v in filtros.items() if v is not None and v != ''}

        response, status = insumo_controller.obtener_con_stock(filtros)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_stock_consolidado: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500
