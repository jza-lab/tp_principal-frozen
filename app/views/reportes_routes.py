from flask import Blueprint, render_template, jsonify, request
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
    fecha_inicio_str = request.args.get('fecha_inicio')
    fecha_fin_str = request.args.get('fecha_fin')
    
    kpis_produccion = indicadores_controller.obtener_kpis_produccion(fecha_inicio_str, fecha_fin_str)
    
    # Parsear fechas para KPIs de calidad e inventario
    if fecha_inicio_str:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
    else:
        fecha_inicio = datetime.now() - timedelta(days=30)

    if fecha_fin_str:
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
    else:
        fecha_fin = datetime.now()

    kpis_calidad = indicadores_controller.obtener_kpis_calidad(fecha_inicio, fecha_fin)
    kpis_inventario = indicadores_controller.obtener_kpis_inventario(fecha_inicio_str, fecha_fin_str)
    kpis_comercial = indicadores_controller.obtener_kpis_comercial(fecha_inicio, fecha_fin)

    kpis = {
        "produccion": kpis_produccion,
        "calidad": kpis_calidad,
        "inventario": kpis_inventario,
        "comercial": kpis_comercial,
        "fecha_inicio": kpis_produccion['fecha_inicio'],
        "fecha_fin": kpis_produccion['fecha_fin']
    }
    
    return render_template('indicadores/dashboard.html', kpis=kpis)
