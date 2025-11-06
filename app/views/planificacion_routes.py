import logging
from flask import Blueprint, render_template, flash, url_for, request, jsonify, redirect 
from flask_jwt_extended import get_jwt_identity, jwt_required, get_jwt
from app.controllers.planificacion_controller import PlanificacionController
from app.controllers.usuario_controller import UsuarioController
from datetime import date, timedelta, datetime
from app.utils.decorators import permission_required
from app import csrf

planificacion_bp = Blueprint('planificacion', __name__, url_prefix='/planificacion')
logger = logging.getLogger(__name__)
csrf.exempt(planificacion_bp)

@planificacion_bp.route('/')
@jwt_required()
@permission_required(accion='consultar_plan_de_produccion')
def index():
    controller = PlanificacionController()
    current_user = get_jwt()
    
    # 1. Obtener parámetros de la solicitud
    week_str = request.args.get('semana')
    if not week_str:
        today = date.today()
        start_of_week_iso = today - timedelta(days=today.isoweekday() - 1)
        week_str = start_of_week_iso.strftime("%Y-W%V")
    
    try:
        horizonte_dias = request.args.get('horizonte', default=7, type=int)
        if horizonte_dias <= 0: horizonte_dias = 7
    except ValueError:
        horizonte_dias = 7

    # 2. Llamada única al método orquestador
    response, status_code = controller.obtener_datos_para_vista_planificacion(
        week_str=week_str,
        horizonte_dias=horizonte_dias,
        current_user_id=current_user.get('id'),
        current_user_rol=current_user.get('rol')
    )

    if status_code != 200:
        flash(response.get('error', 'Error desconocido al cargar los datos de planificación.'), 'error')
        # Renderizar la plantilla con datos vacíos para evitar que la página se rompa
        return render_template('planificacion/tablero.html', mps_data={}, ordenes_por_dia={}, carga_crp={}, capacidad_crp={}, supervisores=[], operarios=[], columnas={})

    # 3. Desempaquetar datos y preparar contexto para la plantilla
    datos = response.get('data', {})
    
    # Navegación semanal
    try:
        year, week_num_str = week_str.split('-W')
        current_week_start = date.fromisocalendar(int(year), int(week_num_str), 1)
        prev_week_start = current_week_start - timedelta(days=7)
        next_week_start = current_week_start + timedelta(days=7)
        prev_week_str = prev_week_start.strftime("%Y-W%V")
        next_week_str = next_week_start.strftime("%Y-W%V")
    except ValueError:
        prev_week_str, next_week_str = None, None
        logger.warning(f"Error parseando week_str {week_str}")

    columnas_kanban = {
        'EN ESPERA': 'En Espera',
        'LISTA PARA PRODUCIR':'Lista para producir',
        'EN_LINEA_1': 'Linea 1',
        'EN_LINEA_2': 'Linea 2',
        'EN_EMPAQUETADO': 'Empaquetado',
        'CONTROL_DE_CALIDAD': 'Control de Calidad',
        'COMPLETADA': 'Completada'
    }

    # Roles para la UI
    user_roles = current_user.get('roles', [])
    is_operario = 'OPERARIO' in user_roles
    is_supervisor_calidad = 'SUPERVISOR_CALIDAD' in user_roles

    return render_template(
        'planificacion/tablero.html',
        mps_data=datos.get('mps_data', {}),
        ordenes_por_dia=datos.get('ordenes_por_dia', {}),
        carga_crp=datos.get('carga_crp', {}),
        capacidad_crp=datos.get('capacidad_crp', {}),
        supervisores=datos.get('supervisores', []),
        operarios=datos.get('operarios', []),
        inicio_semana=datos.get('inicio_semana'),
        fin_semana=datos.get('fin_semana'),
        semana_actual_str=week_str,
        semana_anterior_str=prev_week_str,
        semana_siguiente_str=next_week_str,
        # TODO: 'ordenes_por_estado' debe ser calculado por el orquestador si es necesario para el Kanban
        ordenes_por_estado={}, 
        columnas=columnas_kanban,
        now=datetime.utcnow(),
        timedelta=timedelta,
        date=date,
        is_operario=is_operario,
        is_supervisor_calidad=is_supervisor_calidad
    )

# --- Rutas de API (sin cambios) ---

@planificacion_bp.route('/api/consolidar', methods=['POST'])
@jwt_required()
@permission_required(accion='aprobar_plan_de_produccion')
def consolidar_api():
    data = request.get_json()
    op_ids = data.get('op_ids', [])
    usuario_id = get_jwt_identity()
    controller = PlanificacionController()
    response, status_code = controller.consolidar_ops(op_ids, usuario_id)
    return jsonify(response), status_code

@planificacion_bp.route('/api/consolidar-y-aprobar', methods=['POST'])
@jwt_required()
@permission_required(accion='aprobar_plan_de_produccion')
def consolidar_y_aprobar_api():
    data = request.get_json()
    usuario_id = get_jwt_identity()
    controller = PlanificacionController()
    response, status_code = controller.consolidar_y_aprobar_lote(
        op_ids=data.get('op_ids', []),
        asignaciones=data.get('asignaciones', {}),
        usuario_id=usuario_id
    )
    return jsonify(response), status_code

@planificacion_bp.route('/api/confirmar-aprobacion', methods=['POST'])
@jwt_required()
@permission_required(accion='aprobar_plan_de_produccion')
def confirmar_aprobacion_api():
    data = request.get_json()
    usuario_id = get_jwt_identity()
    op_id = data.get('op_id')
    asignaciones = data.get('asignaciones')
    if not op_id or not asignaciones:
        return jsonify({'success': False, 'error': 'Faltan datos (op_id o asignaciones).'}), 400
    controller = PlanificacionController()
    response, status_code = controller.confirmar_aprobacion_lote(op_id, asignaciones, usuario_id)
    return jsonify(response), status_code

@planificacion_bp.route('/forzar_auto_planificacion', methods=['POST'])
@jwt_required()
@permission_required(accion='ejecutar_planificacion_automatica')
def forzar_planificacion():
    usuario_id = get_jwt_identity()
    controller = PlanificacionController()
    response, status_code = controller.forzar_auto_planificacion(usuario_id)
    return jsonify(response), status_code

@planificacion_bp.route('/api/validar-fecha-requerida', methods=['POST'])
@jwt_required()
def validar_fecha_requerida_api():
    data = request.json
    items_data = data.get('items', [])
    fecha_requerida = data.get('fecha_requerida')

    if not items_data or not fecha_requerida:
        return jsonify({'success': False, 'error': 'Faltan items o fecha_requerida.'}), 400

    controller = PlanificacionController()
    # Asumo que el método `api_validar_fecha_requerida` existe en el controlador
    response, status_code = controller.api_validar_fecha_requerida(items_data, fecha_requerida)
    return jsonify(response), status_code

@planificacion_bp.route('/configuracion', methods=['GET'])
#@jwt_required()
#@permission_required(accion='configurar_planificacion')
def configuracion_lineas():
    """Muestra la página de configuración de líneas, bloqueos y parámetros generales."""
    from app.controllers.configuracion_controller import ConfiguracionController, TOLERANCIA_SOBREPRODUCCION_PORCENTAJE, DEFAULT_TOLERANCIA_SOBREPRODUCCION
    
    plan_controller = PlanificacionController()
    config_controller = ConfiguracionController()

    # Cargar datos de líneas y bloqueos
    response, status_code = plan_controller.obtener_datos_configuracion()
    if status_code != 200:
        flash(response.get('error', 'No se pudieron cargar los datos de configuración de líneas.'), 'error')
        # Aún así, intentamos renderizar la página con lo que tengamos
        contexto = {'lineas': [], 'bloqueos': [], 'now': datetime.utcnow(), 'configuracion': {}}
    else:
        contexto = response.get('data', {})
        contexto['now'] = datetime.utcnow()

    # Cargar parámetros generales de producción
    tolerancia = config_controller.obtener_valor_configuracion(
        TOLERANCIA_SOBREPRODUCCION_PORCENTAJE,
        DEFAULT_TOLERANCIA_SOBREPRODUCCION
    )
    
    # Añadir al contexto en un diccionario anidado para Jinja2
    contexto['configuracion'] = {
        'TOLERANCIA_SOBREPRODUCCION_PORCENTAJE': tolerancia
    }

    return render_template('planificacion/configuracion.html', **contexto)

@planificacion_bp.route('/configuracion/guardar-linea', methods=['POST'])
##@jwt_required()
# @permission_required(accion='configurar_planificacion')
def guardar_configuracion_linea():
    """Guarda los cambios de eficiencia/utilización de una línea."""
    data = request.form
    controller = PlanificacionController()
    response, status_code = controller.actualizar_configuracion_linea(data)

    if status_code == 200:
        flash(response.get('message', 'Línea actualizada.'), 'success')
    else:
        flash(response.get('error', 'Error al actualizar.'), 'error')

    return redirect(url_for('planificacion.configuracion_lineas'))


@planificacion_bp.route('/configuracion/agregar-bloqueo', methods=['POST'])
##@jwt_required()
# @permission_required(accion='configurar_planificacion')
def agregar_bloqueo_capacidad():
    """Agrega un nuevo bloqueo de mantenimiento."""
    data = request.form
    controller = PlanificacionController()
    response, status_code = controller.agregar_bloqueo(data)

    if status_code == 201:
        flash(response.get('message', 'Bloqueo agregado.'), 'success')
    else:
        flash(response.get('error', 'Error al agregar bloqueo.'), 'error')

    return redirect(url_for('planificacion.configuracion_lineas'))

@planificacion_bp.route('/configuracion/eliminar-bloqueo/<int:bloqueo_id>', methods=['POST'])
##@jwt_required()
# @permission_required(accion='configurar_planificacion')
def eliminar_bloqueo_capacidad(bloqueo_id):
    """Elimina un bloqueo de mantenimiento."""
    controller = PlanificacionController()
    response, status_code = controller.eliminar_bloqueo(bloqueo_id)

    if status_code == 200:
        flash(response.get('message', 'Bloqueo eliminado.'), 'success')
    else:
        flash(response.get('error', 'Error al eliminar.'), 'error')

    return redirect(url_for('planificacion.configuracion_lineas'))

@planificacion_bp.route('/configuracion/guardar-produccion', methods=['POST'])
#@jwt_required()
#@permission_required(accion='configurar_planificacion')
def guardar_configuracion_produccion():
    """
    Guarda los parámetros generales de producción, como la tolerancia de sobreproducción.
    """
    from app.controllers.configuracion_controller import ConfiguracionController, TOLERANCIA_SOBREPRODUCCION_PORCENTAJE
    
    controller = ConfiguracionController()
    
    try:
        tolerancia_str = request.form.get(TOLERANCIA_SOBREPRODUCCION_PORCENTAJE, '0')
        tolerancia_val = int(float(tolerancia_str)) # Convertir a float primero para manejar decimales, luego a int
        
        if not (0 <= tolerancia_val <= 100):
            flash('El valor de tolerancia debe ser un número entero entre 0 y 100.', 'warning')
        else:
            response, status_code = controller.actualizar_valor_configuracion(
                TOLERANCIA_SOBREPRODUCCION_PORCENTAJE, 
                tolerancia_val
            )
            if status_code == 200:
                flash(response.get('message', 'Parámetros guardados.'), 'success')
            else:
                flash(response.get('error', 'Error al guardar los parámetros.'), 'error')
                
    except (ValueError, TypeError):
        flash('Valor de tolerancia inválido. Debe ser un número.', 'warning')
    
    return redirect(url_for('planificacion.configuracion_lineas'))
