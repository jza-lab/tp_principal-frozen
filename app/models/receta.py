from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime
from app.models.base_model import BaseModel


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
        
