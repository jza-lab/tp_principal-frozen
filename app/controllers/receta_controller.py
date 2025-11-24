from app.controllers.base_controller import BaseController
from app.models.receta import RecetaModel
from app.models.producto import ProductoModel
from app.models.insumo import InsumoModel
from app.models.receta_ingrediente import RecetaIngredienteModel
from app.models.operacion_receta_model import OperacionRecetaModel
from app.models.operacion_receta_rol_model import OperacionRecetaRolModel
from app.models.operacion_receta_costo_fijo_model import OperacionRecetaCostoFijoModel
from app.schemas.receta_schema import RecetaSchema
from typing import Dict, List, Optional
from marshmallow import ValidationError
import logging

logger = logging.getLogger(__name__)

class RecetaController(BaseController):
    """
    Controlador para la lógica de negocio de las recetas y sus ingredientes.
    """
    def __init__(self):
        super().__init__()
        self.model = RecetaModel()
        self.schema = RecetaSchema()
        self.producto_model = ProductoModel()
        self.insumo_model = InsumoModel()
        self.receta_ingrediente_model = RecetaIngredienteModel()
        self.operacion_receta_model = OperacionRecetaModel()
        self.operacion_receta_rol_model = OperacionRecetaRolModel()
        self.operacion_receta_costo_fijo_model = OperacionRecetaCostoFijoModel()
        # Importar RolController aquí para evitar importación circular a nivel de módulo
        from app.controllers.rol_controller import RolController
        self.rol_controller = RolController()

    def _calcular_y_actualizar_peso_producto(self, receta_id: int) -> Dict:
        """
        Calcula el peso total de un producto basado en los insumos de su receta y lo actualiza en la DB.
        """
        try:
            # 1. Obtener la receta y el producto asociado
            receta_resp, _ = self.obtener_receta_con_ingredientes(receta_id)
            if not receta_resp.get('success'):
                return {'success': False, 'error': f"Receta {receta_id} no encontrada."}
            
            receta = receta_resp['data']
            producto_id = receta.get('producto_id')
            ingredientes = receta.get('ingredientes', [])

            if not producto_id:
                return {'success': False, 'error': "La receta no está asociada a ningún producto."}

            if not ingredientes:
                # Si no hay ingredientes, el peso es 0.
                self.producto_model.update(producto_id, {'peso_total_gramos': 0}, 'id')
                return {'success': True, 'message': 'Receta sin ingredientes, peso establecido a 0.'}

            # 2. Calcular peso total de los insumos
            peso_total_insumos = 0
            for ing in ingredientes:
                insumo_id = ing.get('id_insumo')
                cantidad = float(ing.get('cantidad', 0))

                insumo_resp = self.insumo_model.find_by_id(insumo_id, 'id_insumo')
                if not insumo_resp.get('success'):
                    raise Exception(f"Insumo ID {insumo_id} no encontrado en el catálogo.")

                insumo = insumo_resp['data']
                peso_unitario = insumo.get('peso_gramos_unidad')

                if peso_unitario is None or float(peso_unitario) <= 0:
                    raise Exception(f"El insumo '{insumo.get('nombre')}' (ID: {insumo_id}) no tiene un 'peso_gramos_unidad' válido definido.")
                
                peso_total_insumos += cantidad * float(peso_unitario)

            # 3. Añadir porcentaje de empaque (5%)
            peso_final = peso_total_insumos * 1.05

            # 4. Actualizar el producto
            update_resp = self.producto_model.update(producto_id, {'peso_total_gramos': peso_final}, 'id')
            if not update_resp.get('success'):
                raise Exception(f"No se pudo actualizar el peso del producto ID {producto_id}.")

            logger.info(f"Peso del producto ID {producto_id} actualizado a {peso_final}g.")
            return {'success': True}

        except Exception as e:
            logger.error(f"Error calculando peso para receta {receta_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def obtener_recetas(self, filtros: Optional[Dict] = None) -> List[Dict]:
        """
        Obtiene una lista de recetas, opcionalmente filtradas.
        """
        result = self.model.find_all(filtros or {})
        return result.get('data', [])

    def obtener_receta_con_ingredientes(self, receta_id: int) -> Optional[Dict]:
        """
        Obtiene una receta específica junto con su lista de ingredientes y mano de obra enriquecida.
        """
        receta_result = self.model.find_by_id(receta_id, 'id')
        if not receta_result.get('success'):
            return None, 500

        receta = receta_result['data']
        
        try:
            # Obtener ingredientes
            ingredientes_result = self.receta_ingrediente_model.find_by_receta_id_with_insumo(receta_id)
            receta['ingredientes'] = ingredientes_result['data'] if ingredientes_result.get('success') else []

            # Obtener operaciones (pasos de producción)
            operaciones_result = self.operacion_receta_model.find_by_receta_id(receta_id)
            operaciones = operaciones_result.get('data', [])

            # Para cada operación, obtener los roles asignados y los costos fijos
            for op in operaciones:
                roles_result = self.operacion_receta_rol_model.find_by_operacion_id(op['id'])
                if roles_result.get('success'):
                    # Guardamos la estructura completa incluyendo porcentaje
                    op['roles_detalle'] = roles_result.get('data', [])
                    op['roles_asignados'] = [rol['rol_id'] for rol in op['roles_detalle']]
                else:
                    op['roles_detalle'] = []
                    op['roles_asignados'] = []
                
                costos_fijos_result = self.operacion_receta_costo_fijo_model.find_by_operacion_id(op['id'])
                if costos_fijos_result.get('success'):
                    op['costos_fijos_ids'] = [cf['costo_fijo_id'] for cf in costos_fijos_result.get('data', [])]
                else:
                    op['costos_fijos_ids'] = []
            
            receta['operaciones'] = operaciones

            return {'success': True, 'data': receta}, 200
        except Exception as e:
            logger.error(f"Error al obtener detalles de la receta {receta_id}: {e}", exc_info=True)
            return {'success': False, 'error': f"Error al obtener detalles de la receta: {str(e)}"}, 500

    def obtener_recetas_con_ingredientes_masivo(self, receta_ids: List[int]) -> tuple:
        """
        Obtiene múltiples recetas y sus ingredientes en un número mínimo de consultas.
        """
        if not receta_ids:
            return self.success_response(data=[])

        try:
            # 1. Obtener todas las recetas base
            recetas_res = self.model.find_all(filters={'id': receta_ids})
            if not recetas_res.get('success'):
                return self.error_response(f"Error al buscar recetas base: {recetas_res.get('error')}")

            recetas_map = {r['id']: r for r in recetas_res['data']}

            # 2. Obtener todos los ingredientes para esas recetas, haciendo join con insumos
            ingredientes_res = self.model.db.table('receta_ingredientes').select('*, insumo:id_insumo(*)').in_('receta_id', receta_ids).execute()
            
            # 3. Agrupar ingredientes por receta_id
            for ing in ingredientes_res.data:
                receta_id = ing.get('receta_id')
                if receta_id in recetas_map:
                    if 'ingredientes' not in recetas_map[receta_id]:
                        recetas_map[receta_id]['ingredientes'] = []
                    recetas_map[receta_id]['ingredientes'].append(ing)
            
            return self.success_response(data=list(recetas_map.values()))

        except Exception as e:
            return self.error_response(f"Error crítico en obtención masiva de recetas: {str(e)}", 500)
    
    def obtener_ingredientes_para_receta(self, receta_id: int) -> Dict:
        """
        Obtiene la lista de ingredientes enriquecidos para una receta específica.
        Utiliza el nuevo método del modelo que hace el join con insumos.
        """
        return self.model.get_ingredientes(receta_id)

    def calcular_costo_total_receta(self, receta_id: int) -> Optional[float]:
        """
        Calcula el costo total de una receta sumando el costo de cada ingrediente.
        """
        ingredientes_result = self.obtener_ingredientes_para_receta(receta_id)
        if not ingredientes_result.get('success'):
            return ingredientes_result

        ingredientes = ingredientes_result['data']
        costo_total = 0.0

        for ingrediente in ingredientes:
            try:
                insumo_result = self.model.db.table('insumos_catalogo').select('precio_unitario').eq('id_insumo', ingrediente['id_insumo']).execute()

            except Exception as e:
                return {'success': False, 'error': f"Error al obtener el costo del insumo {ingrediente['id_insumo']}: {str(e)}"}
            if insumo_result.data:
                costo_unitario = insumo_result.data[0]['precio_unitario']
                costo_total += costo_unitario * ingrediente['cantidad']
            else:
                return {'success': False, 'error': f"Insumo con ID {ingrediente['id_insumo']} no encontrado."}
                    
        return {'success': True, 'data': {'costo_total': costo_total}}
    
    def crear_receta_con_ingredientes(self, data: Dict) -> Dict:
        """
        Crea una receta, sus ingredientes y la mano de obra asociada.
        """
        try:
            validated_data = self.schema.load(data)
            ingredientes_data = validated_data.pop('ingredientes', [])
            operaciones_data = data.get('operaciones', []) # Use get to avoid popping it from validated_data

            # Crear la receta principal
            receta_result = self.model.create(validated_data)
            if not receta_result.get('success'):
                return receta_result

            nueva_receta_id = receta_result['data']['id']

            # Gestionar ingredientes
            if ingredientes_data:
                ingredientes_result = self.gestionar_ingredientes_para_receta(nueva_receta_id, ingredientes_data)
                if not ingredientes_result.get('success'):
                    self.model.delete(nueva_receta_id, 'id')
                    return ingredientes_result

            # Gestionar operaciones y sus roles
            if operaciones_data:
                operaciones_result = self.gestionar_operaciones_para_receta(nueva_receta_id, operaciones_data)
                if not operaciones_result.get('success'):
                    # Si falla, eliminar la receta recién creada para mantener la consistencia
                    self.model.delete(nueva_receta_id, 'id')
                    return operaciones_result

            # Calcular el peso del producto después de crear la receta
            self._calcular_y_actualizar_peso_producto(nueva_receta_id)

            return {'success': True, 'data': receta_result['data']}
        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            # En un caso real, aquí se manejaría un rollback de la transacción
            return {'success': False, 'error': f'Error interno en el controlador: {str(e)}'}

    def gestionar_ingredientes_para_receta(self, receta_id: int, receta_items: List[Dict]) -> Dict:
        """
        Gestiona los ingredientes de la receta de forma eficiente.
        Elimina los ingredientes existentes y luego inserta los nuevos en un solo lote.
        """
        try:
            # 1. Eliminar ingredientes antiguos
            self.model.db.table('receta_ingredientes').delete().eq('receta_id', receta_id).execute()

            if not receta_items:
                # Si no hay ingredientes, recalcular el peso (será 0)
                self._calcular_y_actualizar_peso_producto(receta_id)
                return {'success': True} 

            # 2. Preparar los nuevos ingredientes para una inserción en lote
            # 2. Preparar los nuevos ingredientes, buscando la unidad de medida si falta.
            ingredientes_a_insertar = []
            for item in receta_items:
                unidad_medida = item.get('unidad_medida')
                if not unidad_medida:
                    # Si la unidad no viene, la buscamos en el catálogo de insumos
                    insumo_id = item.get('id_insumo')
                    if insumo_id:
                        insumo_res = self.insumo_model.find_by_id(insumo_id, 'id_insumo')
                        if insumo_res.get('success'):
                            unidad_medida = insumo_res['data'].get('unidad_medida', 'N/A')
                
                ingredientes_a_insertar.append({
                    'receta_id': receta_id,
                    'id_insumo': item['id_insumo'],
                    'cantidad': item['cantidad'],
                    'unidad_medida': unidad_medida or 'N/A' # Asegurar que no sea None
                })
            
            # 3. Insertar todos los nuevos ingredientes en una sola llamada
            insert_result = self.model.db.table('receta_ingredientes').insert(ingredientes_a_insertar).execute()

            # 4. Verificar que la inserción fue exitosa
            if len(insert_result.data) != len(ingredientes_a_insertar):
                raise Exception("No se pudieron guardar todos los ingredientes de la receta.")
            
            # Calcular el peso del producto después de actualizar los ingredientes
            self._calcular_y_actualizar_peso_producto(receta_id)

            return {'success': True}
        except Exception as e:
            # Loggear el error sería una buena práctica aquí
            return {'success': False, 'error': str(e)}

    def gestionar_operaciones_para_receta(self, receta_id: int, operaciones_data: List[Dict]) -> Dict:
        """
        Gestiona los pasos de producción (operaciones), sus roles asignados y costos fijos.
        Utiliza una estrategia de "borrar y volver a crear".
        """
        try:
            # 1. Obtener y eliminar todas las operaciones antiguas de la receta
            operaciones_antiguas = self.operacion_receta_model.find_by_receta_id(receta_id).get('data', [])
            for op in operaciones_antiguas:
                # Al eliminar la operación, los roles y costos fijos se borran en cascada por la FK (si está configurada)
                # Si no, las borramos manualmente por seguridad
                self.operacion_receta_rol_model.delete_by_operacion_id(op['id'])
                self.operacion_receta_costo_fijo_model.delete_by_operacion_id(op['id'])
                self.operacion_receta_model.delete(op['id'])

            if not operaciones_data:
                return {'success': True, 'message': 'No se proporcionaron operaciones.'}

            # 2. Crear las nuevas operaciones y sus detalles
            for op_data in operaciones_data:
                # Crear la operación principal
                datos_operacion = {
                    'receta_id': receta_id,
                    'nombre_operacion': op_data['nombre_operacion'],
                    'secuencia': op_data['secuencia'],
                    'tiempo_preparacion': op_data['tiempo_preparacion'],
                    'tiempo_ejecucion_unitario': op_data['tiempo_ejecucion_unitario']
                }
                op_result = self.operacion_receta_model.create(datos_operacion)
                if not op_result.get('success'):
                    raise Exception(f"No se pudo crear la operación '{op_data['nombre_operacion']}': {op_result.get('error')}")

                nueva_op_id = op_result['data']['id']
                
                # Asignar roles (con porcentajes)
                # op_data['roles'] debe ser una lista de dicts: [{'rol_id': 1, 'porcentaje_participacion': 50}, ...]
                roles_data = op_data.get('roles', [])
                if roles_data:
                    roles_result = self.operacion_receta_rol_model.bulk_create_for_operacion(nueva_op_id, roles_data)
                    if not roles_result.get('success'):
                         raise Exception(f"No se pudieron asignar roles a la operación '{op_data['nombre_operacion']}': {roles_result.get('error')}")

                # Asignar Costos Fijos
                costos_fijos_ids = op_data.get('costos_fijos', [])
                if costos_fijos_ids:
                    cf_result = self.operacion_receta_costo_fijo_model.bulk_create_for_operacion(nueva_op_id, costos_fijos_ids)
                    if not cf_result.get('success'):
                         raise Exception(f"No se pudieron asignar costos fijos a la operación '{op_data['nombre_operacion']}': {cf_result.get('error')}")

            return {'success': True}

        except Exception as e:
            logger.error(f"Error gestionando operaciones para receta {receta_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
