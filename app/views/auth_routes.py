from flask import Blueprint, jsonify, session, request, redirect, url_for, flash, render_template
from app.controllers.usuario_controller import UsuarioController
from app.controllers.facial_controller import FacialController

# Blueprint para la autenticación de usuarios
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Instanciar controladores
usuario_controller = UsuarioController()
facial_controller = FacialController()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Gestiona el inicio de sesión de los usuarios."""
    if request.method == 'POST':
        
        legajo = request.form['legajo']
        password = request.form['password']
        respuesta = usuario_controller.autenticar_usuario_V2(legajo, password)
        usuario= respuesta.get('data')

        if respuesta.get('success') and usuario and usuario.get('activo'):
            session['usuario_id'] = usuario['id']
            session['rol'] = usuario['rol']
            session['usuario_nombre'] = f"{usuario['nombre']} {usuario['apellido']}"
            session['user_data'] = usuario # Guardar para el registro de egreso

            flash(f"Bienvenido {usuario['nombre']}", 'success')
            return redirect(url_for('admin_usuario.index'))
        else:
            flash('Credenciales incorrectas o usuario inactivo.', 'error')
            return redirect(url_for('auth.login'))

    # Para peticiones GET, simplemente renderizar la plantilla
    return render_template('usuarios/login.html')

@auth_bp.route("/identificar_rostro", methods=["GET","POST"])
def identificar_rostro():
   data = request.get_json()
   image_data_url = data.get("image")
   #facial_controller.registrar_rostro(id, image_data_url)
   resultado = facial_controller.identificar_rostro(image_data_url)
   estado=resultado['success']
   
   if(estado):
       usuario= resultado['usuario']
       if(usuario and usuario.get('id') and usuario.get('activo')):
           session['usuario_id'] = usuario['id']
           session['rol'] = usuario['rol']
           session['usuario_nombre'] = f"{usuario.get('nombre')} {usuario.get('apellido')}"
           session['user_data'] = usuario
           print(usuario)
           return jsonify({
                   'success': True, 
                   'message': 'Rostro identificado correctamente.',
                   'redirect': url_for('admin_usuario.index') # Redirigir a la página principal
               }), 200
   else:
        return jsonify({
           'success': False, 
           'message': 'Rostro no reconocido o usuario inactivo. Por favor, ingrese mediante sus credenciales.'
       }), 401

@auth_bp.route('/logout')
def logout():
    """Cierra la sesión del usuario actual."""
    if 'user_data' in session:
        flash("Egreso registrado correctamente. Sesión cerrada.", "info")
    else:
        flash("Sesión cerrada.", "info")

    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/perfil')
def perfil():
    """Muestra la página de perfil del usuario que ha iniciado sesión."""
    if 'usuario_id' not in session:
        return redirect(url_for('auth.login'))

    usuario = usuario_controller.obtener_usuario_por_id(session['usuario_id'])
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('auth.logout'))

    return render_template('usuarios/perfil.html', usuario=usuario)