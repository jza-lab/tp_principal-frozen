from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.services.materia_prima_service import MateriaPrimaService
from app.repositories.materia_prima_repository import MateriaPrimaRepository
from app.repositories.movimiento_stock_repository import MovimientoStockRepository
from datetime import datetime

materia_prima_bp = Blueprint('materia_prima', __name__, url_prefix='/materias-primas')

# Instanciar repositorios
materia_prima_repository = MateriaPrimaRepository()
movimiento_stock_repository = MovimientoStockRepository()

# Instanciar servicio con inyección de dependencias
materia_prima_service = MateriaPrimaService(materia_prima_repository, movimiento_stock_repository)

@materia_prima_bp.route('/')
def listar():
    """Lista de materias primas"""
    categoria = request.args.get('categoria')
    busqueda = request.args.get('busqueda')
    
    materias_primas = materia_prima_service.buscar_materias_primas(categoria=categoria, busqueda=busqueda)
    
    # Obtener categorías únicas para filtros
    todas_materias = materia_prima_service.repository.obtener_todas()
    categorias = sorted(list(set(mp.categoria for mp in todas_materias)))
    
    return render_template('materias_primas/listar.html', ##Cambiar html del front
                         materias_primas=materias_primas,
                         categorias=categorias,
                         proveedores=[]) # Se envía una lista vacía para no romper el template

@materia_prima_bp.route('/nueva', methods=['GET', 'POST'])
def nueva():
    """Crear nueva materia prima"""
    if request.method == 'POST':
        try:
            materia_prima = materia_prima_service.crear_materia_prima(
                codigo=request.form['codigo'],
                nombre=request.form['nombre'],
                unidad=request.form['unidad'],
                proveedor=request.form['proveedor'],
                categoria=request.form['categoria'],
                stock_minimo=float(request.form['stock_minimo'])
            )
            
            flash('Materia prima creada exitosamente', 'success')
            return redirect(url_for('materia_prima.listar')) ##Cambiar html del front
            
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash('Error al crear materia prima', 'error')
    
    return render_template('materias_primas/formulario.html') ##Cambiar html del front

@materia_prima_bp.route('/<int:id>/stock', methods=['POST'])
def actualizar_stock():
    """Actualizar stock de materia prima"""
    try:
        id = request.form['materia_prima_id']
        tipo = request.form['tipo_movimiento']  # ENTRADA o SALIDA
        cantidad = float(request.form['cantidad'])
        observaciones = request.form.get('observaciones', '')
        
        # PLACEHOLDER DE DESARROLLO:
        # El ID de usuario está hardcodeado. En un entorno de producción,
        # esto debe ser reemplazado por el ID del usuario autenticado en la sesión:
        # usuario_id = session.get('usuario_id')
        usuario_id_placeholder = 1
        flash(f"Acción realizada por el usuario ID {usuario_id_placeholder} (placeholder). La autenticación real debe ser implementada.", "warning")

        if tipo == 'ENTRADA':
            materia_prima_service.actualizar_stock_entrada(
                materia_prima_id=id,
                cantidad=cantidad,
                usuario_id=usuario_id_placeholder,
                observaciones=observaciones
            )
        else:
            materia_prima_service.actualizar_stock_salida(
                materia_prima_id=id,
                cantidad=cantidad,
                usuario_id=usuario_id_placeholder,
                observaciones=observaciones
            )
        
        flash('Stock actualizado correctamente', 'success')
        
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        flash('Error al actualizar stock', 'error')
    
    return redirect(url_for('materia_prima.listar')) ##Cambiar html del front

@materia_prima_bp.route('/alertas')
def alertas():
    """Ver alertas de stock bajo"""
    alertas_stock = materia_prima_service.obtener_alertas_stock_bajo()
    return render_template('materias_primas/alertas.html', alertas=alertas_stock) ##Cambiar html del front
