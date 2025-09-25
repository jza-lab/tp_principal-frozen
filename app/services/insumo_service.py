from typing import List, Optional
from datetime import datetime
from app.models.insumo import Insumo
from app.models.lote import Lote
from app.repositories.insumo_repository import InsumoRepository
from app.repositories.lote_repository import LoteRepository

class InsumoService:
    
    def __init__(self, insumo_repository: InsumoRepository, lote_repository: LoteRepository):
        self.insumo_repo = insumo_repository
        self.lote_repo = lote_repository
    
    def crear_insumo(self, codigo: str, nombre: str, unidad_medida: str,
                          categoria: str, stock_min: float) -> Insumo:
        
        if self.insumo_repo.obtener_por_codigo(codigo):
            raise ValueError(f"Ya existe un insumo con código {codigo}")
        
        if unidad_medida not in ['kg', 'g', 'litros', 'unidades']:
            raise ValueError("Unidad de medida no válida")
        
        insumo = Insumo(
            id_insumo=None, # La BD lo genera
            codigo_interno=codigo,
            nombre=nombre,
            unidad_medida=unidad_medida,
            categoria=categoria,
            stock_min=stock_min,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            activo=True
        )
        
        return self.insumo_repo.create(insumo)

    def registrar_ingreso_lote(self, insumo_id: int, proveedor_id: int, cantidad: float,
                               costo_por_unidad: float, fecha_vencimiento: Optional[datetime] = None,
                               numero_factura: Optional[str] = None) -> Lote:
        
        if not self.insumo_repo.get_by_id(insumo_id):
            raise ValueError("Insumo no encontrado")

        nuevo_lote = Lote(
            id=None,
            codigo=f"LOTE-{insumo_id}-{datetime.now().timestamp()}",
            materia_prima_id=insumo_id, # Mantener coherencia con el modelo de Lote
            proveedor_id=proveedor_id,
            cantidad_inicial=cantidad,
            cantidad_actual=cantidad,
            fecha_ingreso=datetime.now(),
            fecha_vencimiento=fecha_vencimiento,
            numero_factura=numero_factura,
            costo_por_unidad=costo_por_unidad,
            activo=True
        )
        
        lote_creado = self.lote_repo.create(nuevo_lote)
        self._actualizar_stock_total(insumo_id)
        return lote_creado

    def consumir_stock(self, insumo_id: int, cantidad_a_consumir: float):
        if cantidad_a_consumir <= 0:
            raise ValueError("La cantidad a consumir debe ser positiva.")

        lotes = self.lote_repo.obtener_por_materia_prima(insumo_id, solo_activos=True)

        stock_disponible = sum(lote.cantidad_actual for lote in lotes)
        if stock_disponible < cantidad_a_consumir:
            raise ValueError(f"Stock insuficiente. Disponible: {stock_disponible}, Requerido: {cantidad_a_consumir}")

        cantidad_restante = cantidad_a_consumir
        for lote in lotes:
            if cantidad_restante == 0:
                break

            cantidad_a_tomar = min(lote.cantidad_actual, cantidad_restante)
            lote.cantidad_actual -= cantidad_a_tomar
            cantidad_restante -= cantidad_a_tomar

            self.lote_repo.update(lote.id, lote)

        self._actualizar_stock_total(insumo_id)

    def _actualizar_stock_total(self, insumo_id: int):
        lotes = self.lote_repo.obtener_por_materia_prima(insumo_id, solo_activos=False)
        stock_total = sum(l.cantidad_actual for l in lotes)
        self.insumo_repo.actualizar_stock_en_db(insumo_id, stock_total)

    def obtener_alertas_stock_bajo(self) -> List[Insumo]:
        todos = self.insumo_repo.get_all()
        return [insumo for insumo in todos if insumo.esta_en_stock_minimo()]
    
    def buscar_insumos(self, categoria: str = None, busqueda: str = None) -> List[Insumo]:
        return self.insumo_repo.obtener_por_filtros(categoria=categoria, busqueda=busqueda)