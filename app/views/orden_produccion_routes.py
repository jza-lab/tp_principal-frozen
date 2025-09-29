from venv import logger
from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash, session
from marshmallow import ValidationError
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.producto_controller import ProductoController
from app.controllers.etapa_produccion_controller import EtapaProduccionController
from app.controllers.usuario_controller import UsuarioController
from app.controllers.receta_controller import RecetaController
from app.utils.decorators import roles_required
from datetime import date

orden_produccion_bp = Blueprint('orden_produccion', __name__, url_prefix='/ordenes')

# Se instancian los controladores necesarios
controller = OrdenProduccionController()
producto_controller = ProductoController()
etapa_controller = EtapaProduccionController()
usuario_controller = UsuarioController()
receta_controller = RecetaController()

@orden_produccion_bp.route('/')
def listar():
    """
    Muestra la lista de órdenes de producción.
    Permite filtrar por estado.
    """
    estado = request.args.get('estado')
    filtros = {'estado': estado} if estado else {}
    
    response, status_code = controller.obtener_ordenes(filtros)
    
    ordenes = []
    if response.get('success'):
        ordenes_data = response.get('data', [])
        # Ordenar: no canceladas primero, luego canceladas
        ordenes = sorted(ordenes_data, key=lambda x: x.get('estado') == 'CANCELADA')
    else:
        flash(response.get('error', 'Error al cargar las órdenes de producción.'), 'error')
        
    # El título puede variar según el filtro para dar más contexto
    titulo = f"Órdenes de Producción"
    if estado:
        titulo += f" (Estado: {estado.replace('_', ' ').title()})"
    else:
        titulo += " (Todas)"

    return render_template('ordenes_produccion/listar.html', ordenes=ordenes, titulo=titulo)

@orden_produccion_bp.route('/nueva', methods=['GET', 'POST', 'PUT'])
def nueva():
    """
    Muestra la página de detalle de una orden de producción específica,
    incluyendo sus etapas.
    """
    etapas=None 
    productos =  producto_controller.obtener_todos_los_productos()
    operarios = usuario_controller.obtener_todos_los_usuarios()
    return render_template('ordenes_produccion/formulario.html', etapas=etapas, productos=productos, operarios = operarios)
        

@orden_produccion_bp.route('/nueva/crear', methods=['POST'])
def crear():
    try:
        datos_json = request.get_json()
        if not datos_json:
            return jsonify({'success': False, 'error': 'No se recibieron datos JSON válidos.'}), 400

        usuario_id_creador = session.get('usuario_id')

        if not usuario_id_creador:
            return jsonify({'success': False, 'error': 'Usuario no autenticado.'}), 401

        # Corregido: Pasar `datos_json` al controlador, no el objeto `request`.
        resultado = controller.crear_orden(datos_json, usuario_id_creador)
        
        if resultado.get('success'):
            # Devolver el objeto creado con el código de estado 201 (Created)
            return jsonify(resultado), 201
        else:
            # Devolver el error específico con el código de estado 400 (Bad Request)
            return jsonify(resultado), 400
        
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
    

@orden_produccion_bp.route('/modificar/<int:id>', methods=['GET', 'POST', 'PUT'])
def modificar(id):
    """
    Muestra la página de detalle de una orden de producción específica,
    incluyendo sus etapas.
    """
    try:
        if(request.method == 'POST' or request.method == 'PUT'):
            datos_json = request.get_json(silent=True) 
            print(datos_json)
            if(datos_json is None):
                logger.error("Error: Se esperaba JSON, pero se recibió un cuerpo vacío o sin Content-Type: application/json")
                return jsonify({'success': False, 'error': 'No se recibieron datos JSON válidos (verifique Content-Type)'}), 400
            id = session['usuario_id']
            print(id)
            response, status = controller.crear_orden(request , 23)
            return jsonify(response), status

        orden = controller.obtener_orden_por_id(id)
        etapas=None 
        productos =  producto_controller.obtener_todos_los_productos()
        operarios = usuario_controller.obtener_todos_los_usuarios()
        return render_template('ordenes_produccion/formulario.html',orden_m=orden, etapas=etapas, productos=productos, operarios = operarios)
        
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

@orden_produccion_bp.route('/<int:id>/detalle')
def detalle(id):
    """
    Muestra la página de detalle de una orden de producción específica,
    incluyendo sus etapas y el desglose de pedidos de cliente que la componen.
    """
    respuesta = controller.obtener_orden_por_id(id)
    if not respuesta or not respuesta.get('success'):
        flash('Orden no encontrada.', 'error')
        return redirect(url_for('orden_produccion.listar'))
    
    orden = respuesta.get('data')
    etapas = None

    # Obtener desglose de origen de los pedidos
    desglose_origen = []
    desglose_response = controller.obtener_desglose_origen(id)
    if desglose_response.get('success'):
        desglose_origen = desglose_response.get('data', [])
    else:
        flash('No se pudo cargar el desglose de origen de los pedidos.', 'warning')

    ingredientes = []
    if orden and orden.get('receta_id'):
        ingredientes_response = receta_controller.obtener_ingredientes_para_receta(orden.get('receta_id'))
        if ingredientes_response.get('success'):
            ingredientes = ingredientes_response.get('data', [])
        else:
            flash(ingredientes_response.get('error', 'No se pudieron cargar los ingredientes.'), 'warning')

    return render_template('ordenes_produccion/detalle.html', 
                           orden=orden, 
                           etapas=etapas, 
                           ingredientes=ingredientes,
                           desglose_origen=desglose_origen)

@orden_produccion_bp.route('/<int:id>/iniciar', methods=['POST'])
def iniciar(id):
    """
    Endpoint para cambiar el estado de una orden a 'EN_PROCESO'.
    """
    resultado = controller.cambiar_estado_orden(id, 'EN_PROCESO')
    if resultado.get('success'):
        flash('Orden iniciada exitosamente.', 'success')
    else:
        flash(f"Error al iniciar la orden: {resultado.get('error', 'Error desconocido')}", 'error')

    return redirect(url_for('orden_produccion.detalle', id=id))

@orden_produccion_bp.route('/<int:id>/completar', methods=['POST'])
def completar(id):
    """
    Endpoint para cambiar el estado de una orden a 'COMPLETADA'.
    """
    resultado = controller.cambiar_estado_orden(id, 'COMPLETADA')
    if resultado.get('success'):
        flash('Orden completada exitosamente.', 'success')
    else:
        flash(f"Error al completar la orden: {resultado.get('error', 'Error desconocido')}", 'error')

    return redirect(url_for('orden_produccion.detalle', id=id))

@orden_produccion_bp.route('/pendientes')
@roles_required('SUPERVISOR', 'ADMIN', 'GERENTE')
def listar_pendientes():
    """
    Muestra las órdenes de producción pendientes de aprobación para el supervisor.
    """
    response, status_code = controller.obtener_ordenes({'estado': 'PENDIENTE'})

    ordenes = []
    if response.get('success'):
        ordenes = response.get('data', [])
    else:
        flash(response.get('error', 'Error al cargar las órdenes pendientes.'), 'error')
        
    return render_template('ordenes_produccion/listar.html', 
                           ordenes=ordenes, 
                           titulo="Órdenes Pendientes de Aprobación")

@orden_produccion_bp.route('/<int:id>/aprobar', methods=['POST'])
@roles_required('SUPERVISOR', 'ADMIN', 'GERENTE')
def aprobar(id):
    """
    Endpoint para que el supervisor apruebe una orden.
    """
    usuario_id = session.get('usuario_id') # Asumimos que el ID del supervisor es necesario
    resultado = controller.aprobar_orden(id, usuario_id)
    if resultado.get('success'):
        flash('Orden aprobada y stock reservado.', 'success')
    else:
        flash(f"Error al aprobar: {resultado.get('error', 'Error desconocido')}", 'error')
    return redirect(url_for('orden_produccion.listar'))

@orden_produccion_bp.route('/<int:id>/rechazar', methods=['POST'])
@roles_required('SUPERVISOR', 'ADMIN', 'GERENTE')
def rechazar(id):
    """
    Endpoint para que el supervisor rechace una orden.
    """
    motivo = request.form.get('motivo', 'No especificado')
    resultado = controller.rechazar_orden(id, motivo)
    if resultado.get('success'):
        flash('Orden rechazada exitosamente.', 'warning')
    else:
        flash(f"Error al rechazar: {resultado.get('error', 'Error desconocido')}", 'error')
    return redirect(url_for('orden_produccion.listar'))