from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from app.controllers.insumo_controller import InsumoController
from app.controllers.configuracion_controller import ConfiguracionController
from marshmallow import ValidationError
from app.utils.decorators import permission_required
from app.controllers.producto_controller import ProductoController
from decimal import Decimal, InvalidOperation

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
    insumo_controller = InsumoController()
    insumo_id = request.form.get('id_insumo')

    try:
        stock_min = request.form.get('stock_min')
        stock_max = request.form.get('stock_max')

        if not insumo_id:
            flash('ID de insumo no proporcionado.', 'error')
            return redirect(url_for('alertas.listar_insumos_alertas'))

        update_data = {}
        if stock_min is not None and stock_min.strip() != '':
            valor_stock_min = int(stock_min)
            if valor_stock_min > 1000000000:
                flash('El stock mínimo no puede ser mayor a 1,000,000,000.', 'error')
                return redirect(url_for('alertas.listar_insumos_alertas'))
            update_data['stock_min'] = valor_stock_min

        if stock_max is not None and stock_max.strip() != '':
            valor_stock_max = int(stock_max)
            if valor_stock_max > 1000000000:
                flash('El stock máximo no puede ser mayor a 1,000,000,000.', 'error')
                return redirect(url_for('alertas.listar_insumos_alertas'))
            update_data['stock_max'] = valor_stock_max

        if not update_data:
            flash('No se proporcionaron datos para actualizar.', 'warning')
            return redirect(url_for('alertas.listar_insumos_alertas'))

        response, status_code = insumo_controller.actualizar_insumo(insumo_id, update_data)

        if status_code == 200:
            flash('Límites de stock actualizados correctamente.', 'success')
        else:
            flash(f"Error al actualizar: {response.get('error', 'Error desconocido')}", 'error')

    except ValidationError as e:
        error_list = '<ul class="list-unstyled mb-0">'
        if isinstance(e.messages, dict):
            for field, messages in e.messages.items():
                for message in messages:
                    error_list += f"<li>{message}</li>"
        else:
            error_list += f"<li>{e.messages}</li>"
        error_list += '</ul>'
        flash(error_list, 'error')

    except ValueError:
        flash('Error: El stock mínimo y máximo deben ser números enteros.', 'error')
    except Exception as e:
        flash(f'Ocurrió un error inesperado: {str(e)}', 'error')

    return redirect(url_for('alertas.listar_insumos_alertas'))

@alertas_bp.route('/lotes', methods=['GET', 'POST'])
@permission_required(accion='configurar_alertas')
def configurar_alertas_lotes():
    """
    Permite configurar el umbral de días para alertas de vencimiento de lotes
    y los umbrales del semáforo de vida útil.
    """
    config_controller = ConfiguracionController()
    config_model = config_controller.model
    
    if request.method == 'POST':
        dias_vencimiento = request.form.get('dias_vencimiento')
        sem_verde = request.form.get('sem_verde')
        sem_amarillo = request.form.get('sem_amarillo')
        
        try:
            if dias_vencimiento:
                dias = int(dias_vencimiento)
                # Se guarda la configuración de días de alerta (urgencia)
                response, status_code = config_controller.guardar_dias_vencimiento(dias)
                if status_code != 200:
                     flash(response.get('error', 'Error al guardar días vencimiento.'), 'error')

            # Guardar configuración semáforos directamente
            if sem_verde and sem_amarillo:
                config_model.guardar_valor('UMBRAL_VIDA_UTIL_VERDE', int(sem_verde))
                config_model.guardar_valor('UMBRAL_VIDA_UTIL_AMARILLO', int(sem_amarillo))
            
            flash('Configuración guardada.', 'success')

        except (ValueError, TypeError):
            flash('Por favor, ingrese números válidos.', 'error')

        return redirect(url_for('alertas.configurar_alertas_lotes'))

    dias_vencimiento_actual = config_controller.obtener_dias_vencimiento()
    
    # Obtener valores actuales o defaults para el semáforo
    sem_verde = config_model.obtener_valor('UMBRAL_VIDA_UTIL_VERDE', 75)
    sem_amarillo = config_model.obtener_valor('UMBRAL_VIDA_UTIL_AMARILLO', 50)

    return render_template(
        'alertas/lotes.html', 
        dias_vencimiento=dias_vencimiento_actual,
        sem_verde=sem_verde,
        sem_amarillo=sem_amarillo
    )

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
        producto_info = producto_controller.obtener_producto_por_id(int(producto_id))

        if not producto_info.get('success'):
            flash('Producto no encontrado.', 'error')
            return redirect(url_for('alertas.listar_productos_alertas', tab='stock-min'))

        producto = producto_info.get('data')
        cantidad_maxima = producto.get('cantidad_maxima_x_pedido')

        if cantidad_maxima is not None and stock_min > cantidad_maxima:
            flash('El stock mínimo no puede ser mayor que la cantidad máxima por pedido.', 'error')
            return redirect(url_for('alertas.listar_productos_alertas', tab='stock-min'))

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

        if cantidad_maxima > 1000000000:
            flash('La cantidad máxima no puede ser mayor a 1,000,000,000.', 'error')
            return redirect(url_for('alertas.listar_productos_alertas', tab='cantidad-max'))

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

@alertas_bp.route('/productos/actualizar-minimo-produccion', methods=['POST'])
def actualizar_minimo_produccion():

    # 1. Validar la entrada (Try/Except)
    try:
        producto_id = request.form.get('id_producto')
        cantidad_minima = Decimal(request.form.get('cantidad_minima_produccion'))
    except (InvalidOperation, TypeError):
        # Error de tipo de dato: Flashear y redirigir
        flash('Valor de cantidad mínima inválido. Debe ser un número.', 'danger')
        return redirect(url_for('alertas.listar_productos_alertas', tab='cant-min-prod'))

    # 2. Validar la lógica del negocio
    if producto_id and cantidad_minima >= 0:
        producto_controller = ProductoController()
        resp, status = producto_controller.actualizar_cantidad_minima_produccion(producto_id, cantidad_minima)

        # 3. Flashear el resultado (éxito o error)
        if status == 200:
            flash('Cantidad mínima de producción actualizada.', 'success')
        else:
            flash(resp.get('error', 'Error al actualizar.'), 'danger')
    else:
        # Error de datos (ej. ID faltante o cantidad negativa)
        flash('Datos inválidos (ID de producto o cantidad negativa).', 'danger')

    # 4. Redirigir siempre a la pestaña correcta
    # Esta ruta es usada por las otras funciones de POST en tu archivo
    return redirect(url_for('alertas.listar_productos_alertas', tab='cant-min-prod'))
