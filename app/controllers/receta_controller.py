from app.controllers.base_controller import BaseController
from app.models.receta import RecetaModel, RecetaIngrediente
from app.schemas.receta_schema import RecetaSchema
from typing import Dict, List, Optional
from marshmallow import ValidationError

class RecetaController(BaseController):
    """
    Controlador para la lógica de negocio de las recetas y sus ingredientes.
    """
    def __init__(self):
        super().__init__()
        self.model = RecetaModel()
        self.ingrediente_model = RecetaIngrediente
        self.schema = RecetaSchema()

    def obtener_recetas(self, filtros: Optional[Dict] = None) -> List[Dict]:
        """
        Obtiene una lista de recetas, opcionalmente filtradas.
        """
        result = self.model.find_all(filtros or {})
        return result.get('data', [])

    def obtener_receta_con_ingredientes(self, receta_id: int) -> Optional[Dict]:
        """
        Obtiene una receta específica junto con su lista de ingredientes.
        """
        receta_result = self.model.find_by_id(receta_id, 'id')
        if not receta_result.get('success'):
            return None

        receta = receta_result['data']

        ingredientes_result = self.ingrediente_model.find_all({'receta_id': receta_id})
        receta['ingredientes'] = ingredientes_result.get('data', [])

        return receta
    
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
        Crea una receta y sus ingredientes asociados de forma transaccional.
        """
        try:
            validated_data = self.schema.load(data)
            ingredientes_data = validated_data.pop('ingredientes', [])

            # Crear la receta principal
            receta_result = self.model.create(validated_data)
            if not receta_result.get('success'):
                return receta_result

            nueva_receta_id = receta_result['data']['id']

            # Crear los ingredientes
            for ingrediente in ingredientes_data:
                ingrediente['receta_id'] = nueva_receta_id
                ingrediente_result = self.ingrediente_model.create(ingrediente)

                # Si falla un ingrediente, se intenta revertir la creación de la receta
                if not ingrediente_result.get('success'):
                    self.model.delete(nueva_receta_id, 'id')
                    return {'success': False, 'error': f"Error al crear ingrediente: {ingrediente_result.get('error')}"}

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
                return {'success': True} # No hay nada más que hacer si no hay nuevos ingredientes.

            # 2. Preparar los nuevos ingredientes para una inserción en lote
            ingredientes_a_insertar = [
                {
                    'receta_id': receta_id,
                    'id_insumo': item['id_insumo'],
                    'cantidad': item['cantidad'],
                    'unidad_medida': item['unidad_medida']
                }
                for item in receta_items
            ]
            
            # 3. Insertar todos los nuevos ingredientes en una sola llamada
            insert_result = self.model.db.table('receta_ingredientes').insert(ingredientes_a_insertar).execute()

            # 4. Verificar que la inserción fue exitosa
            if len(insert_result.data) != len(ingredientes_a_insertar):
                raise Exception("No se pudieron guardar todos los ingredientes de la receta.")
            
            return {'success': True}
        except Exception as e:
            # Loggear el error sería una buena práctica aquí
            return {'success': False, 'error': str(e)}