from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime
from app.models.base_model import BaseModel
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)

@dataclass
class Receta:
    """Representa la receta para fabricar un producto terminado.

    Esta clase define los parámetros, tiempos y rendimiento de una versión
    específica de la receta para un producto. Se asocia con una lista de
    ingredientes a través de la clase `RecetaIngrediente`."""

    id: Optional[int]
    nombre: str
    version: str
    producto_id: Optional[int] = None
    descripcion: Optional[str] = None
    rendimiento: float = 0.0
    activa: bool = True
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.created_at:
            d['created_at'] = self.created_at.isoformat()
        return d

@dataclass
class RecetaIngrediente:
    """Representa un ingrediente específico dentro de una receta.

    Esta clase asocia una `MateriaPrima` con una `Receta`, especificando
    la cantidad necesaria de ese ingrediente."""
    id: Optional[int]
    receta_id: int
    materia_prima_id: int
    cantidad: float
    unidad: str

    def to_dict(self) -> dict:
        """Convierte la instancia del modelo a un diccionario."""
        return asdict(self)

class RecetaModel(BaseModel):
    """
    Modelo para interactuar con la tabla de recetas en la base de datos.
    """
    def get_table_name(self) -> str:
        return 'recetas'

    def get_costo_produccion(self, producto_id: int, costos_insumos: Dict[str, float] = None) -> float:
        """
        Calcula el costo de producción para una unidad de un producto.
        Si se provee `costos_insumos` (un dict de {insumo_id: costo}), se usa para evitar
        consultas N+1 a la base de datos. De lo contrario, calcula los costos al momento.
        """
        from app.models.insumo_inventario import InsumoInventarioModel
        insumo_inventario_model = InsumoInventarioModel()

        receta_res = self.find_all(filters={'producto_id': producto_id, 'activa': True}, limit=1)
        if not receta_res.get('success') or not receta_res.get('data'):
            logger.warning(f"No se encontró receta activa para el producto ID {producto_id}.")
            return 0.0
        receta = receta_res['data'][0]

        ingredientes_res = self.get_ingredientes(receta['id'])
        if not ingredientes_res.get('success'):
            logger.error(f"Error al obtener ingredientes para la receta ID {receta['id']}.")
            return 0.0

        costo_total = 0.0
        for ingrediente in ingredientes_res.get('data', []):
            insumo_id = ingrediente.get('id_insumo')
            cantidad_necesaria = float(ingrediente.get('cantidad', 0))
            
            if not insumo_id:
                continue

            costo_promedio = 0.0
            if costos_insumos is not None:
                # Vía optimizada: usar el costo pre-calculado del diccionario.
                costo_promedio = costos_insumos.get(insumo_id, 0.0)
                if costo_promedio == 0.0:
                     logger.warning(f"El insumo ID {insumo_id} no se encontró en el dict de costos pre-calculados.")
            else:
                # Vía no optimizada: hacer una consulta por cada insumo (fallback).
                costo_promedio_res = insumo_inventario_model.get_costo_promedio_ponderado(insumo_id)
                if costo_promedio_res.get('success'):
                    costo_promedio = float(costo_promedio_res.get('costo_promedio', 0.0))
                else:
                    logger.warning(f"No se pudo obtener el costo promedio para el insumo ID {insumo_id}.")
            
            costo_total += cantidad_necesaria * costo_promedio

        return costo_total

    def get_ingredientes(self, receta_id: int) -> dict:
        """
        Obtiene la lista de ingredientes (insumos) para una receta específica,
        junto con la cantidad y unidad requerida.
        """
        try:
            # La tabla intermedia es 'receta_ingredientes'
            # Hacemos un select que trae campos de la tabla intermedia y
            # anida los detalles del insumo relacionado desde 'insumos_catalogo'.
            # Supabase usa las FKs para inferir esta relación.
            # El campo 'materia_prima_id' en 'receta_ingredientes' apunta a 'id' en 'insumos_catalogo'.
            result = self.db.table('receta_ingredientes').select(
                'cantidad, unidad_medida, insumos_catalogo(id_insumo, nombre, descripcion, codigo_interno)'
            ).eq('receta_id', receta_id).execute()

            if result.data:
                # Aplanar la respuesta para que sea más fácil de usar en la plantilla
                ingredientes_procesados = []
                for item in result.data:
                    insumo_data = item.pop('insumos_catalogo')
                    if insumo_data:
                        item['id_insumo'] = insumo_data.get('id_insumo')
                        item['nombre_insumo'] = insumo_data.get('nombre')
                        item['descripcion_insumo'] = insumo_data.get('descripcion')
                        item['codigo_insumo'] = insumo_data.get('codigo_interno')
                    else:
                        item['id_insumo'] = "Insumo no encontrado"
                        item['nombre_insumo'] = "Insumo no encontrado"
                        item['descripcion_insumo'] = ""
                        item['codigo_insumo'] = ""
                    ingredientes_procesados.append(item)

                return {'success': True, 'data': ingredientes_procesados}
            else:
                return {'success': True, 'data': []} # No es un error si no tiene ingredientes

        except Exception as e:
            # Loggear el error sería una buena práctica aquí
            return {'success': False, 'error': f'Error al obtener ingredientes: {str(e)}'}

    def find_all_recetas_by_insumo(self, insumo_id: int) -> dict:
        """
        Encuentra todas las recetas que utilizan un insumo específico.
        """
        try:
            result = self.db.table('recetas').select(
                '*, receta_ingredientes!inner(id_insumo)'
            ).eq('receta_ingredientes.id_insumo', insumo_id).execute()

            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': True, 'data': []} # No es un error si no hay recetas

        except Exception as e:
            return {'success': False, 'error': f'Error al buscar recetas por insumo: {str(e)}'}


    def find_by_ids(self, receta_ids: List[int]) -> Dict:
        """ Obtiene múltiples recetas por sus IDs en una consulta. """
        if not receta_ids:
            return {'success': True, 'data': []}
        try:
            ids_unicos = list(set(receta_ids))
            query = self.db.table(self.table_name).select('*').in_('id', ids_unicos)
            result = query.execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error en find_by_ids para recetas: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_ingredientes_by_receta_ids(self, receta_ids: List[int]) -> Dict:
        """ Obtiene TODOS los ingredientes para una LISTA de IDs de receta. """
        if not receta_ids:
            return {'success': True, 'data': []}
        try:
            ids_unicos = list(set(receta_ids))

            # --- ¡CORRECCIÓN! ---
            # Cambiamos 'insumos' por 'insumos_catalogo' como sugirió el error.
            query = self.db.table('receta_ingredientes').select(
                '*, insumos_catalogo(nombre, tiempo_entrega_dias, id_insumo)'
            ).in_('receta_id', ids_unicos)
            # --- FIN CORRECCIÓN -

            result = query.execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error en get_ingredientes_by_receta_ids: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def obtener_operaciones_receta(self, receta_id: int) -> Dict:
        """ Obtiene las operaciones de una receta desde el modelo. """
        try:
            result = self.db.table('operacionesreceta').select('*').eq('receta_id', receta_id).execute()
            return {'success': True, 'data': result.data} if result.data else {'success': True, 'data': []}
        except Exception as e:
            logger.error(f"Error obteniendo operaciones para receta {receta_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
