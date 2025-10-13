import json
from datetime import date, timedelta, datetime
from flask import Blueprint, jsonify, session, request, redirect, url_for, flash, render_template
from app.controllers.usuario_controller import UsuarioController
from app.controllers.facial_controller import FacialController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.notificación_controller import NotificacionController
from app.controllers.inventario_controller import InventarioController
from app.permisos import admin_permission_required, admin_permission_any_of
from app.controllers.autorizacion_controller import AutorizacionController
from app.controllers.lote_producto_controller import LoteProductoController

# Blueprint para la administración de usuarios
admin_usuario_bp = Blueprint('admin_usuario', __name__, url_prefix='/admin')

# Instanciar controladores
usuario_controller = UsuarioController()
facial_controller = FacialController()
orden_produccion_controller=OrdenProduccionController()
autorizacion_controller = AutorizacionController()
notificacion_controller = NotificacionController()
inventario_controller = InventarioController()
lote_producto_controller = LoteProductoController()

@admin_usuario_bp.route('/')
@admin_permission_required(accion='ver_dashboard')
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
    
    # 1. Obtener insumos con stock bajo (la lista y el conteo)
    insumos_bajo_stock_resp, _ = inventario_controller.obtener_insumos_bajo_stock()
    insumos_bajo_stock_list = insumos_bajo_stock_resp.get('data', [])
    alertas_stock_count = len(insumos_bajo_stock_list)
    alertas_stock_count = inventario_controller.obtener_conteo_alertas_stock()

    # 2. Obtener productos sin lotes (la lista y el conteo)
    productos_sin_lotes_resp, _ = lote_producto_controller.obtener_conteo_productos_sin_lotes()
    data_sin_lotes = productos_sin_lotes_resp.get('data', {})
    productos_sin_lotes_count = data_sin_lotes.get('conteo_sin_lotes', 0) 
    productos_sin_lotes_list = data_sin_lotes.get('productos_sin_lotes', [])
    
    user_permissions = session.get('permisos', {})

    return render_template('dashboard/index.html', asistencia=asistencia,
                            ordenes_pendientes = ordenes_pendientes,
                            ordenes_aprobadas = ordenes_aprobadas,
                            ordenes_totales = ordenes_totales,
                            notificaciones=notificaciones,
                            alertas_stock_count=alertas_stock_count,
                            insumos_bajo_stock_list=insumos_bajo_stock_list,
                            productos_sin_lotes_count=productos_sin_lotes_count,
                            productos_sin_lotes_list=productos_sin_lotes_list,
                            user_permissions=user_permissions)

@admin_usuario_bp.route('/usuarios')
@admin_permission_any_of('ver_info_empleados', 'modificar_usuarios', 'crear_usuarios')
def listar_usuarios():
    """Muestra la lista de todos los usuarios del sistema."""
    usuarios = usuario_controller.obtener_todos_los_usuarios()
    turnos = usuario_controller.obtener_todos_los_turnos()
    sectores = usuario_controller.obtener_todos_los_sectores()
    return render_template('usuarios/listar.html', usuarios=usuarios, turnos=turnos, sectores=sectores)

@admin_usuario_bp.route('/usuarios/<int:id>')
@admin_permission_any_of('ver_info_empleados', 'modificar_usuarios')
def ver_perfil(id):
    """Muestra el perfil de un usuario específico, incluyendo su dirección."""
    usuario = usuario_controller.obtener_usuario_por_id(id, include_sectores=True, include_direccion=True)
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))

    # Parsear fechas de string a datetime objects antes de renderizar
    for key in ['ultimo_login_web', 'ultimo_login_totem', 'fecha_ingreso']:
        if usuario.get(key) and isinstance(usuario[key], str):
            try:
                usuario[key] = datetime.fromisoformat(usuario[key].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                print(f"Advertencia: No se pudo parsear la fecha '{usuario[key]}' para el campo '{key}'.")
                usuario[key] = None

    # Formatear la dirección para una mejor visualización
    if usuario.get('direccion'):
        dir_data = usuario['direccion']
        usuario['direccion_formateada'] = f"{dir_data.get('calle', '')} {dir_data.get('altura', '')}, " \
                                          f"{dir_data.get('localidad', '')}, {dir_data.get('provincia', '')}"
    else:
        usuario['direccion_formateada'] = 'No especificada'

    # Obtener datos para los dropdowns del modo edición
    roles_disponibles = usuario_controller.obtener_todos_los_roles()
    sectores_disponibles = usuario_controller.obtener_todos_los_sectores()
    turnos_disponibles = usuario_controller.obtener_todos_los_turnos()

    return render_template('usuarios/perfil.html', 
                           usuario=usuario,
                           roles_disponibles=roles_disponibles,
                           sectores_disponibles=sectores_disponibles,
                           turnos_disponibles=turnos_disponibles)

@admin_usuario_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@admin_permission_required(accion='crear_usuarios')
def nuevo_usuario():
    """
    Gestiona la creación de un nuevo usuario, incluyendo la asignación de sectores.
    """
    if request.method == 'POST':
        datos_usuario = request.form.to_dict()
        
        # --- Procesamiento de Sectores ---
        sectores_str = datos_usuario.get('sectores', '[]')
        try:
            sectores_ids = json.loads(sectores_str)
            if isinstance(sectores_ids, list):
                datos_usuario['sectores'] = [int(s) for s in sectores_ids if str(s).isdigit()]
            else:
                datos_usuario['sectores'] = []
        except (json.JSONDecodeError, TypeError):
            # Fallback para el caso de que no sea un JSON string
            sectores_raw = request.form.getlist('sectores')
            datos_usuario['sectores'] = [int(s) for s in sectores_raw if s.isdigit()]

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
@admin_permission_any_of('modificar_usuarios', 'modificar_info_empleados')
def editar_usuario(id):
    """
    Gestiona la edición de un usuario. Responde con JSON a peticiones AJAX
    y con render/redirect a peticiones de formulario normales.
    """
    # Determinar si es una petición AJAX
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        datos_actualizados = request.form.to_dict()
        print(f"DEBUG: Datos recibidos en la ruta: {datos_actualizados}")
        
        # --- Procesamiento de Datos ---
        # Sectores: AJAX los envía como un string JSON, el form normal como una lista
        sectores_str = datos_actualizados.get('sectores', '[]')
        try:
            # Para AJAX
            sectores_ids = json.loads(sectores_str)
            if isinstance(sectores_ids, list):
                datos_actualizados['sectores'] = [int(s) for s in sectores_ids if str(s).isdigit()]
            else:
                 datos_actualizados['sectores'] = []
        except (json.JSONDecodeError, TypeError):
            # Para Formulario normal
            sectores_raw = request.form.getlist('sectores')
            datos_actualizados['sectores'] = [int(s) for s in sectores_raw if s.isdigit()]

        # Role ID y Turno ID
        for key in ['role_id', 'turno_id']:
            if key in datos_actualizados and str(datos_actualizados[key]).isdigit():
                datos_actualizados[key] = int(datos_actualizados[key])
            else:
                datos_actualizados.pop(key, None)
        
        # --- Lógica de Actualización ---
        resultado = usuario_controller.actualizar_usuario(id, datos_actualizados)

        if resultado.get('success'):
            if is_ajax:
                return jsonify({'success': True, 'message': 'Usuario actualizado exitosamente.'})
            else:
                flash('Usuario actualizado exitosamente.', 'success')
                return redirect(url_for('admin_usuario.listar_usuarios'))
        else:
            error_message = resultado.get('error', 'Ocurrió un error desconocido.')
            if is_ajax:
                return jsonify({'success': False, 'message': error_message}), 400
            else:
                flash(f"Error al actualizar: {error_message}", 'error')
                # Recargar datos para el formulario en caso de error
                usuario_existente = usuario_controller.obtener_usuario_por_id(id, include_sectores=True, include_direccion=True)
                if not usuario_existente:
                    flash('Error crítico: No se pudo encontrar el usuario.', 'error')
                    return redirect(url_for('admin_usuario.listar_usuarios'))
                
                # Fusionar datos para preservar la entrada del usuario
                usuario_existente.update(datos_actualizados)
                
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
@admin_permission_required(accion='inactivar_usuarios')
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
@admin_permission_any_of('modificar_usuarios', 'inactivar_usuarios')
def habilitar_usuario(id):
    """Reactiva un usuario."""
    resultado = usuario_controller.habilitar_usuario(id)
    if resultado.get('success'):
        flash('Usuario activado exitosamente.', 'success')
    else:
        flash(f"Error al activar el usuario: {resultado.get('error')}", 'error')
    return redirect(url_for('admin_usuario.listar_usuarios'))

@admin_usuario_bp.route('/usuarios/actividad_totem', methods=['GET'])
@admin_permission_any_of('registrar_asistencias', 'ver_reportes_basicos')
def obtener_actividad_totem():
    """
    Devuelve una lista en formato JSON de la actividad del tótem (ingresos/egresos) de hoy.
    """
    filtros = {
        'sector_id': request.args.get('sector_id'),
        'fecha_desde': request.args.get('fecha_desde'),
        'fecha_hasta': request.args.get('fecha_hasta')
    }
    resultado = usuario_controller.obtener_actividad_totem(filtros)
    if resultado.get('success'):
        return jsonify(success=True, data=resultado.get('data', []))
    else:
        return jsonify(success=False, error=resultado.get('error', 'Error al obtener la actividad del tótem')), 500

@admin_usuario_bp.route('/usuarios/actividad_web', methods=['GET'])
@admin_permission_any_of('registrar_asistencias', 'ver_reportes_basicos')
def obtener_actividad_web():
    """
    Devuelve una lista en formato JSON de los usuarios que iniciaron sesión en la web hoy.
    """
    filtros = {
        'sector_id': request.args.get('sector_id'),
        'fecha_desde': request.args.get('fecha_desde'),
        'fecha_hasta': request.args.get('fecha_hasta')
    }
    resultado = usuario_controller.obtener_actividad_web(filtros)
    if resultado.get('success'):
        return jsonify(success=True, data=resultado.get('data', []))
    else:
        return jsonify(success=False, error=resultado.get('error', 'Error al obtener la actividad web')), 500

@admin_usuario_bp.route('/usuarios/validar', methods=['POST'])
@admin_permission_any_of('crear_usuarios', 'modificar_usuarios', 'modificar_info_empleados')
def validar_campo():
    """
    Valida de forma asíncrona si un campo (legajo, email, etc.) ya existe,
    excluyendo el usuario actual si se proporciona un user_id.
    """
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')
    user_id = data.get('user_id')

    if not field or not value:
        return jsonify({'valid': False, 'error': 'Campo o valor no proporcionado.'}), 400

    # Aquí pasamos el user_id al controlador. El controlador se encargará de la lógica.
    resultado = usuario_controller.validar_campo_unico(field, value, user_id)
    return jsonify(resultado)

@admin_usuario_bp.route('/usuarios/validar_rostro', methods=['POST'])
@admin_permission_required(accion='crear_usuarios')
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
@admin_permission_any_of('crear_usuarios', 'modificar_usuarios', 'modificar_info_empleados')
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
@admin_permission_required(accion='aprobar_permisos')
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
        
        resultado = autorizacion_controller.crear_autorizacion(data)

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

@admin_usuario_bp.route('/autorizaciones', methods=['GET'])
@admin_permission_required(accion='aprobar_permisos')
def listar_autorizaciones():
    """
    Obtiene todas las autorizaciones de ingreso pendientes.
    """
    resultado = autorizacion_controller.obtener_autorizaciones_pendientes()
    if resultado.get('success'):
        return jsonify(success=True, data=resultado.get('data', []))
    else:
        # Devuelve un array vacío si no hay autorizaciones pendientes, en lugar de un error.
        if "no se encontraron" in resultado.get('error', '').lower():
            return jsonify(success=True, data=[])
        return jsonify(success=False, error=resultado.get('error', 'Error al obtener las autorizaciones.')), 500

@admin_usuario_bp.route('/autorizaciones/<int:id>/estado', methods=['POST'])
@admin_permission_required(accion='aprobar_permisos')
def actualizar_estado_autorizacion(id):
    """
    Actualiza el estado de una autorización de ingreso (APROBADO o RECHAZADO).
    """
    data = request.get_json()
    nuevo_estado = data.get('estado')
    comentario = data.get('comentario')

    if not nuevo_estado or nuevo_estado not in ['APROBADO', 'RECHAZADO']:
        return jsonify(success=False, error='Estado no válido.'), 400

    resultado = autorizacion_controller.actualizar_estado_autorizacion(id, nuevo_estado, comentario)

    if resultado.get('success'):
        return jsonify(success=True, message='Autorización actualizada exitosamente.')
    else:
        return jsonify(success=False, error=resultado.get('error', 'Error al actualizar la autorización.')), 500
