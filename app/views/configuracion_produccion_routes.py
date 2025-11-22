from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.controllers.configuracion_produccion_controller import ConfiguracionProduccionController
from app.utils.decorators import permission_required
from datetime import date

configuracion_produccion_bp = Blueprint('configuracion_produccion', __name__, url_prefix='/admin/configuracion-produccion')

@configuracion_produccion_bp.route('/', methods=['GET', 'POST'])
@permission_required('admin_configuracion_sistema')
def gestionar_configuracion():
    controller = ConfiguracionProduccionController()
    
    # Método POST: Actualizar configuración estándar
    if request.method == 'POST' and request.form.get('action') == 'update_standard':
        # 1. Obtener el mapeo actual para saber qué ID corresponde a qué día
        map_resp = controller.get_configuracion_produccion_map()
        current_map = map_resp.get('data', {}) if map_resp.get('success') else {}

        configs_data = []
        for i in range(1, 8):
            horas = request.form.get(f'horas_{i}')
            db_obj = current_map.get(i)
            if db_obj and horas is not None:
                configs_data.append({
                    'id': db_obj.get('id'),
                    'horas': horas
                })
        
        if configs_data:
            _, status_code = controller.update_configuracion_produccion(configs_data)
            if status_code == 200:
                flash('Configuración de horas estándar actualizada exitosamente.', 'success')
            else:
                flash('Error al actualizar la configuración.', 'error')
        else:
            flash('No se encontraron datos válidos para actualizar.', 'warning')
            
        return redirect(request.url)

    # Método GET (Visualización)
    response_conf = controller.get_configuracion_produccion_map()
    configuraciones = response_conf.get('data', {})
    
    dias_semana = {
        1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves',
        5: 'Viernes', 6: 'Sábado', 7: 'Domingo'
    }

    try:
        today = date.today()
        year = int(request.args.get('year', today.year))
        month = int(request.args.get('month', today.month))
    except ValueError:
        year = today.year
        month = today.month

    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year
    
    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    response_cal, _ = controller.get_calendario_mensual(year, month)
    cal_data = response_cal.get('data', {})

    return render_template('configuracion_produccion/formulario.html', 
                           configuraciones=configuraciones,
                           dias_semana=dias_semana,
                           calendario_data=cal_data.get('calendario', []),
                           total_horas_mes=cal_data.get('total_horas', 0),
                           current_year=year,
                           month_name=cal_data.get('month_name', ''),
                           prev_month=prev_month, prev_year=prev_year,
                           next_month=next_month, next_year=next_year)

@configuracion_produccion_bp.route('/gestionar-excepcion', methods=['POST'])
@permission_required('admin_configuracion_sistema')
def gestionar_excepcion():
    """
    Endpoint AJAX para guardar o eliminar excepciones de calendario.
    Action: 'save' or 'delete'.
    """
    controller = ConfiguracionProduccionController()
    action = request.form.get('action')
    fecha = request.form.get('fecha')

    if not fecha:
        return jsonify({'success': False, 'error': 'Fecha requerida'}), 400

    if action == 'delete':
        response, status_code = controller.eliminar_excepcion(fecha)
    elif action == 'save':
        data = {
            'fecha': fecha,
            'es_laborable': request.form.get('es_laborable'),
            'motivo': request.form.get('motivo'),
            'horas': request.form.get('horas')
        }
        response, status_code = controller.guardar_excepcion(data)
    else:
        return jsonify({'success': False, 'error': 'Acción inválida'}), 400

    if status_code == 200:
        return jsonify({'success': True, 'message': response.get('message')})
    else:
        return jsonify({'success': False, 'error': response.get('error')}), status_code
