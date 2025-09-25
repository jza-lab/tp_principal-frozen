from typing import List, Optional
from datetime import datetime
from app.models.materia_prima import MateriaPrima
from app.models.lote import Lote
from app.repositories.materia_prima_repository import MateriaPrimaRepository
from app.repositories.lote_repository import LoteRepository

class MateriaPrimaService:
    
    def __init__(self, materia_prima_repository: MateriaPrimaRepository, lote_repository: LoteRepository):
        self.materia_prima_repo = materia_prima_repository
        self.lote_repo = lote_repository
    
    def crear_materia_prima(self, codigo: str, nombre: str, unidad_medida: str,
                          categoria: str, stock_minimo: float) -> MateriaPrima:
        
        if self.materia_prima_repo.obtener_por_codigo(codigo):
            raise ValueError(f"Ya existe una materia prima con código {codigo}")
        
        if unidad_medida not in ['kg', 'g', 'litros', 'unidades']:
            raise ValueError("Unidad de medida no válida")
        
        materia_prima = MateriaPrima(
            id=None,
            codigo=codigo,
            nombre=nombre,
            unidad_medida=unidad_medida,
            categoria=categoria,
            stock_actual=0.0,
            stock_minimo=stock_minimo,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            activo=True
        )
        
        return self.materia_prima_repo.crear(materia_prima)

    def registrar_ingreso_lote(self, materia_prima_id: int, proveedor_id: int, cantidad: float,
                               costo_por_unidad: float, fecha_vencimiento: Optional[datetime] = None,
                               numero_factura: Optional[str] = None) -> Lote:
        
        if not self.materia_prima_repo.obtener_por_id(materia_prima_id):
            raise ValueError("Materia prima no encontrada")

        nuevo_lote = Lote(
            id=None,
            codigo=f"LOTE-{materia_prima_id}-{datetime.now().timestamp()}", # Código de lote único
            materia_prima_id=materia_prima_id,
            proveedor_id=proveedor_id,
            cantidad_inicial=cantidad,
            cantidad_actual=cantidad,
            fecha_ingreso=datetime.now(),
            fecha_vencimiento=fecha_vencimiento,
            numero_factura=numero_factura,
            costo_por_unidad=costo_por_unidad,
            activo=True
        )
        
        lote_creado = self.lote_repo.crear(nuevo_lote)
        self._actualizar_stock_total(materia_prima_id)
        return lote_creado

    def consumir_stock(self, materia_prima_id: int, cantidad_a_consumir: float):
        if cantidad_a_consumir <= 0:
            raise ValueError("La cantidad a consumir debe ser positiva.")

        lotes = self.lote_repo.obtener_por_materia_prima(materia_prima_id, solo_activos=True)

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

            self.lote_repo.actualizar(lote)

        self._actualizar_stock_total(materia_prima_id)

    def _actualizar_stock_total(self, materia_prima_id: int):
        lotes = self.lote_repo.obtener_por_materia_prima(materia_prima_id, solo_activos=False)
        stock_total = sum(lote.cantidad_actual for lote in lotes)
        self.materia_prima_repo.actualizar_stock_en_db(materia_prima_id, stock_total)

    def obtener_alertas_stock_bajo(self) -> List[MateriaPrima]:
        todas = self.materia_prima_repo.obtener_todas()
        return [mp for mp in todas if mp.esta_en_stock_minimo()]
    
    def buscar_materias_primas(self, categoria: str = None, busqueda: str = None) -> List[MateriaPrima]:
        return self.materia_prima_repo.obtener_por_filtros(categoria=categoria, busqueda=busqueda)