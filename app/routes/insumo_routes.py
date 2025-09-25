from flask import Blueprint, render_template, request, redirect, url_for, flash
from uuid import UUID
from app.services.insumo_service import InsumoService
from app.repositories.insumo_repository import InsumoRepository
from app.repositories.lote_repository import LoteRepository
from datetime import datetime

insumo_bp = Blueprint('insumo', __name__, url_prefix='/insumos')

# Instanciar repositorios y servicio
insumo_repository = InsumoRepository()
lote_repository = LoteRepository()
insumo_service = InsumoService(insumo_repository, lote_repository)

@insumo_bp.route('/')
def listar():
    """Lista de insumos"""
    categoria = request.args.get('categoria')
    busqueda = request.args.get('busqueda')
    
    insumos = insumo_service.buscar_insumos(categoria=categoria, busqueda=busqueda)
    
    # Obtener categorías únicas para filtros
    todos_insumos = insumo_repository.get_all()
    categorias = sorted(list(set(i.categoria for i in todos_insumos)))
    
    return render_template('insumos/listar.html',
                           insumos=insumos,
                           categorias=categorias,
                           proveedores=[])

@insumo_bp.route('/nuevo', methods=['GET', 'POST'])
def nuevo():
    """Crear nuevo insumo"""
    if request.method == 'POST':
        try:
            insumo_service.crear_insumo(
                codigo=request.form['codigo'],
                nombre=request.form['nombre'],
                unidad_medida=request.form['unidad_medida'],
                categoria=request.form['categoria'],
                stock_minimo=float(request.form['stock_minimo'])
            )
            flash('Insumo creado exitosamente', 'success')
            return redirect(url_for('insumo.listar'))
            
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash(f'Error al crear insumo: {e}', 'error')
    
    return render_template('insumos/formulario.html')

@insumo_bp.route('/<uuid:id>/stock', methods=['POST'])
def actualizar_stock(id: UUID):
    """Actualizar stock de un insumo (placeholder)"""
    # Esta ruta necesita ser implementada con la lógica de negocio correcta
    # (ej: registrar entrada/salida de lote)
    flash('Funcionalidad de actualizar stock no implementada.', 'info')
    return redirect(url_for('insumo.listar'))

@insumo_bp.route('/alertas')
def alertas():
    """Ver alertas de stock bajo"""
    alertas_stock = insumo_service.obtener_alertas_stock_bajo()
    return render_template('insumos/alertas.html', alertas=alertas_stock)

@insumo_bp.route('/<uuid:id>/lote/nuevo', methods=['GET', 'POST'])
def registrar_lote(id: UUID):
    """Registrar un nuevo lote para un insumo."""
    insumo = insumo_repository.get_by_id(id)
    if not insumo:
        flash('Insumo no encontrado.', 'error')
        return redirect(url_for('insumo.listar'))

    if request.method == 'POST':
        try:
            # Lógica para procesar el formulario de nuevo lote
            # ...
            flash('Lote registrado exitosamente (funcionalidad placeholder).', 'success')
            return redirect(url_for('insumo.listar'))
        except Exception as e:
            flash(f'Error al registrar el lote: {e}', 'error')

    return render_template('insumos/registrar_lote.html', insumo=insumo)

