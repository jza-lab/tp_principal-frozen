from flask import Blueprint, request, jsonify, send_file, render_template, Flask
from werkzeug.utils import secure_filename
import pandas as pd
import logging
from datetime import datetime
from io import BytesIO

from app.controllers.producto_controller import ProductoController
from app.controllers.proveedor_controller import ProveedorController
from app.controllers.insumo_controller import InsumoController
from app.controllers.historial_precios_controller import HistorialPreciosController
from app.permisos import permission_required

precios_bp = Blueprint('precios', __name__)
logger = logging.getLogger(__name__)

# Instancias de controllers
proveedor_controller = ProveedorController()
insumo_controller = InsumoController()
historial_controller = HistorialPreciosController()
producto_controller = ProductoController()

@precios_bp.route('/actualizar-precios')
@permission_required(sector_codigo='LOGISTICA', accion='actualizar')
def index():
    return render_template('precios_proveedores_files/actualizar_precios_proveedores.html')

@precios_bp.route('/api/precios/cargar-archivo-proveedor', methods=['POST'])
@permission_required(sector_codigo='LOGISTICA', accion='actualizar')
def cargar_archivo_precios_proveedor():
    """
    Endpoint para cargar archivo Excel con precios de proveedores - VERSIÓN SIMPLIFICADA
    """

    try:
        if 'archivo' not in request.files:
            return jsonify({'success': False, 'error': 'No se envió archivo'}), 400

        archivo = request.files['archivo']
        usuario = request.form.get('usuario', 'sistema')

        if archivo.filename == '':
            return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400

        if not archivo.filename.lower().endswith(('.xlsx', '.xls')):
            return jsonify({'success': False, 'error': 'Solo se aceptan archivos Excel'}), 400

        # Procesar archivo (ya devuelve formato frontend)
        resultados = procesar_archivo_proveedor(archivo, usuario)

        # Generar reporte
        reporte = generar_reporte_consolidado(resultados)

        return jsonify({
            'success': True,
            'message': 'Archivo procesado exitosamente',
            'reporte': reporte,
            'detalles': resultados  # Ya está en formato correcto
        })

    except Exception as e:
        logger.error(f"Error cargando archivo de precios: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def adaptar_resultados_frontend(resultados):
    """
    Adapta los resultados de procesar_archivo_proveedor al formato del frontend
    """
    detalles = []

    for resultado in resultados:
        # Mapear estados al formato que espera el frontend
        estado_original = resultado.get('estado', 'ERROR')

        if estado_original == 'ACTUALIZADO':
            estado_frontend = 'ACTUALIZADO'
        elif estado_original == 'SIN_CAMBIOS':
            estado_frontend = 'SIN_CAMBIOS'
        elif 'ERROR' in estado_original:
            estado_frontend = 'ERROR'
        else:
            estado_frontend = 'ERROR'  # Por defecto

        # Construir el detalle en el formato esperado
        detalle = {
            'fila': resultado.get('fila', 0),
            'codigo_interno': resultado.get('codigo_interno', ''),
            'producto': resultado.get('producto', ''),
            'proveedor': resultado.get('proveedor', ''),
            'estado': estado_frontend,
            'mensaje': resultado.get('mensaje', '')
        }

        # Si falta producto, intentar obtenerlo de otra forma
        if not detalle['producto']:
            detalle['producto'] = resultado.get('nombre', 'Producto no especificado')

        # Si falta proveedor, poner uno por defecto
        if not detalle['proveedor']:
            detalle['proveedor'] = 'Proveedor no identificado'

        detalles.append(detalle)

    return detalles

def generar_reporte_consolidado(detalles):
    """Genera reporte resumen del procesamiento en formato frontend"""
    total = len(detalles)
    actualizados = len([r for r in detalles if r.get('estado') == 'ACTUALIZADO'])
    errores = len([r for r in detalles if r.get('estado') == 'ERROR'])
    sin_cambios = len([r for r in detalles if r.get('estado') == 'SIN_CAMBIOS'])

    return {
        'total_filas': total,
        'actualizados': actualizados,
        'errores': errores,
        'sin_cambios': sin_cambios,
        'fecha_procesamiento': datetime.now().isoformat()
    }

def procesar_archivo_proveedor(archivo, usuario):
    """
    Procesa el archivo Excel usando los controllers - VERSIÓN CON FORMATO FRONTEND
    """
    try:
        datos = pd.read_excel(archivo)
        resultados = []
        insumos_actualizados = [] 

        for indice, fila in datos.iterrows():
            # Usar controller para buscar proveedor
            proveedor = proveedor_controller.buscar_por_identificacion(fila.to_dict())

            if not proveedor:
                resultados.append({
                    'fila': indice + 2,  # +2 porque Excel empieza en 1 y header en 1
                    'codigo_interno': fila.get('codigo_interno', 'Desconocido'),
                    'producto': fila.get('descripcion', 'Producto no especificado'),
                    'proveedor': 'No identificado',
                    'estado': 'ERROR',  # Formato directo para frontend
                    'mensaje': 'Proveedor no encontrado. Verifique email/CUIL'
                })
                continue

            # Usar controller para buscar insumo
            codigo_buscar = fila.get('codigo_interno')
            print('SE ESTA BUSCANDO---', codigo_buscar)
            insumo = insumo_controller.buscar_por_codigo_interno(codigo_buscar)

            if not insumo:
                resultados.append({
                    'fila': indice + 2,
                    'codigo_interno': codigo_buscar,
                    'producto': fila.get('descripcion', 'Producto no especificado'),
                    'proveedor': proveedor['nombre'],
                    'estado': 'ERROR',  # Formato directo para frontend
                    'mensaje': f'Insumo con código {codigo_buscar} no encontrado en catálogo'
                })
                continue

            # Procesar actualización de precio
            resultado = procesar_actualizacion_precio(insumo, proveedor, fila, usuario)
            if resultado.get('insumo_actualizado'):
                insumos_actualizados.append(resultado['insumo_actualizado'])
            resultado['fila'] = indice + 2
            resultado['proveedor'] = proveedor['nombre']
            resultado['codigo_interno'] = insumo['codigo_interno']
            resultado['producto'] = insumo['nombre']

            if 'insumo_actualizado' in resultado:
                 del resultado['insumo_actualizado']

            resultados.append(resultado)
            if insumos_actualizados:
                logger.info(f"Actualizando precios de productos para {len(insumos_actualizados)} insumos únicos.")
                
                productos_update_result, status = producto_controller.actualizar_costo_productos_insumo(insumos_actualizados)
                
                if not productos_update_result.get('success'):
                    logger.error(f"Fallo al actualizar costos de productos: {productos_update_result.get('error')}")
                    
        return resultados

    except Exception as e:
        logger.error(f"Error procesando archivo: {str(e)}")
        # Devolver un resultado de error en el formato correcto
        return [{
            'fila': 1,
            'codigo_interno': 'ERROR',
            'producto': 'Error en procesamiento',
            'proveedor': 'Sistema',
            'estado': 'ERROR',
            'mensaje': f'Error procesando archivo: {str(e)}'
        }]

def procesar_actualizacion_precio(insumo, proveedor, fila, usuario):
    """
    Procesa la actualización de precio usando controllers - VERSIÓN CON FORMATO FRONTEND
    """
    try:
        precio_nuevo = float(fila.get('precio_unitario', 0))
        precio_anterior = float(insumo.get('precio_unitario', 0))

        # Validaciones
        if precio_nuevo <= 0:
            return {
                'estado': 'ERROR',
                'mensaje': f'Precio inválido: {precio_nuevo}'
            }

        variacion = calcular_variacion_porcentual(precio_anterior, precio_nuevo)

        # Si hay cambio, actualizar
        if precio_nuevo != precio_anterior:
            # Actualizar precio usando controller
            exito = insumo_controller.actualizar_precio(insumo['id_insumo'], precio_nuevo)

            if exito:
                # Registrar en historial (si tienes este controller)
                insumo_actualizado_data = {'id_insumo': insumo['id_insumo']} 
                try:
                    historial_controller.registrar_cambio({
                        'id_insumo': insumo['id_insumo'],
                        'precio_anterior': precio_anterior,
                        'precio_nuevo': precio_nuevo,
                        'usuario_cambio': usuario,
                        'origen_cambio': 'archivo_proveedor',
                        'archivo_origen': proveedor['nombre'],
                        'observaciones': f'Proveedor: {proveedor["nombre"]} | Variación: {variacion:.1f}%'
                    })
                except Exception as e:
                    logger.warning(f"No se pudo registrar en historial: {str(e)}")

                return {
                    'estado': 'ACTUALIZADO',
                    'mensaje': f'Precio actualizado de ${precio_anterior:.2f} a ${precio_nuevo:.2f} ({"+" if variacion > 0 else ""}{variacion:.1f}%)',
                    'insumo_actualizado': insumo_actualizado_data
                }
            else:
                return {
                    'estado': 'ERROR',
                    'mensaje': 'Error actualizando precio en base de datos',
                    'insumo_actualizado': None
                }
        else:
            return {
                'estado': 'SIN_CAMBIOS',
                'mensaje': 'Precio sin cambios',
                'insumo_actualizado': None
            }

    except Exception as e:
        logger.error(f"Error procesando precio {insumo['codigo_interno']}: {str(e)}")
        return {
            'estado': 'ERROR',
            'mensaje': f'Error interno: {str(e)}'
        }

def calcular_variacion_porcentual(anterior, nuevo):
    """Calcula el porcentaje de variación del precio"""
    if anterior == 0:
        return 100 if nuevo > 0 else 0
    return ((nuevo - anterior) / anterior) * 100

def generar_reporte_consolidado(resultados):
    """Genera reporte resumen del procesamiento"""
    total = len(resultados)
    actualizados = len([r for r in resultados if r.get('estado') == 'ACTUALIZADO'])
    errores = len([r for r in resultados if 'ERROR' in r.get('estado', '')])
    sin_cambios = len([r for r in resultados if r.get('estado') == 'SIN_CAMBIOS'])

    return {
        'total_filas': total,
        'actualizados': actualizados,
        'errores': errores,
        'sin_cambios': sin_cambios,
        'fecha_procesamiento': datetime.now().isoformat()
    }

# Otros endpoints (plantillas, catálogo, etc.)
@precios_bp.route('/api/precios/plantilla', methods=['GET'])
@permission_required(sector_codigo='LOGISTICA', accion='leer')
def descargar_plantilla():
    """Descarga plantilla para carga de precios"""
    # Obtener catálogo usando controller
    catalogo = insumo_controller.obtener_catalogo_activo()

    # Crear datos de ejemplo
    datos_ejemplo = []
    for insumo in catalogo[:5]:  # Primeros 5 como ejemplo
        datos_ejemplo.append({
            'email_proveedor': 'tu-email@empresa.com',
            'cuil_proveedor': '20-12345678-9',
            'codigo_interno': insumo['codigo_interno'],
            'precio_unitario': round(float(insumo.get('precio_unitario', 0)) * 1.1, 2),
            'observaciones': 'Precio vigente'
        })

    df = pd.DataFrame(datos_ejemplo)

    # Crear Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Precios', index=False)

    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='plantilla_precios_proveedores.xlsx'
    )