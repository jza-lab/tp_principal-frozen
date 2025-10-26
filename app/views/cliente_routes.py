from flask import Blueprint, request, render_template, jsonify, session, redirect, url_for, flash
from app.controllers.cliente_controller import ClienteController
from app.utils.decorators import permission_required, permission_any_of

cliente_bp = Blueprint('cliente', __name__, url_prefix='/cliente')
cliente_controller = ClienteController()

@cliente_bp.route('/register', methods=['GET', 'POST'])
@permission_required(accion='gestionar_clientes')
def register():
    try:
        if request.method == 'PUT' or request.method == 'POST':
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
        cuit = request.form.get('cuit')
        password = request.form.get('password')
        
        response, status_code = cliente_controller.autenticar_cliente(cuit, password)
        
        if response.get('success'):
            cliente_data = response.get('data')
            session['cliente_id'] = cliente_data['id']
            session['cliente_nombre'] = cliente_data['nombre']
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
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('public.index'))
