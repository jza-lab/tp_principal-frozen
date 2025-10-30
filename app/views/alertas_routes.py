from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.controllers.insumo_controller import InsumoController
from app.controllers.configuracion_controller import ConfiguracionController
from app.utils.decorators import permission_required
from app.controllers.producto_controller import ProductoController


alertas_bp = Blueprint('alertas', __name__, url_prefix='/alertas')

@alertas_bp.route('/insumos', methods=['GET'])
@permission_required(accion='ver_alertas')
def listar_insumos_alertas():
    """
    Muestra la lista de insumos para configurar alertas de stock.
    """
    # (Esta ruta también podría beneficiarse de la lógica de 'active_tab'
    # si esa página también tiene pestañas)
    active_tab = request.args.get('tab', 'default') # Ejemplo por si lo necesitás
    
    insumo_controller = InsumoController()
    response, _ = insumo_controller.obtener_insumos()
    if not response.get('success'):
        flash('Error al cargar los insumos.', 'error')
        insumos = []
    else:
        insumos = response.get('data', [])
        
    return render_template('alertas/insumos.html', insumos=insumos, active_tab=active_tab)

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
            
        insumo_controller = InsumoController()
        response, status_code = insumo_controller.actualizar_insumo(insumo_id, update_data)

        if status_code == 200:
            flash('Límites de stock actualizados correctamente.', 'success')
        else:
            flash(f"Error al actualizar: {response.get('error', 'Error desconocido')}", 'error')

    except ValueError:
        flash('Error: El stock mínimo y máximo deben ser números enteros.', 'error')
    except Exception as e:
        flash(f'Ocurrió un error inesperado: {str(e)}', 'error')

    # (Acá también podrías agregar el ?tab=... si la página de insumos tuviera tabs)
    return redirect(url_for('alertas.listar_insumos_alertas'))

@alertas_bp.route('/lotes', methods=['GET', 'POST'])
@permission_required(accion='configurar_alertas')
def configurar_alertas_lotes():
    """
    Permite configurar el umbral de días para alertas de vencimiento de lotes.
    """
    config_controller = ConfiguracionController()
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

@alertas_bp.route('/productos', methods=['GET'])
@permission_required(accion='ver_alertas')
def listar_productos_alertas():
    """
    Muestra la lista de productos para configurar alertas de stock.
    """
    # *** 1. LEER EL PARÁMETRO 'tab' DE LA URL ***
    # Si no se proporciona, 'stock-min' es el valor por defecto.
    active_tab = request.args.get('tab', 'stock-min')
    
    producto_controller = ProductoController()
    response, _ = producto_controller.obtener_todos_los_productos()
    if not response.get('success'):
        flash('Error al cargar los productos.', 'error')
        productos = []
    else:
        productos = response.get('data', [])
        
    # *** 2. PASAR LA VARIABLE 'active_tab' A LA PLANTILLA ***
    return render_template('alertas/productos.html', productos=productos, active_tab=active_tab)

@alertas_bp.route('/productos/actualizar', methods=['POST'])
@permission_required(accion='configurar_alertas')
def actualizar_stock_min_producto():
    """
    Actualiza el stock mínimo de producción para un producto.
    """
    try:
        producto_id = request.form.get('id_producto')
        stock_min_str = request.form.get('stock_min_produccion')

        if not producto_id or stock_min_str is None:
            flash('ID de producto o stock mínimo no proporcionado.', 'error')
            return redirect(url_for('alertas.listar_productos_alertas'))

        stock_min = int(stock_min_str)
        
        producto_controller = ProductoController()
        response, status_code = producto_controller.actualizar_stock_min_produccion(int(producto_id), stock_min)

        if status_code == 200:
            flash('Límite de stock de producción actualizado correctamente.', 'success')
        else:
            flash(f"Error al actualizar: {response.get('error', 'Error desconocido')}", 'error')

    except (ValueError, TypeError):
        flash('Error: El stock mínimo debe ser un número entero.', 'error')
    except Exception as e:
        flash(f'Ocurrió un error inesperado: {str(e)}', 'error')

    # *** 3. REDIRIGIR AVISANDO QUÉ PESTAÑA ESTABA ACTIVA ***
    # (Esta es la pestaña de 'stock-min')
    return redirect(url_for('alertas.listar_productos_alertas', tab='stock-min'))

@alertas_bp.route('/productos/actualizar_cantidad_maxima', methods=['POST'])
@permission_required(accion='configurar_alertas')
def actualizar_cantidad_maxima_x_pedido():
    """
    Actualiza la cantidad máxima por pedido para un producto.
    """
    try:
        producto_id = request.form.get('id_producto')
        cantidad_maxima_str = request.form.get('cantidad_maxima_x_pedido')

        if not producto_id or cantidad_maxima_str is None:
            flash('ID de producto o cantidad máxima no proporcionado.', 'error')
            return redirect(url_for('alertas.listar_productos_alertas'))

        cantidad_maxima = int(cantidad_maxima_str)
        
        producto_controller = ProductoController()
        response, status_code = producto_controller.actualizar_cantidad_maxima_x_pedido(int(producto_id), cantidad_maxima)

        if status_code == 200:
            flash('Cantidad máxima por pedido actualizada correctamente.', 'success')
        else:
            flash(f"Error al actualizar: {response.get('error', 'Error desconocido')}", 'error')

    except (ValueError, TypeError):
        flash('Error: La cantidad máxima debe ser un número entero.', 'error')
    except Exception as e:
        flash(f'Ocurrió un error inesperado: {str(e)}', 'error')

    # *** 3. REDIRIGIR AVISANDO QUÉ PESTAÑA ESTABA ACTIVA ***
    # (Esta es la pestaña de 'cantidad-max')
    return redirect(url_for('alertas.listar_productos_alertas', tab='cantidad-max'))
