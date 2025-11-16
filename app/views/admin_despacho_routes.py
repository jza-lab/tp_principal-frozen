from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.controllers.despacho_controller import DespachoController
from datetime import datetime
from app.controllers.vehiculo_controller import VehiculoController
from app.utils.decorators import permission_required
import json
from app.json_encoder import CustomJSONEncoder
from collections import defaultdict

despacho_bp = Blueprint('despacho', __name__, url_prefix='/admin/despachos')
despacho_controller = DespachoController()
vehiculo_controller = VehiculoController()

@despacho_bp.route('/')
@permission_required('consultar_despachos')
def listar_despachos():
    response = despacho_controller.get_all()
    if response['success']:
        despachos = response['data']
    else:
        flash(response.get('error', 'Error al cargar los despachos.'), 'danger')
        despachos = []
    return render_template('despachos/listar.html', despachos=despachos)

@despacho_bp.route('/gestion', methods=['GET'])
@permission_required('crear_despachos')
def gestion_despachos_vista():
    """
    Muestra la interfaz de gestión de despachos con pestañas para creación (mapa)
    e historial.
    """
    # 1. Obtener pedidos listos para despachar (para la pestaña de creación)
    response_pedidos = despacho_controller.obtener_pedidos_para_despacho()
    if not response_pedidos['success']:
        flash(response_pedidos['error'], 'danger')
        pedidos = []
    else:
        pedidos = response_pedidos['data']

    # 2. Obtener historial de despachos (para la pestaña de historial)
    response_despachos, _ = despacho_controller.get_all()
    if response_despachos.get('success'):
        despachos_existentes = response_despachos.get('data', [])
        for despacho in despachos_existentes:
            if despacho.get('created_at') and isinstance(despacho['created_at'], str):
                despacho['created_at'] = datetime.fromisoformat(despacho['created_at'])
    else:
        flash(response_despachos.get('error', 'Error al cargar el historial de despachos.'), 'danger')
        despachos_existentes = []

    # 3. Agrupar pedidos por zona para la vista de tarjetas
    pedidos_por_grupo = defaultdict(list)
    for pedido in pedidos:
        # Usar 'get' para evitar errores si 'zona' o 'nombre' no existen
        nombre_zona = pedido.get('zona', {}).get('nombre', 'Sin Zona Asignada')
        pedidos_por_grupo[nombre_zona].append(pedido)

    # 4. Renderizar la plantilla con todos los datos necesarios
    return render_template('despachos/gestion_despachos.html',
                           pedidos_json=json.dumps(pedidos, cls=CustomJSONEncoder),
                           pedidos_por_grupo=pedidos_por_grupo,
                           despachos=despachos_existentes)

@despacho_bp.route('/api/vehiculo/<patente>', methods=['GET'])
@permission_required('consultar_vehiculos') # Asumiendo un permiso existente o creando uno nuevo
def api_buscar_vehiculo(patente):
    """
    Endpoint API para buscar un vehículo por su patente.
    """
    response = vehiculo_controller.buscar_por_patente(patente)
    if response['success'] and response['data']:
        return jsonify({'success': True, 'data': response['data'][0]})
    elif response['success']:
        return jsonify({'success': False, 'error': 'Vehículo no encontrado'}), 404
    else:
        return jsonify({'success': False, 'error': response.get('error', 'Error interno')}), 500

@despacho_bp.route('/api/crear', methods=['POST'])
@permission_required('crear_despachos')
def api_crear_despacho():
    """
    Endpoint API para crear un despacho y asociar los pedidos.
    """
    data = request.json
    vehiculo_id = data.get('vehiculo_id')
    pedido_ids = data.get('pedido_ids')
    observaciones = data.get('observaciones', '')

    if not vehiculo_id or not pedido_ids:
        return {'success': False, 'error': 'Faltan datos requeridos (vehiculo_id, pedido_ids)'}, 400

    response_data, status_code = despacho_controller.crear_despacho_y_actualizar_pedidos(
        vehiculo_id,
        pedido_ids,
        observaciones
    )

    status_code_int = int(status_code)

    if status_code_int < 300 and response_data.get('success'):
        flash(f"Despacho #{response_data.get('data', {}).get('despacho_id', '')} creado exitosamente.", 'success')
        redirect_url = url_for('despacho.gestion_despachos_vista', tab='historial')
        response_data['redirect_url'] = redirect_url
        return jsonify(response_data), status_code_int
    else:
        error_message = response_data.get('error', 'Error interno al crear el despacho')
        return jsonify({'success': False, 'error': error_message}), status_code_int

@despacho_bp.route('/hoja-de-ruta/<int:despacho_id>')
@permission_required('consultar_despachos')
def descargar_hoja_de_ruta(despacho_id):
    """
    Genera y devuelve la Hoja de Ruta en formato PDF para un despacho específico.
    """
    response = despacho_controller.generar_hoja_de_ruta_pdf(despacho_id)
    if isinstance(response, dict) and not response.get('success'):
        flash(response.get('error', 'No se pudo generar la Hoja de Ruta.'), 'danger')
        # Idealmente, redirigir a una página de listado de despachos
        return redirect(url_for('orden_venta.listar')) 
    return response
