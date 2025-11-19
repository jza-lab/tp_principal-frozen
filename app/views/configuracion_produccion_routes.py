from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.controllers.configuracion_produccion_controller import ConfiguracionProduccionController
from app.utils.decorators import permission_required

configuracion_produccion_bp = Blueprint('configuracion_produccion', __name__, url_prefix='/admin/configuracion-produccion')

@configuracion_produccion_bp.route('/', methods=['GET', 'POST'])
@permission_required('admin_configuracion_sistema')
def gestionar_configuracion():
    controller = ConfiguracionProduccionController()
    if request.method == 'POST':
        # El formulario enviará los datos en un formato específico
        # Ej: horas_1, horas_2, etc. para los días de la semana
        configs_data = []
        for i in range(1, 8): # Asumiendo 7 días, Lunes=1 a Domingo=7
            horas = request.form.get(f'horas_{i}')
            if horas is not None:
                configs_data.append({'id': i, 'horas': horas})
        
        _, status_code = controller.update_configuracion_produccion(configs_data)
        if status_code == 200:
            flash('Configuración de producción actualizada exitosamente.', 'success')
        else:
            flash('Error al actualizar la configuración.', 'error')
        return redirect(url_for('configuracion_produccion.gestionar_configuracion'))

    # Método GET
    response, _ = controller.get_configuracion_produccion()
    configuraciones = response.get('data', [])
    # Convertir la lista a un diccionario para fácil acceso en la plantilla
    config_dict = {config['id']: config for config in configuraciones}
    
    dias_semana = {
        1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves',
        5: 'Viernes', 6: 'Sábado', 7: 'Domingo'
    }

    return render_template('configuracion_produccion/formulario.html', 
                           configuraciones=config_dict,
                           dias_semana=dias_semana)
