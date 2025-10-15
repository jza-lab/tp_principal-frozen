from datetime import date, timedelta
from flask import Blueprint, jsonify, session, request, redirect, url_for, flash, render_template
from app.controllers.usuario_controller import UsuarioController
from app.controllers.facial_controller import FacialController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.notificación_controller import NotificacionController
from app.controllers.inventario_controller import InventarioController
from app.permisos import permission_required, permission_any_of
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
@permission_required(accion='ver_dashboard')
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
@permission_any_of('ver_info_empleados', 'modificar_usuarios', 'crear_usuarios')
def listar_usuarios():
    """Muestra la lista de todos los usuarios del sistema."""
    usuarios = usuario_controller.obtener_todos_los_usuarios()
    turnos = usuario_controller.obtener_todos_los_turnos()
    sectores = usuario_controller.obtener_todos_los_sectores()
    return render_template('usuarios/listar.html', usuarios=usuarios, turnos=turnos, sectores=sectores)

@admin_usuario_bp.route('/usuarios/<int:id>')
@permission_any_of('ver_info_empleados', 'modificar_usuarios')
def ver_perfil(id):
    """Muestra el perfil de un usuario específico, delegando la carga de datos al controlador."""
    resultado = usuario_controller.obtener_datos_para_vista_perfil(id)

    if not resultado.get('success'):
        flash(resultado.get('error', 'Ocurrió un error'), 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))

    # El controlador ya ha preparado todos los datos necesarios.
    # Desempaquetamos el diccionario de datos para pasarlo a la plantilla.
    return render_template('usuarios/perfil.html', **resultado.get('data', {}))

@admin_usuario_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@permission_required(accion='crear_usuarios')
def nuevo_usuario():
    """
    Gestiona la creación de un nuevo usuario, incluyendo la asignación de sectores.
    """
    if request.method == 'POST':
        resultado = usuario_controller.gestionar_creacion_usuario_form(request.form, facial_controller)

        if resultado.get('success'):
            flash('Usuario creado exitosamente.', 'success')
            if resultado.get('warning'):
                flash(resultado.get('warning'), 'warning')
            return redirect(url_for('admin_usuario.listar_usuarios'))
        else:
            flash(f"Error al crear el usuario: {resultado.get('error')}", 'error')
            form_data = usuario_controller.obtener_datos_para_formulario_usuario()
            
            # Re-poblar el formulario con los datos ingresados por el usuario
            datos_formulario = request.form.to_dict()
            sectores_seleccionados = [int(s) for s in request.form.getlist('sectores') if s.isdigit()]

            return render_template('usuarios/formulario.html', 
                                 usuario=datos_formulario, 
                                 is_new=True,
                                 roles=form_data.get('roles'),
                                 sectores=form_data.get('sectores'),
                                 turnos=form_data.get('turnos'),
                                 usuario_sectores_ids=sectores_seleccionados)

    # Método GET
    form_data = usuario_controller.obtener_datos_para_formulario_usuario()
    return render_template('usuarios/formulario.html', 
                         usuario={}, 
                         is_new=True,
                         roles=form_data.get('roles'),
                         sectores=form_data.get('sectores'),
                         turnos=form_data.get('turnos'),
                         usuario_sectores_ids=[])

@admin_usuario_bp.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@permission_any_of('modificar_usuarios', 'modificar_info_empleados')
def editar_usuario(id):
    """
    Gestiona la edición de un usuario. Responde con JSON a peticiones AJAX
    y con render/redirect a peticiones de formulario normales.
    """
    # Determinar si es una petición AJAX
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        resultado = usuario_controller.gestionar_actualizacion_usuario_form(id, request.form)

        if resultado.get('success'):
            if is_ajax:
                return jsonify({'success': True, 'message': 'Usuario actualizado exitosamente.'})
            flash('Usuario actualizado exitosamente.', 'success')
            return redirect(url_for('admin_usuario.listar_usuarios'))
        else:
            error_message = resultado.get('error', 'Ocurrió un error desconocido.')
            if is_ajax:
                return jsonify({'success': False, 'message': error_message}), 400
            
            flash(f"Error al actualizar: {error_message}", 'error')
            # Recargar datos para el formulario en caso de error
            usuario_existente = usuario_controller.obtener_usuario_por_id(id, include_direccion=True)
            if not usuario_existente:
                return redirect(url_for('admin_usuario.listar_usuarios'))
            
            # Fusionar datos para preservar la entrada del usuario en el formulario
            usuario_existente.update(request.form.to_dict())
            form_data = usuario_controller.obtener_datos_para_formulario_usuario()
            
            return render_template('usuarios/formulario.html', 
                                 usuario=usuario_existente, 
                                 is_new=False,
                                 roles=form_data.get('roles'),
                                 sectores=form_data.get('sectores'),
                                 turnos=form_data.get('turnos'),
                                 usuario_sectores_ids=[int(s) for s in request.form.getlist('sectores') if s.isdigit()])

    # Método GET
    usuario = usuario_controller.obtener_usuario_por_id(id, include_direccion=True)
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))
        
    form_data = usuario_controller.obtener_datos_para_formulario_usuario()
    usuario_sectores_ids = usuario_controller.obtener_sectores_ids_usuario(id)

    return render_template('usuarios/formulario.html', 
                         usuario=usuario, 
                         is_new=False,
                         roles=form_data.get('roles'),
                         sectores=form_data.get('sectores'),
                         turnos=form_data.get('turnos'),
                         usuario_sectores_ids=usuario_sectores_ids)

@admin_usuario_bp.route('/usuarios/<int:id>/eliminar', methods=['POST'])
@permission_required(accion='inactivar_usuarios')
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
@permission_any_of('modificar_usuarios', 'inactivar_usuarios')
def habilitar_usuario(id):
    """Reactiva un usuario."""
    resultado = usuario_controller.habilitar_usuario(id)
    if resultado.get('success'):
        flash('Usuario activado exitosamente.', 'success')
    else:
        flash(f"Error al activar el usuario: {resultado.get('error')}", 'error')
    return redirect(url_for('admin_usuario.listar_usuarios'))

@admin_usuario_bp.route('/usuarios/actividad_totem', methods=['GET'])
@permission_any_of('registrar_asistencias', 'ver_reportes_basicos')
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
@permission_any_of('registrar_asistencias', 'ver_reportes_basicos')
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
@permission_any_of('crear_usuarios', 'modificar_usuarios', 'modificar_info_empleados')
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
@permission_required(accion='crear_usuarios')
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
@permission_any_of('crear_usuarios', 'modificar_usuarios', 'modificar_info_empleados')
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
@permission_required(accion='aprobar_permisos')
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
@permission_required(accion='aprobar_permisos')
def listar_autorizaciones():
    """
    Obtiene todas las autorizaciones de ingreso.
    """
    resultado = autorizacion_controller.obtener_todas_las_autorizaciones()
    if resultado.get('success'):
        # El modelo ya devuelve los datos agrupados, ej: {'PENDIENTE': [...], 'APROBADA': [...]}
        grouped_data = resultado.get('data', {})
        
        # Separar para la estructura que espera el frontend
        pendientes = grouped_data.get('PENDIENTE', [])
        historial = grouped_data.get('APROBADA', []) + grouped_data.get('RECHAZADA', [])
        
        return jsonify(success=True, data={'pendientes': pendientes, 'historial': historial})
    
    return jsonify(success=False, error=resultado.get('error', 'Error al obtener las autorizaciones.')), 500

@admin_usuario_bp.route('/autorizaciones/<int:id>/estado', methods=['POST'])
@permission_required(accion='aprobar_permisos')
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
