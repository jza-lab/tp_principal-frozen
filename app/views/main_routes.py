from flask import Blueprint, jsonify, redirect, url_for, render_template, request, send_from_directory
from flask_jwt_extended import jwt_required
from app.models.producto import ProductoModel
from app.models.cliente import ClienteModel
from app.models.pedido import PedidoModel
from app.models.orden_compra_model import OrdenCompraModel
from app.models.orden_produccion import OrdenProduccionModel

main_bp = Blueprint('main_routes', __name__)

@main_bp.route('/')
def index():
    """Ruta raíz que redirige al login."""
    return redirect(url_for('auth.login'))

@main_bp.route('/service-worker.js')
def service_worker():
    """Sirve el archivo service-worker.js desde la raíz."""
    response = send_from_directory('static', 'service-worker.js', mimetype='application/javascript')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@main_bp.route('/search')
@jwt_required()
def search_page():
    """Renderiza la página de búsqueda dedicada."""
    return render_template('search/index.html')

@main_bp.route('/search/results')
@jwt_required()
def global_search_results():
    query_string = request.args.get('q', '').strip()
    results = {}

    if query_string:
        # Busca Productos
        results['productos'] = ProductoModel().find_all(filters={'busqueda': query_string}, limit=10).get('data', [])

        # Busca Clientes
        results['clientes'] = ClienteModel().get_all(filtros={'busqueda': query_string}, limit=10).get('data', [])

        # Busca Pedidos por ID
        if query_string.isdigit() and len(query_string) < 10:
            try:
                pedido_id = int(query_string)
                pedido_result = PedidoModel().get_one_with_items(pedido_id)
                if pedido_result.get('success'):
                    pedidos = [pedido_result.get('data')]
                    results['pedidos'] = pedidos

                    # Reverse relational search
                    for pedido in pedidos:
                        if pedido.get('items'):
                            for item in pedido.get('items'):
                                if item.get('orden_produccion_id'):
                                    op_result = OrdenProduccionModel().get_one_enriched(item.get('orden_produccion_id'))
                                    if op_result.get('success'):
                                        op = op_result.get('data')
                                        if not any(o['id'] == op['id'] for o in results.get('ordenes_produccion', [])):
                                            results.setdefault('ordenes_produccion', []).append(op)
                else:
                    results['pedidos'] = []
            except ValueError:
                results['pedidos'] = []
        else:
            results['pedidos'] = []

        # Busca Órdenes de Compra por código
        orden_compra_result = OrdenCompraModel().find_by_codigo(query_string)
        if orden_compra_result.get('success'):
            ordenes_compra = [orden_compra_result.get('data')]
            results['ordenes_compra'] = ordenes_compra

            # Relational search OC -> OP
            for oc in ordenes_compra:
                if oc.get('orden_produccion_id'):
                    op_result = OrdenProduccionModel().get_one_enriched(oc.get('orden_produccion_id'))
                    if op_result.get('success'):
                        op = op_result.get('data')
                        if not any(o['id'] == op['id'] for o in results.get('ordenes_produccion', [])):
                            results.setdefault('ordenes_produccion', []).append(op)
        else:
            results['ordenes_compra'] = []

        # Busca Órdenes de Producción por código
        orden_produccion_result = OrdenProduccionModel().get_all_enriched(filtros={'codigo': query_string})
        if orden_produccion_result.get('success'):
            ordenes_produccion = orden_produccion_result.get('data', [])
            for op in ordenes_produccion:
                if not any(o['id'] == op['id'] for o in results.get('ordenes_produccion', [])):
                    results.setdefault('ordenes_produccion', []).append(op)

            # Enhanced relational search
            for op in ordenes_produccion:
                # Find related sales orders
                if op.get('pedidos_asociados'):
                    for pedido in op.get('pedidos_asociados'):
                        if not any(p['id'] == pedido['id'] for p in results.get('pedidos', [])):
                            results.setdefault('pedidos', []).append(pedido)

                # Find related purchase orders
                oc_result = OrdenCompraModel().get_all(filters={'orden_produccion_id': op['id']})
                if oc_result.get('success'):
                    for oc in oc_result.get('data', []):
                        if not any(o['id'] == oc['id'] for o in results.get('ordenes_compra', [])):
                            results.setdefault('ordenes_compra', []).append(oc)
        else:
            results['ordenes_produccion'] = []

    return render_template('search/results.html', results=results, query_string=query_string)

@main_bp.route('/api/health')
def health_check():
    """Endpoint de health check para verificar que la API está funcionando."""
    return jsonify({
        'status': 'ok',
        'message': 'API de Trazabilidad de Insumos funcionando correctamente',
        'version': '1.0.0'
    })
