from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from app.controllers.reclamo_controller import ReclamoController
from flask_jwt_extended import jwt_required, get_current_user
from flask_wtf import FlaskForm

reclamo_bp = Blueprint('reclamo', __name__, url_prefix='/api/reclamos')

@reclamo_bp.route('/', methods=['POST'])
def crear_reclamo():
    """
    Endpoint para crear un nuevo reclamo.
    Espera un JSON con los datos del reclamo.
    """
    # La creación de reclamos es una acción del cliente, usa la sesión de Flask.
    if 'cliente_id' not in session:
        return jsonify({"success": False, "error": "Acceso no autorizado. Debes iniciar sesión."}), 401

    datos_json = request.get_json()
    if not datos_json:
        return jsonify({"success": False, "error": "No se recibieron datos JSON."}), 400

    cliente_id = session['cliente_id']

    controller = ReclamoController()
    respuesta, status_code = controller.crear_reclamo(datos_json, cliente_id)

    return jsonify(respuesta), status_code

@reclamo_bp.route('/', methods=['GET'])
@jwt_required()
def obtener_reclamos():
    """
    Endpoint para obtener todos los reclamos del cliente que ha iniciado sesión.
    """
    current_user = get_current_user()
    cliente_id = current_user.id

    controller = ReclamoController()
    respuesta, status_code = controller.obtener_reclamos_por_cliente(cliente_id)

    return jsonify(respuesta), status_code

# --- NUEVAS RUTAS PÚBLICAS ---

@reclamo_bp.route('/<int:reclamo_id>', methods=['GET'])
def obtener_detalle_reclamo(reclamo_id):
    """
    Muestra la página de detalle (chat) de un reclamo para el cliente.
    """
    # Esta ruta es para clientes, por lo que usa la sesión de Flask, no JWT.
    if 'cliente_id' not in session:
        flash('Debes iniciar sesión para ver los detalles del reclamo.', 'warning')
        return redirect(url_for('cliente.login'))

    cliente_id = session['cliente_id']

    controller = ReclamoController()
    respuesta, status_code = controller.obtener_detalle_reclamo(reclamo_id)

    if not respuesta.get('success'):
        flash(respuesta.get('error', 'Reclamo no encontrado.'), 'error')
        return redirect(url_for('cliente.perfil'))

    reclamo = respuesta.get('data')

    # Verificación de seguridad
    if reclamo.get('cliente_id') != cliente_id:
        flash('No tienes permiso para ver este reclamo.', 'error')
        return redirect(url_for('cliente.perfil'))

    return render_template('public/reclamo_detalle.html', reclamo=reclamo, csrf_form=FlaskForm())

@reclamo_bp.route('/<int:reclamo_id>/responder', methods=['POST'])
@jwt_required()
def responder_reclamo_cliente(reclamo_id):
    """
    Endpoint para que el cliente envíe una respuesta a un reclamo.
    """
    current_user = get_current_user()
    cliente_id = current_user.id

    mensaje = request.form.get('mensaje')
    if not mensaje:
        flash('La respuesta no puede estar vacía.', 'error')
        return redirect(url_for('reclamo.obtener_detalle_reclamo', reclamo_id=reclamo_id))

    controller = ReclamoController()
    # Verificar que el reclamo pertenece al cliente
    reclamo_resp, _ = controller.obtener_detalle_reclamo(reclamo_id)
    if not reclamo_resp.get('success') or reclamo_resp['data'].get('cliente_id') != cliente_id:
        flash('No tienes permiso para responder a este reclamo.', 'error')
        return redirect(url_for('cliente.perfil'))

    respuesta, status_code = controller.responder_reclamo_cliente(reclamo_id, cliente_id, mensaje)

    if status_code == 201:
        flash('Respuesta enviada. El administrador la revisará a la brevedad.', 'success')
    else:
        flash(f"Error: {respuesta.get('error', 'No se pudo enviar la respuesta.')}", 'error')

    return redirect(url_for('reclamo.obtener_detalle_reclamo', reclamo_id=reclamo_id))

@reclamo_bp.route('/<int:reclamo_id>/resolver', methods=['POST'])
@jwt_required()
def resolver_reclamo_cliente(reclamo_id):
    """
    Endpoint para que el cliente marque un reclamo como solucionado.
    """
    current_user = get_current_user()
    cliente_id = current_user.id

    controller = ReclamoController()
    # Verificar que el reclamo pertenece al cliente
    reclamo_resp, _ = controller.obtener_detalle_reclamo(reclamo_id)
    if not reclamo_resp.get('success') or reclamo_resp['data'].get('cliente_id') != cliente_id:
        flash('No tienes permiso para esta acción.', 'error')
        return redirect(url_for('cliente.perfil'))

    respuesta, status_code = controller.cerrar_reclamo_cliente(reclamo_id)

    if status_code == 200:
        flash('¡Qué bueno! Marcaste este reclamo como solucionado.', 'success')
    else:
        flash(f"Error: {respuesta.get('error', 'No se pudo actualizar el estado.')}", 'error')

    return redirect(url_for('reclamo.obtener_detalle_reclamo', reclamo_id=reclamo_id))