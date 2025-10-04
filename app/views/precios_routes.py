from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
import pandas as pd
import logging
from datetime import datetime
from io import BytesIO

from app.controllers.proveedor_controller import ProveedorController
from app.controllers.insumo_controller import InsumoController
from app.controllers.historial_precios_controller import HistorialPreciosController

precios_bp = Blueprint('precios', __name__)
logger = logging.getLogger(__name__)

# Instancias de controllers
proveedor_controller = ProveedorController()
insumo_controller = InsumoController()
historial_controller = HistorialPreciosController()

@precios_bp.route('/api/precios/cargar-archivo-proveedor', methods=['POST'])
def cargar_archivo_precios_proveedor():
    """
    Endpoint para cargar archivo Excel con precios de proveedores
    """
    try:
        if 'archivo' not in request.files:
            return jsonify({'success': False, 'error': 'No se envió archivo'}), 400

        archivo = request.files['archivo']
        usuario = request.form.get('usuario', 'sistema')

        if archivo.filename == '':
            return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400

        # Validar extensión
        if not archivo.filename.lower().endswith(('.xlsx', '.xls')):
            return jsonify({'success': False, 'error': 'Solo se aceptan archivos Excel'}), 400

        # Procesar archivo
        resultados = procesar_archivo_proveedor(archivo, usuario)
        reporte = generar_reporte_consolidado(resultados)

        return jsonify({
            'success': True,
            'message': 'Archivo procesado exitosamente',
            'reporte': reporte,
            'detalles': resultados
        })

    except Exception as e:
        logger.error(f"Error cargando archivo de precios: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def procesar_archivo_proveedor(archivo, usuario):
    """
    Procesa el archivo Excel usando los controllers
    """
    try:
        datos = pd.read_excel(archivo)
        resultados = []

        for indice, fila in datos.iterrows():
            # Usar controller para buscar proveedor
            proveedor = proveedor_controller.buscar_por_identificacion(fila.to_dict())

            if not proveedor:
                resultados.append({
                    'fila': indice + 1,
                    'codigo_interno': fila.get('codigo_interno', 'Desconocido'),
                    'estado': 'ERROR_PROVEEDOR',
                    'mensaje': 'Proveedor no encontrado. Verifique email/CUIL'
                })
                continue

            # Usar controller para buscar insumo
            insumo = insumo_controller.buscar_por_codigo_interno(fila.get('codigo_interno'))

            if not insumo:
                resultados.append({
                    'fila': indice + 1,
                    'codigo_interno': fila.get('codigo_interno'),
                    'proveedor': proveedor['nombre'],
                    'estado': 'ERROR_INSUMO',
                    'mensaje': 'Código interno no encontrado en catálogo'
                })
                continue

            # Procesar actualización de precio
            resultado = procesar_actualizacion_precio(insumo, proveedor, fila, usuario)
            resultado['fila'] = indice + 1
            resultados.append(resultado)

        return resultados

    except Exception as e:
        logger.error(f"Error procesando archivo: {str(e)}")
        raise

def procesar_actualizacion_precio(insumo, proveedor, fila, usuario):
    """
    Procesa la actualización de precio usando controllers
    """
    try:
        precio_nuevo = float(fila.get('precio_unitario', 0))
        precio_anterior = float(insumo.get('precio_unitario', 0))

        # Validaciones
        if precio_nuevo <= 0:
            return {
                'codigo_interno': insumo['codigo_interno'],
                'producto': insumo['nombre'],
                'proveedor': proveedor['nombre'],
                'estado': 'ERROR',
                'mensaje': f'Precio inválido: {precio_nuevo}'
            }

        variacion = calcular_variacion_porcentual(precio_anterior, precio_nuevo)

        # Si hay cambio, actualizar
        if precio_nuevo != precio_anterior:
            # Actualizar precio usando controller
            exito = insumo_controller.actualizar_precio(insumo['id_insumo'], precio_nuevo)

            if exito:
                # Registrar en historial
                historial_controller.registrar_cambio({
                    'id_insumo': insumo['id_insumo'],
                    'precio_anterior': precio_anterior,
                    'precio_nuevo': precio_nuevo,
                    'usuario_cambio': usuario,
                    'origen_cambio': 'archivo_proveedor',
                    'archivo_origen': proveedor['nombre'],
                    'observaciones': f'Proveedor: {proveedor["nombre"]} | Variación: {variacion:.1f}%'
                })

                return {
                    'codigo_interno': insumo['codigo_interno'],
                    'producto': insumo['nombre'],
                    'proveedor': proveedor['nombre'],
                    'precio_anterior': precio_anterior,
                    'precio_nuevo': precio_nuevo,
                    'variacion_porcentaje': round(variacion, 1),
                    'estado': 'ACTUALIZADO',
                    'mensaje': 'Precio actualizado exitosamente'
                }
            else:
                return {
                    'codigo_interno': insumo['codigo_interno'],
                    'producto': insumo['nombre'],
                    'proveedor': proveedor['nombre'],
                    'estado': 'ERROR',
                    'mensaje': 'Error actualizando precio en base de datos'
                }
        else:
            return {
                'codigo_interno': insumo['codigo_interno'],
                'producto': insumo['nombre'],
                'proveedor': proveedor['nombre'],
                'estado': 'SIN_CAMBIOS',
                'mensaje': 'Precio sin cambios'
            }

    except Exception as e:
        logger.error(f"Error procesando precio {insumo['codigo_interno']}: {str(e)}")
        return {
            'codigo_interno': insumo['codigo_interno'],
            'producto': insumo['nombre'],
            'proveedor': proveedor['nombre'],
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