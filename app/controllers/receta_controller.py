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