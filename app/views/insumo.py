from flask import Blueprint, redirect, render_template, request, jsonify, session, url_for, flash
from app.controllers.insumo_controller import InsumoController
from app.controllers.inventario_controller import InventarioController
from app.controllers.proveedor_controller import ProveedorController
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.usuario_controller import UsuarioController
from app.utils.validators import validate_uuid
from marshmallow import ValidationError
import logging
from datetime import datetime # Importación de datetime para manejar las fechas

logger = logging.getLogger(__name__)

# Blueprint
insumos_bp = Blueprint('insumos_api', __name__, url_prefix='/api/insumos')

# Controlador
insumo_controller = InsumoController()
proveedor_controller = ProveedorController()
ordenes_compra_controller = OrdenCompraController()
inventario_controller= InventarioController()
usuario_controller = UsuarioController()


@insumos_bp.route('/catalogo/nuevo', methods=['GET', 'POST'])
def crear_insumo():
    try:
        if request.method == 'POST':
            datos_json = request.get_json()
            if not datos_json:
                logger.error("Error: Se esperaba JSON, pero se recibió un cuerpo vacío o sin Content-Type: application/json")
                return jsonify({'success': False, 'error': 'No se recibieron datos JSON válidos (verifique Content-Type)'}), 400

            response, status = insumo_controller.crear_insumo(datos_json)
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
        print(insumo)
        lotes_response, lotes_status = inventario_controller.obtener_lotes_por_insumo(id_insumo, solo_disponibles=False)
        lotes = lotes_response.get('data', []) if lotes_status == 200 else []
        return render_template('insumos/perfil_insumo.html', insumo=insumo, lotes=lotes)

    except Exception as e:
        logger.error(f"Error inesperado en obtener_insumo_por_id: {str(e)}")
        return redirect(url_for('insumos_api.obtener_insumos'))

@insumos_bp.route('/catalogo/actualizar/<string:id_insumo>', methods=['GET', 'POST', 'PUT'])
def actualizar_insumo(id_insumo):
    """
    Actualizar un insumo del catálogo
    ---
    POST /api/insumos/catalogo/actualizar/{id_insumo}
    Content-Type: application/json
    """

    try:
        if not validate_uuid(id_insumo):
            return jsonify({
                'success': False,
                'error': 'ID de insumo inválido'
            }), 400
        
        if request.method == 'POST' or request.method == 'PUT':
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

@insumos_bp.route('/catalogo/habilitar/<string:id_insumo>', methods=['POST'])
def habilitar_insumo(id_insumo):
    """
    Habilitar un insumo del catálogo
    ---
    POST /api/insumos/catalogo/habilitar/{id_insumo}
    """
    try:
        if not validate_uuid(id_insumo):
            return jsonify({
                'success': False,
                'error': 'ID de insumo inválido'
            }), 400

        response, status = insumo_controller.habilitar_insumo(id_insumo)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en habilitar_insumo: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@insumos_bp.route('/catalogo/lote/nuevo/<string:id_insumo>', methods = ['GET', 'POST'])
def agregar_lote(id_insumo):
    proveedores_resp, _ = proveedor_controller.obtener_proveedores_activos()
    proveedores = proveedores_resp.get('data', []) if proveedores_resp.get('success') else []
    
    response, status = insumo_controller.obtener_insumo_por_id(id_insumo)
    insumo = response['data']
    
    ordenes_compra_resp, _ = ordenes_compra_controller.obtener_codigos_por_insumo(id_insumo)
    ordenes_compra_data = ordenes_compra_resp.get('data', []) if ordenes_compra_resp.get('success') else []

    # FIX: Definir 'today' y pasar 'lote={}' para evitar UndefinedError en el template
    today = datetime.now().strftime('%Y-%m-%d')
    
    return render_template(
        'insumos/registrar_lote.html', 
        insumo=insumo, 
        proveedores=proveedores, 
        ordenes=ordenes_compra_data, 
        is_edit=False,
        lote={}, # <-- Solución: Pasamos un diccionario vacío
        today=today # <-- Solución: Pasamos la fecha de hoy
    )

@insumos_bp.route('/catalogo/lote/nuevo/<string:id_insumo>/crear', methods = ['GET','POST'])
def crear_lote(id_insumo):
    try:
        datos_json = request.get_json()
        if not datos_json:
            logger.error("Error: Se esperaba JSON, pero se recibió un cuerpo vacío o sin Content-Type: application/json")
            return jsonify({'success': False, 'error': 'No se recibieron datos JSON válidos (verifique Content-Type)'}), 400
        
        id = session['usuario_id']
        response, status = inventario_controller.crear_lote(datos_json, id)
        print(response, status)
        return jsonify(response), status

    except ValidationError as e:
        return jsonify({
            'success': False,
            'error': 'Datos inválidos',
            'details': e.messages
        }), 400
    except Exception as e:
        logger.error(f"Error inesperado en crear_lote: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@insumos_bp.route('/catalogo/lote/editar/<string:id_insumo>/<string:id_lote>', methods=['GET'])
def editar_lote(id_insumo, id_lote):
    """Renderiza el formulario para editar un lote existente."""
    def parse_date_for_template(date_str):
        if not date_str: return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        except Exception:
            return date_str

    try:
        if not validate_uuid(id_insumo) or not validate_uuid(id_lote):
            return "ID de insumo o lote inválido", 400

        # Obtener datos para el formulario
        proveedores_resp, _ = proveedor_controller.obtener_proveedores_activos()
        proveedores = proveedores_resp.get('data', [])
        ordenes_compra_resp, _ = ordenes_compra_controller.obtener_codigos_por_insumo(id_insumo)
        ordenes_compra_data = ordenes_compra_resp.get('data', [])

        # Obtener datos del insumo y del lote
        insumo_resp, insumo_status = insumo_controller.obtener_insumo_por_id(id_insumo)
        lote_resp, lote_status = inventario_controller.obtener_lote_por_id(id_lote)

        if insumo_status != 200 or lote_status != 200:
            logger.error(f"Datos no encontrados para insumo ({id_insumo}) o lote ({id_lote}).")
            return "Insumo o lote no encontrado", 404

        insumo_data = insumo_resp.get('data')
        lote_data = lote_resp.get('data')

        # Formatear fechas para el template
        if lote_data:
            lote_data['f_ingreso'] = parse_date_for_template(lote_data.get('f_ingreso'))
            lote_data['f_vencimiento'] = parse_date_for_template(lote_data.get('f_vencimiento'))

        return render_template(
            'insumos/registrar_lote.html',
            insumo=insumo_data,
            lote=lote_data,
            proveedores=proveedores,
            ordenes=ordenes_compra_data,
            is_edit=True
        )

    except Exception as e:
        logger.exception(f"Error CRÍTICO en editar_lote (GET) para insumo={id_insumo}, lote={id_lote}.")
        return "Error interno del servidor", 500


@insumos_bp.route('/catalogo/lote/editar/<string:id_insumo>/<string:id_lote>', methods=['PUT'])
def actualizar_lote_api(id_insumo, id_lote):
    """API endpoint para actualizar un lote."""
    try:
        if not validate_uuid(id_lote):
            return jsonify({'success': False, 'error': 'ID de lote inválido'}), 400
        
        datos_json = request.get_json()
        if not datos_json:
            return jsonify({'success': False, 'error': 'Cuerpo JSON requerido'}), 400

        response, status = inventario_controller.actualizar_lote_parcial(id_lote, datos_json)
        return jsonify(response), status

    except ValidationError as e:
        return jsonify({'success': False, 'error': 'Datos inválidos', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error inesperado en actualizar_lote_api: {e}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

@insumos_bp.route('/catalogo/lote/eliminar/<string:id_insumo>/<string:id_lote>', methods=['POST'])
def eliminar_lote(id_insumo, id_lote):
    try:
        if not validate_uuid(id_lote) or not validate_uuid(id_insumo):
            flash('ID de lote o insumo inválido.', 'error')
            return redirect(url_for('insumos_api.obtener_insumos'))

        response, status = inventario_controller.eliminar_lote(id_lote)
        
        if status == 200:
            flash('Lote eliminado correctamente.', 'success')
        else:
            error_message = response.get('error', 'Ocurrió un error al eliminar el lote.')
            flash(error_message, 'error')

        return redirect(url_for('insumos_api.obtener_insumo_por_id', id_insumo=id_insumo))

    except Exception as e:
        logger.error(f"Error inesperado en eliminar_lote: {e}")
        flash('Error interno del servidor al intentar eliminar el lote.', 'error')
        return redirect(url_for('insumos_api.obtener_insumo_por_id', id_insumo=id_insumo))


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
