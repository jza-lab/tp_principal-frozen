from datetime import date, timedelta
from flask import Blueprint, jsonify, session, request, redirect, url_for, flash, render_template

from app.controllers.usuario_controller import UsuarioController
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.proveedor_controller import ProveedorController
from app.controllers.insumo_controller import InsumoController
from app.permisos import permission_required

# Blueprint para la administración de usuarios
cliente_proveedor = Blueprint('clientes_proveedores', __name__, url_prefix='/administrar')

# Instanciar controladores
proveedor_controller = ProveedorController()
orden_compra_controller = OrdenCompraController()
insumo_controller = InsumoController()
usuario_controller = UsuarioController()

@cliente_proveedor.route('/clientes/')
@permission_required(sector_codigo='ADMINISTRACION', accion='leer')
def listar_clientes():
    clientes=[]
    return render_template('clientes/listar.html', clientes=clientes)

@cliente_proveedor.route('/clientes/<int:id>')
@permission_required(sector_codigo='ADMINISTRACION', accion='leer')
def ver_perfil_cliente(id):
    """Muestra el perfil de un cliente específico."""
    return render_template('clientes/perfil.html')

@cliente_proveedor.route('/clientes/nuevo', methods=['GET', 'POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='crear')
def nuevo_cliente():
    """
    Gestiona la creación de un nuevo cliente
    """
    return render_template('clientes/formulario.html')

@cliente_proveedor.route('/clientes/<int:id>/editar', methods=['GET', 'POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='actualizar')
def editar_cliente(id):
    """Gestiona la edición de un cliente existente"""
    if request.method == 'POST':
        return
    return render_template('clientes/formulario.html')

@cliente_proveedor.route('/clientes/<int:id>/eliminar', methods=['POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='eliminar')
def eliminar_cliente(id):
    """Reactiva un cliente."""
    # resultado = cliente_controller.eliminar_cliente(id)
    # if request.is_json:
    #     return jsonify(resultado)
    
    # if resultado.get('success'):
    #     flash('Usuario desactivado exitosamente.', 'success')
    # else:
    #     flash(f"Error al desactivar el usuario: {resultado.get('error')}", 'error')
    # return redirect(url_for('admin_usuario.listar_usuarios'))
    return

@cliente_proveedor.route('/clientes/<int:id>/habilitar', methods=['POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='actualizar')
def habilitar_cliente(id):
    """Reactiva un cliente."""
    # resultado = usuario_controller.habilitar_usuario(id)
    # if resultado.get('success'):
    #     flash('Usuario activado exitosamente.', 'success')
    # else:
    #     flash(f"Error al activar el usuario: {resultado.get('error')}", 'error')
    # return redirect(url_for('admin_usuario.listar_usuarios'))
    return

#------------------- Proveedores ------------------#

@cliente_proveedor.route('/proveedores/')
@permission_required(sector_codigo='ADMINISTRACION', accion='leer')
def listar_proveedores():
    """Muestra la lista de todos los proveedores del sistema."""
    proveedores_result, status = proveedor_controller.obtener_proveedores()
    proveedores= proveedores_result.get('data', []) if proveedores_result.get('success') else []
    return render_template('proveedores/listar.html', proveedores=proveedores)

@cliente_proveedor.route('/proveedores/<int:id>')
@permission_required(sector_codigo='ADMINISTRACION', accion='leer')
def ver_perfil_proveedor(id):
    proveedor_result, status = proveedor_controller.obtener_proveedor(id)
    proveedor= proveedor_result.get('data') if proveedor_result.get('success') else None
    if not proveedor:
        return redirect(url_for('clientes_proveedores.listar_proveedores'))
    
    insumos_asociados_response, status = insumo_controller.obtener_insumos({"id_proveedor": id})
    insumos_asociados = insumos_asociados_response.get('data', []) if insumos_asociados_response.get('success') else []
    return render_template('proveedores/perfil.html', proveedor=proveedor, insumos_asociados=insumos_asociados)

@cliente_proveedor.route('/proveedores/nuevo', methods=['GET', 'POST', 'PUT'])
@permission_required(sector_codigo='ADMINISTRACION', accion='crear')
def nuevo_proveedor():
    """
    Gestiona la creación de un nuevo proveedor
    """
    try:
        if request.method == 'PUT' or request.method == 'POST':
            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            
            resultado, status = proveedor_controller.crear_proveedor(datos_json)
            
            return jsonify(resultado), status
    except Exception as e:
        flash(f"Error al actualizar el proveedor: {str(e)}", 'error')

    proveedor = None
    return render_template('proveedores/formulario.html', proveedor=proveedor)

@cliente_proveedor.route('/proveedores/<int:id>/editar', methods=['GET', 'POST', 'PUT'])
@permission_required(sector_codigo='ADMINISTRACION', accion='actualizar')
def editar_proveedor(id):
    """Gestiona la edición de un proveedor existente"""
    proveedor_result, status = proveedor_controller.obtener_proveedor(id)
    proveedor= proveedor_result.get('data') if proveedor_result.get('success') else None
    if not proveedor:
        return redirect(url_for('clientes_proveedores.listar_proveedores'))
    try:
        if request.method == 'PUT' or request.method == 'POST':
            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            
            resultado, status = proveedor_controller.actualizar_proveedor(id, datos_json)
            
            return jsonify(resultado), status
    except Exception as e:
        flash(f"Error al actualizar el proveedor: {str(e)}", 'error')
    proveedor_result, status = proveedor_controller.obtener_proveedor(id)
    proveedor= proveedor_result.get('data') if proveedor_result.get('success') else None
    return render_template('proveedores/formulario.html', proveedor=proveedor)

@cliente_proveedor.route('/proveedores/<int:id>/eliminar', methods=['POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='eliminar')
def eliminar_proveedor(id):
    """Desactiva un proveedor."""
    resultado, status = proveedor_controller.eliminar_proveedor(id)
    if request.is_json:
        return jsonify(resultado)
    
    if resultado.get('success'):
        flash('Proveedor desactivado exitosamente.', 'success')
    else:
        flash(f"Error al desactivar el proveedor: {resultado.get('error')}", 'error')
    return redirect(url_for('clientes_proveedores.listar_proveedores'))
    

@cliente_proveedor.route('/proveedores/<int:id>/habilitar', methods=['POST'])
@permission_required(sector_codigo='ADMINISTRACION', accion='actualizar')
def habilitar_proveedor(id):
    """Reactiva un proveedor."""
    resultado, status = proveedor_controller.habilitar_proveedor(id)
    if request.is_json:
        return jsonify(resultado)
    
    if resultado.get('success'):
        flash('Proveedor activado exitosamente.', 'success')
    else:
        flash(f"Error al activar el proveedor: {resultado.get('error')}", 'error')
    return redirect(url_for('clientes_proveedores.listar_proveedores'))
    