from flask import Blueprint, request, render_template, jsonify, session, redirect, url_for, flash
from app.controllers.cliente_controller import ClienteController
from app.utils.decorators import permission_required, permission_any_of
from app.controllers.reclamo_controller import ReclamoController
from app.controllers.consulta_controller import ConsultaController

cliente_bp = Blueprint('cliente', __name__, url_prefix='/cliente')

@cliente_bp.route('/register', methods=['GET', 'POST'])
@permission_any_of('admin_gestion_sistema', 'admin_supervision')
def register():
    try:
        if request.method == 'PUT' or request.method == 'POST':
            cliente_controller = ClienteController()
            datos_json = request.get_json(force=True) 
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            
            resultado, status = cliente_controller.crear_cliente(datos_json)
            
            return jsonify(resultado), status
    except Exception as e:
        flash(f"Error al crear al cliente: {str(e)}", 'error')
    return render_template('public/registro.html')

@cliente_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cliente_controller = ClienteController()
        email = request.form.get('email')
        password = request.form.get('password')
        response, status_code = cliente_controller.autenticar_cliente(email, password)
        
        if response.get('success'):
            cliente_data = response.get('data')
            if cliente_data.get('estado_aprobacion') == 'rechazado':
                flash('Su cuenta ha sido rechazada y no puede iniciar sesión. Contacte a administración.', 'error')
                return redirect(url_for('cliente.login'))
            
            session['cliente_id'] = cliente_data['id']
            session['cliente_nombre'] = cliente_data['nombre']
            session['cliente_email'] = cliente_data['email']
            session['cliente_aprobado'] = cliente_data.get('estado_aprobacion') == 'aprobado'
            
            flash('Inicio de sesión exitoso.', 'success')
            return redirect(url_for('public.index'))
        else:
            flash(response.get('error', 'Credenciales incorrectas.'), 'error')
            
    return render_template('public/login.html')
@cliente_bp.route('/logout')
def logout():
    session.pop('cliente_id', None)
    session.pop('cliente_nombre', None)
    session.pop('cliente_aprobado', None)
    session.pop('cliente_email', None)
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('public.index'))

@cliente_bp.route('/perfil')
def perfil():
    if 'cliente_id' not in session:
        flash('Por favor, inicia sesión para ver tu perfil.', 'info')
        return redirect(url_for('cliente.login'))

    cliente_controller = ClienteController()
    reclamo_controller = ReclamoController()
    cliente_id = session['cliente_id']
    response, status_code = cliente_controller.obtener_perfil_cliente(cliente_id)

    if status_code == 200:
        cliente_data = response.get('data')

        # Cargar los reclamos del cliente
        reclamos_response, _ = reclamo_controller.obtener_reclamos_por_cliente(cliente_id)
        if reclamos_response.get('success'):
            cliente_data['reclamos'] = reclamos_response.get('data', [])
        else:
            cliente_data['reclamos'] = []

        # Marcar pedidos pagados
        if 'pedidos' in cliente_data:
            for pedido in cliente_data['pedidos']:
                pedido['pagado'] = pedido.get('estado_pago') == 'Pagado'
            
        return render_template('public/perfil.html', cliente=cliente_data)
    else:
        flash(response.get('error', 'No se pudo cargar tu perfil.'), 'error')
        return redirect(url_for('public.index'))

@cliente_bp.route('/consultas')
def ver_consultas():
    if 'cliente_id' not in session:
        flash('Por favor, inicia sesión para ver tus consultas.', 'info')
        return redirect(url_for('cliente.login'))

    cliente_id = session['cliente_id']
    consulta_controller = ConsultaController()
    consultas_response = consulta_controller.obtener_consultas_por_cliente(cliente_id)
    consultas = consultas_response.get('data', [])

    return render_template('public/mis_consultas.html', consultas=consultas)
