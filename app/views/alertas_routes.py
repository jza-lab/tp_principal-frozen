from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.controllers.insumo_controller import InsumoController
from app.controllers.configuracion_controller import ConfiguracionController
from app.utils.decorators import permission_required

alertas_bp = Blueprint('alertas', __name__, url_prefix='/alertas')
insumo_controller = InsumoController()
config_controller = ConfiguracionController()

@alertas_bp.route('/insumos', methods=['GET'])
@permission_required(accion='ver_alertas')
def listar_insumos_alertas():
    """
    Muestra la lista de insumos para configurar alertas de stock.
    """
    response, _ = insumo_controller.obtener_insumos()
    if not response.get('success'):
        flash('Error al cargar los insumos.', 'error')
        insumos = []
    else:
        insumos = response.get('data', [])
        
    return render_template('alertas/insumos.html', insumos=insumos)

@alertas_bp.route('/insumos/actualizar', methods=['POST'])
@permission_required(accion='configurar_alertas')
def actualizar_stock_min_max():
    """
    Actualiza el stock mínimo y máximo para un insumo.
    """
    try:
        insumo_id = request.form.get('id_insumo')
        stock_min = request.form.get('stock_min')
        stock_max = request.form.get('stock_max')
        
        if not insumo_id:
            flash('ID de insumo no proporcionado.', 'error')
            return redirect(url_for('alertas.listar_insumos_alertas'))

        update_data = {}
        if stock_min is not None and stock_min.strip() != '':
            update_data['stock_min'] = int(stock_min)
        if stock_max is not None and stock_max.strip() != '':
            update_data['stock_max'] = int(stock_max) # OJO, este campo no existe

        if not update_data:
            flash('No se proporcionaron datos para actualizar.', 'warning')
            return redirect(url_for('alertas.listar_insumos_alertas'))
            
        response, status_code = insumo_controller.actualizar_insumo(insumo_id, update_data)

        if status_code == 200:
            flash('Límites de stock actualizados correctamente.', 'success')
        else:
            flash(f"Error al actualizar: {response.get('error', 'Error desconocido')}", 'error')

    except ValueError:
        flash('Error: El stock mínimo y máximo deben ser números enteros.', 'error')
    except Exception as e:
        flash(f'Ocurrió un error inesperado: {str(e)}', 'error')

    return redirect(url_for('alertas.listar_insumos_alertas'))

@alertas_bp.route('/lotes', methods=['GET', 'POST'])
@permission_required(accion='configurar_alertas')
def configurar_alertas_lotes():
    """
    Permite configurar el umbral de días para alertas de vencimiento de lotes.
    """
    if request.method == 'POST':
        dias_vencimiento = request.form.get('dias_vencimiento')
        try:
            dias = int(dias_vencimiento)
            response, status_code = config_controller.guardar_dias_vencimiento(dias)
            
            if status_code == 200:
                flash(response.get('message', 'Configuración guardada.'), 'success')
            else:
                flash(response.get('error', 'Error al guardar.'), 'error')

        except (ValueError, TypeError):
            flash('Por favor, ingrese un número válido de días.', 'error')
        
        return redirect(url_for('alertas.configurar_alertas_lotes'))

    dias_vencimiento_actual = config_controller.obtener_dias_vencimiento()
    
    return render_template('alertas/lotes.html', dias_vencimiento=dias_vencimiento_actual)
