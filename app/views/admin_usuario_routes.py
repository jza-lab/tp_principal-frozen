from datetime import date, timedelta
from flask import Blueprint, jsonify, session, request, redirect, url_for, flash, render_template
from app.controllers.usuario_controller import UsuarioController
from app.controllers.facial_controller import FacialController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.notificación_controller import NotificacionController
from app.controllers.inventario_controller import InventarioController
from app.permisos import permission_required
from app.models.autorizacion_ingreso import AutorizacionIngresoModel

# Blueprint para la administración de usuarios
admin_usuario_bp = Blueprint('admin_usuario', __name__, url_prefix='/admin')

# Instanciar controladores
usuario_controller = UsuarioController()
facial_controller = FacialController()
orden_produccion_controller=OrdenProduccionController()
autorizacion_model = AutorizacionIngresoModel()
notificacion_controller = NotificacionController()
inventario_controller = InventarioController()

@admin_usuario_bp.route('/')
@permission_required(sector_codigo='ADMINISTRACION', accion='leer')
def index():
    hoy = date.today()

    # 0 = Lunes, 6 = Domingo. weekday() devuelve 0 para Lunes.
    # Calcular el desplazamiento (días a restar) para llegar al Lunes.
    dias_restar = hoy.weekday()
    
    # Lunes de esta semana
    fecha_inicio_semana = hoy - timedelta(days=dias_restar)
    
    # Domingo de esta semana (6 días después del Lunes)
    fecha_fin_semana = fecha_inicio_semana + timedelta(days=6)
    
    # Convertir a formato ISO (YYYY-MM-DD) para los filtros
    fecha_inicio_iso = fecha_inicio_semana.isoformat()
    fecha_fin_iso = fecha_fin_semana.isoformat()

    """Página principal del panel de administración."""
    respuesta, estado = orden_produccion_controller.obtener_cantidad_ordenes_estado("EN_PROCESO", hoy)
    ordenes_pendientes_data = respuesta.get('data', {})
    ordenes_pendientes = ordenes_pendientes_data.get('cantidad', 0)

    respuesta2, estado = orden_produccion_controller.obtener_cantidad_ordenes_estado("APROBADA")
    respuesta3, estado = orden_produccion_controller.obtener_cantidad_ordenes_estado("COMPLETADA")

    filtros = {
        'estado': 'APROBADA',
        'fecha_planificada_desde': fecha_inicio_iso,
        'fecha_planificada_hasta': fecha_fin_iso
    }

    respuesta, estado = orden_produccion_controller.obtener_ordenes(filtros)

    # Manejo seguro de datos
    ordenes_aprobadas = respuesta.get('data', [])
    
    cantidad_aprobadas = respuesta2.get('data', {}).get('cantidad', 0)
    cantidad_completadas = respuesta3.get('data', {}).get('cantidad', 0)
    
    ordenes_totales = int(cantidad_aprobadas) + int(cantidad_completadas)

    asistencia = usuario_controller.obtener_porcentaje_asistencia()
    notificaciones = notificacion_controller.obtener_notificaciones_no_leidas()

    alertas_stock_count = inventario_controller.obtener_conteo_alertas_stock()

    return render_template('dashboard/index.html', asistencia=asistencia,
                            ordenes_pendientes = ordenes_pendientes,
                            ordenes_aprobadas = ordenes_aprobadas,
                            ordenes_totales = ordenes_totales,
                            notificaciones=notificaciones)
                            alertas_stock_count=alertas_stock_count)

@admin_usuario_bp.route('/usuarios')
@permission_required(sector_codigo='ADMINISTRACION', accion='leer')
def listar_usuarios():
    """Muestra la lista de todos los usuarios del sistema."""
    usuarios = usuario_controller.obtener_todos_los_usuarios()
    return render_template('usuarios/listar.html', usuarios=usuarios)

@admin_usuario_bp.route('/usuarios/<int:id>')
@permission_required(sector_codigo='ADMINISTRACION', accion='leer')
def ver_perfil(id):
    """Muestra el perfil de un usuario específico."""
    usuario = usuario_controller.obtener_usuario_por_id(id)
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))
    return render_template('usuarios/perfil.html', usuario=usuario)

@admin_usuario_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='crear')
def nuevo_usuario():
    """
    Gestiona la creación de un nuevo usuario, incluyendo la asignación de sectores.
    """
    if request.method == 'POST':
        datos_usuario = request.form.to_dict()
        datos_usuario['sectores'] = [int(s) for s in request.form.getlist('sectores')]
        face_data = datos_usuario.pop('face_data', None)

        if 'role_id' in datos_usuario:
            datos_usuario['role_id'] = int(datos_usuario['role_id'])

        # 1. Validar rostro si se proporciona
        if face_data:
            validacion_facial = facial_controller.validar_y_codificar_rostro(face_data)
            if not validacion_facial.get('success'):
                flash(f"Error en el registro facial: {validacion_facial.get('message')}", 'error')
                roles = usuario_controller.obtener_todos_los_roles()
                sectores = usuario_controller.obtener_todos_los_sectores()
                return render_template('usuarios/formulario.html', 
                                    usuario=datos_usuario, 
                                    is_new=True,
                                    roles=roles,
                                    sectores=sectores,
                                    usuario_sectores_ids=datos_usuario.get('sectores', []))

        # 2. Crear el usuario
        resultado_creacion = usuario_controller.crear_usuario(datos_usuario)
        
        if not resultado_creacion.get('success'):
            flash(f"Error al crear el usuario: {resultado_creacion.get('error')}", 'error')
            roles = usuario_controller.obtener_todos_los_roles()
            sectores = usuario_controller.obtener_todos_los_sectores()
            return render_template('usuarios/formulario.html', 
                                usuario=datos_usuario, 
                                is_new=True,
                                roles=roles,
                                sectores=sectores,
                                usuario_sectores_ids=datos_usuario.get('sectores', []))

        # 3. Registrar el rostro si aplica
        usuario_creado = resultado_creacion.get('data')
        if usuario_creado and face_data:
            resultado_facial = facial_controller.registrar_rostro(usuario_creado.get('id'), face_data)
            if resultado_facial.get('success'):
                flash('Usuario creado y rostro registrado exitosamente.', 'success')
            else:
                flash(f"Usuario creado, pero falló el registro facial: {resultado_facial.get('message')}", 'warning')
        else:
            flash('Usuario creado exitosamente.', 'success')

        return redirect(url_for('admin_usuario.listar_usuarios'))

    # Método GET
    roles = usuario_controller.obtener_todos_los_roles()
    sectores = usuario_controller.obtener_todos_los_sectores()
    turnos = usuario_controller.obtener_todos_los_turnos()
    return render_template('usuarios/formulario.html', 
                         usuario={}, 
                         is_new=True,
                         roles=roles,
                         sectores=sectores,
                         turnos=turnos,
                         usuario_sectores_ids=[])

@admin_usuario_bp.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='actualizar')
def editar_usuario(id):
    """Gestiona la edición de un usuario existente, incluyendo sus sectores."""
    if request.method == 'POST':
        datos_actualizados = request.form.to_dict()
        datos_actualizados['sectores'] = [int(s) for s in request.form.getlist('sectores')]
        
        if 'role_id' in datos_actualizados:
            datos_actualizados['role_id'] = int(datos_actualizados['role_id'])
            
        resultado = usuario_controller.actualizar_usuario(id, datos_actualizados)
        if resultado.get('success'):
            flash('Usuario actualizado exitosamente.', 'success')
            return redirect(url_for('admin_usuario.listar_usuarios'))
        else:
            flash(f"Error al actualizar el usuario: {resultado.get('error')}", 'error')
            # Si falla la actualización, recargamos los datos originales del usuario
            # y los actualizamos con lo que el usuario intentó enviar, para que no pierda sus cambios.
            usuario_existente = usuario_controller.obtener_usuario_por_id(id, include_sectores=True, include_direccion=True)
            if not usuario_existente:
                # Si no podemos encontrar al usuario, es un error grave. Redirigir.
                flash('Error crítico: No se pudo encontrar el usuario para recargar el formulario.', 'error')
                return redirect(url_for('admin_usuario.listar_usuarios'))

            # Actualiza el diccionario del usuario con los datos del formulario que falló
            usuario_existente.update(request.form.to_dict())
            
            roles = usuario_controller.obtener_todos_los_roles()
            sectores = usuario_controller.obtener_todos_los_sectores()
            turnos = usuario_controller.obtener_todos_los_turnos()
            
            return render_template('usuarios/formulario.html', 
                                 usuario=usuario_existente, 
                                 is_new=False,
                                 roles=roles,
                                 sectores=sectores,
                                 turnos=turnos,
                                 usuario_sectores_ids=datos_actualizados.get('sectores', []))

    # Método GET
    usuario = usuario_controller.obtener_usuario_por_id(id, include_sectores=True, include_direccion=True)
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))
    
    roles = usuario_controller.obtener_todos_los_roles()
    sectores = usuario_controller.obtener_todos_los_sectores()
    turnos = usuario_controller.obtener_todos_los_turnos()
    usuario_sectores_actuales = usuario_controller.obtener_sectores_usuario(id)
    usuario_sectores_ids = [s['id'] for s in usuario_sectores_actuales]

    return render_template('usuarios/formulario.html', 
                         usuario=usuario, 
                         is_new=False,
                         roles=roles,
                         sectores=sectores,
                         turnos=turnos,
                         usuario_sectores_ids=usuario_sectores_ids)

@admin_usuario_bp.route('/usuarios/<int:id>/eliminar', methods=['POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='eliminar')
def eliminar_usuario(id):
    if session.get('usuario_id') == id:
        msg = 'No puedes desactivar tu propia cuenta.'
        if request.is_json:  # viene desde fetch
            return jsonify(success=False, error=msg)
        flash(msg, 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))

    resultado = usuario_controller.eliminar_usuario(id)
    if request.is_json:
        return jsonify(resultado)
    
    if resultado.get('success'):
        flash('Usuario desactivado exitosamente.', 'success')
    else:
        flash(f"Error al desactivar el usuario: {resultado.get('error')}", 'error')
    return redirect(url_for('admin_usuario.listar_usuarios'))

@admin_usuario_bp.route('/usuarios/<int:id>/habilitar', methods=['POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='actualizar')
def habilitar_usuario(id):
    """Reactiva un usuario."""
    resultado = usuario_controller.habilitar_usuario(id)
    if resultado.get('success'):
        flash('Usuario activado exitosamente.', 'success')
    else:
        flash(f"Error al activar el usuario: {resultado.get('error')}", 'error')
    return redirect(url_for('admin_usuario.listar_usuarios'))

@admin_usuario_bp.route('/usuarios/actividad_totem', methods=['GET'])
@permission_required(sector_codigo='ADMINISTRACION', accion='leer')
def obtener_actividad_totem():
    """
    Devuelve una lista en formato JSON de la actividad del tótem (ingresos/egresos) de hoy.
    """
    resultado = usuario_controller.obtener_actividad_totem()
    if resultado.get('success'):
        return jsonify(success=True, data=resultado.get('data', []))
    else:
        return jsonify(success=False, error=resultado.get('error', 'Error al obtener la actividad del tótem')), 500

@admin_usuario_bp.route('/usuarios/actividad_web', methods=['GET'])
@permission_required(sector_codigo='ADMINISTRACION', accion='leer')
def obtener_actividad_web():
    """
    Devuelve una lista en formato JSON de los usuarios que iniciaron sesión en la web hoy.
    """
    resultado = usuario_controller.obtener_actividad_web()
    if resultado.get('success'):
        return jsonify(success=True, data=resultado.get('data', []))
    else:
        return jsonify(success=False, error=resultado.get('error', 'Error al obtener la actividad web')), 500

@admin_usuario_bp.route('/usuarios/validar', methods=['POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='crear')
def validar_campo():
    """
    Valida de forma asíncrona si un campo (legajo o email) ya existe.
    """
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')
    
    if not field or not value:
        return jsonify({'valid': False, 'error': 'Campo o valor no proporcionado.'}), 400

    resultado = usuario_controller.validar_campo_unico(field, value)
    return jsonify(resultado)

@admin_usuario_bp.route('/usuarios/validar_rostro', methods=['POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='crear')
def validar_rostro():
    """
    Valida si el rostro en la imagen es válido y no está duplicado.
    """
    data = request.get_json()
    image_data = data.get('image')
    
    if not image_data:
        return jsonify({
            'valid': False, 
            'message': 'No se proporcionó imagen.'
        }), 400
    resultado = facial_controller.validar_y_codificar_rostro(image_data)
    if resultado.get('success'):
        return jsonify({
            'valid': True,
            'message': 'Rostro válido y disponible para registro.'
        })
    else:
        return jsonify({
            'valid': False,
            'message': resultado.get('message', 'Error al validar el rostro.')
        })

@admin_usuario_bp.route('/usuarios/verificar_direccion', methods=['POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='crear')
def verificar_direccion():
    """
    Verifica una dirección en tiempo real usando la API de Georef.
    """
    data = request.get_json()
    calle = data.get('calle')
    altura = data.get('altura')
    localidad = data.get('localidad')
    provincia = data.get('provincia')

    if not all([calle, altura, localidad, provincia]):
        return jsonify({
            'success': False,
            'message': 'Todos los campos de dirección son requeridos para la verificación.'
        }), 400

    georef_controller = usuario_controller.usuario_direccion_controller
    full_street = f"{calle} {altura}"
    
    resultado = georef_controller.normalizar_direccion(
        direccion=full_street,
        localidad=localidad,
        provincia=provincia
    )

    return jsonify(resultado)

@admin_usuario_bp.route('/autorizaciones/nueva', methods=['GET', 'POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='crear')
def nueva_autorizacion():
    """
    Muestra el formulario para crear una nueva autorización de ingreso y la procesa.
    """
    if request.method == 'POST':
        data = request.form.to_dict()
        data['supervisor_id'] = session.get('usuario_id')
        
        # Convertir a tipos de datos correctos
        data['usuario_id'] = int(data['usuario_id'])
        data['turno_autorizado_id'] = int(data['turno_autorizado_id']) if data.get('turno_autorizado_id') else None
        
        resultado = autorizacion_model.create(data)

        if resultado.get('success'):
            flash('Autorización creada exitosamente.', 'success')
            return redirect(url_for('admin_usuario.listar_usuarios'))
        else:
            flash(f"Error al crear la autorización: {resultado.get('error')}", 'error')
            usuarios = usuario_controller.obtener_todos_los_usuarios({'activo': True})
            turnos = usuario_controller.obtener_todos_los_turnos()
            return render_template('usuarios/autorizacion.html',
                                 usuarios=usuarios,
                                 turnos=turnos,
                                 autorizacion=data)

    # Método GET
    usuarios = usuario_controller.obtener_todos_los_usuarios({'activo': True})
    turnos = usuario_controller.obtener_todos_los_turnos()
    return render_template('usuarios/autorizacion.html',
                         usuarios=usuarios,
                         turnos=turnos,
                         autorizacion={})