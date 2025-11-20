from flask import Blueprint, redirect, render_template, jsonify, request, url_for
from datetime import datetime, timedelta
from app.controllers.reportes_controller import ReportesController
from app.controllers.reporte_produccion_controller import ReporteProduccionController
from app.controllers.reporte_stock_controller import ReporteStockController
from app.controllers.indicadores_controller import IndicadoresController

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')
controller = ReportesController()
produccion_controller = ReporteProduccionController()
stock_controller = ReporteStockController()
indicadores_controller = IndicadoresController()

@reportes_bp.route('/')
def dashboard():
    return render_template('reportes/dashboard.html')

@reportes_bp.route('/api/ingresos_vs_egresos')
def api_ingresos_vs_egresos():
    periodo = request.args.get('periodo', 'semanal')
    data = controller.obtener_ingresos_vs_egresos(periodo)
    return jsonify(data)

@reportes_bp.route('/api/top_productos')
def api_top_productos():
    data = controller.obtener_top_productos()
    return jsonify(data)

@reportes_bp.route('/api/stock_critico')
def api_stock_critico():
    data = controller.obtener_stock_critico()
    return jsonify(data)

@reportes_bp.route('/produccion')
def produccion():
    return render_template('reportes/produccion.html')

# API Endpoints for Production Reports
@reportes_bp.route('/api/produccion/ordenes_por_estado')
def api_ordenes_por_estado():
    data = produccion_controller.obtener_ordenes_por_estado()
    return jsonify(data)

@reportes_bp.route('/api/produccion/composicion_produccion')
def api_composicion_produccion():
    data = produccion_controller.obtener_composicion_produccion()
    return jsonify(data)

@reportes_bp.route('/api/produccion/top_insumos')
def api_top_insumos():
    top_n = request.args.get('top_n', 5, type=int)
    data = produccion_controller.obtener_top_insumos(top_n)
    return jsonify(data)

@reportes_bp.route('/api/produccion/tiempo_ciclo_promedio')
def api_tiempo_ciclo_promedio():
    data = produccion_controller.obtener_tiempo_ciclo_promedio()
    return jsonify(data)

# @reportes_bp.route('/api/produccion/eficiencia_produccion')
# def api_eficiencia_produccion():
#     data = produccion_controller.obtener_eficiencia_produccion()
#     return jsonify(data)

@reportes_bp.route('/api/produccion/produccion_por_tiempo')
def api_produccion_por_tiempo():
    periodo = request.args.get('periodo', 'semanal')
    data = produccion_controller.obtener_produccion_por_tiempo(periodo)
    return jsonify(data)

@reportes_bp.route('/stock')
def stock():
    return render_template('reportes/stock.html')

# --- API Endpoints for Stock Reports ---

# Insumos
@reportes_bp.route('/api/stock/insumos/composicion')
def api_stock_insumos_composicion():
    data = stock_controller.obtener_composicion_stock_insumos()
    return jsonify(data)

@reportes_bp.route('/api/stock/insumos/valor')
def api_stock_insumos_valor():
    top_n = request.args.get('top_n', 10, type=int)
    data = stock_controller.obtener_valor_stock_insumos(top_n)
    return jsonify(data)

@reportes_bp.route('/api/stock/insumos/critico')
def api_stock_insumos_critico():
    data = stock_controller.obtener_insumos_stock_critico()
    return jsonify(data)

@reportes_bp.route('/api/stock/insumos/vencimiento')
def api_stock_insumos_vencimiento():
    dias = request.args.get('dias', 30, type=int)
    data = stock_controller.obtener_lotes_insumos_a_vencer(dias)
    return jsonify(data)

# Productos
@reportes_bp.route('/api/stock/productos/composicion')
def api_stock_productos_composicion():
    data = stock_controller.obtener_composicion_stock_productos()
    return jsonify(data)

@reportes_bp.route('/api/stock/productos/valor')
def api_stock_productos_valor():
    top_n = request.args.get('top_n', 10, type=int)
    data = stock_controller.obtener_valor_stock_productos(top_n)
    return jsonify(data)

@reportes_bp.route('/api/stock/productos/sin_stock')
def api_stock_productos_sin_stock():
    data = stock_controller.obtener_productos_sin_stock()
    return jsonify(data)

@reportes_bp.route('/api/stock/productos/vencimiento')
def api_stock_productos_vencimiento():
    dias = request.args.get('dias', 30, type=int)
    data = stock_controller.obtener_lotes_productos_a_vencer(dias)
    return jsonify(data)

@reportes_bp.route('/api/stock/productos/valor_por_categoria')
def api_stock_productos_valor_por_categoria():
    data = stock_controller.obtener_valor_stock_por_categoria_producto()
    return jsonify(data)

@reportes_bp.route('/api/stock/productos/distribucion_por_estado')
def api_stock_productos_distribucion_por_estado():
    data = stock_controller.obtener_distribucion_stock_por_estado_producto()
    return jsonify(data)

@reportes_bp.route('/api/stock/productos/rotacion')
def api_stock_productos_rotacion():
    data = stock_controller.obtener_rotacion_productos()
    return jsonify(data)

@reportes_bp.route('/api/stock/productos/cobertura')
def api_stock_productos_cobertura():
    data = stock_controller.obtener_cobertura_stock()
    return jsonify(data)

@reportes_bp.route('/indicadores')
def indicadores():
    return render_template('indicadores/dashboard.html')

@reportes_bp.route('/api/indicadores/<categoria>')
def api_indicadores_por_categoria(categoria):
    """
    Endpoint genérico de la API para obtener los datos de una categoría de indicador específica.
    """
    # Recoge los nuevos parámetros de la solicitud.
    semana = request.args.get('semana')
    mes = request.args.get('mes')
    ano = request.args.get('ano')

    # Mapeo de categorías a las nuevas funciones del controlador
    mapa_funciones = {
        'produccion': indicadores_controller.obtener_kpis_produccion,
        'calidad': indicadores_controller.obtener_datos_calidad,
        'comercial': indicadores_controller.obtener_datos_comercial,
        'financiera': indicadores_controller.obtener_datos_financieros,
        'inventario': indicadores_controller.obtener_datos_inventario
    }

    if categoria not in mapa_funciones:
        return jsonify({"error": "Categoría no válida"}), 404

    # Llama a la función correspondiente y devuelve los datos
    funcion_controlador = mapa_funciones[categoria]
        # Preparamos argumentos comunes
    kwargs = {
        'semana': request.args.get('semana'),
        'mes': request.args.get('mes'),
        'ano': request.args.get('ano')
    }
    
    # Argumentos específicos por categoría (para evitar errores de firma)
    if categoria == 'produccion':
        kwargs['top_n'] = request.args.get('top_n', 5, type=int) # Default 10
        
    
    datos = funcion_controlador(**kwargs)
    return jsonify(datos)

@reportes_bp.route('/api/indicadores/anos-disponibles')
def api_anos_disponibles():
    """Devuelve los años en los que hay registros de pedidos."""
    anos = indicadores_controller.obtener_anos_disponibles()
    return jsonify(anos)

@reportes_bp.route('/api/ventas/facturacion')
def api_ventas_facturacion():
    fecha_inicio_str = request.args.get('fecha_inicio')
    fecha_fin_str = request.args.get('fecha_fin')
    periodo = request.args.get('periodo', 'mensual')
    data = indicadores_controller.obtener_facturacion_por_periodo(fecha_inicio_str, fecha_fin_str, periodo)
    return jsonify(data)

@reportes_bp.route('/api/finanzas/costo_vs_ganancia')
def api_finanzas_costo_vs_ganancia():
    fecha_inicio_str = request.args.get('fecha_inicio')
    fecha_fin_str = request.args.get('fecha_fin')
    periodo = request.args.get('periodo', 'mensual')
    data = indicadores_controller.obtener_costo_vs_ganancia(fecha_inicio_str, fecha_fin_str, periodo)
    return jsonify(data)

@reportes_bp.route('/api/finanzas/descomposicion_costos')
def api_finanzas_descomposicion_costos():
    fecha_inicio_str = request.args.get('fecha_inicio')
    fecha_fin_str = request.args.get('fecha_fin')
    data = indicadores_controller.obtener_descomposicion_costos(fecha_inicio_str, fecha_fin_str)
    return jsonify(data)

# --- API Endpoints for Clientes Reports ---
@reportes_bp.route('/api/clientes/top_clientes')
def api_clientes_top_clientes():
    fecha_inicio_str = request.args.get('fecha_inicio')
    fecha_fin_str = request.args.get('fecha_fin')
    top_n = request.args.get('top_n', 5, type=int)
    criterio = request.args.get('criterio', 'valor')
    data = indicadores_controller.obtener_top_clientes(fecha_inicio_str, fecha_fin_str, top_n, criterio)
    return jsonify(data)

# --- API Endpoints for Produccion Reports ---
@reportes_bp.route('/api/produccion/causas_desperdicio')
def api_produccion_causas_desperdicio():
    fecha_inicio_str = request.args.get('fecha_inicio')
    fecha_fin_str = request.args.get('fecha_fin')
    data = indicadores_controller.obtener_causas_desperdicio(fecha_inicio_str, fecha_fin_str)
    return jsonify(data)

# --- API Endpoints for Inventario Reports ---
@reportes_bp.route('/api/inventario/antiguedad_stock')
def api_inventario_antiguedad_stock():
    tipo = request.args.get('tipo', 'insumo')
    data = indicadores_controller.obtener_antiguedad_stock(tipo)
    return jsonify(data)

@reportes_bp.route('/configuracion', methods=['GET', 'POST'])
def configuracion():
    if request.method == 'POST':
        # Lógica para guardar la configuración
        meta_flujo_caja = request.form.get('meta_flujo_caja')
        controller.guardar_meta_flujo_caja(meta_flujo_caja)
        # Podríamos añadir un flash message aquí
        return redirect(url_for('reportes.configuracion'))
    
    # Lógica para mostrar la página de configuración
    config = controller.obtener_configuracion_metas()
    return render_template('reportes/configuracion.html', config=config)