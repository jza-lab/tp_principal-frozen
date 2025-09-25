from typing import Dict, List
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

class AlertasService:
    """Servicio para manejar lógica de alertas"""

    def evaluar_insumo(self, insumo_data: Dict) -> List[Dict]:
        """Evaluar alertas para un insumo específico"""
        alertas = []

        # Alerta de stock bajo
        if self._tiene_stock_bajo(insumo_data):
            alertas.append({
                'tipo': 'STOCK_BAJO',
                'severidad': 'ALTA' if insumo_data.get('es_critico') else 'MEDIA',
                'mensaje': f"Stock por debajo del mínimo ({insumo_data.get('stock_min', 0)})"
            })

        # Alerta de vencimiento próximo
        if self._tiene_vencimiento_proximo(insumo_data):
            alertas.append({
                'tipo': 'PROXIMO_VENCIMIENTO',
                'severidad': 'ALTA' if insumo_data.get('es_critico') else 'MEDIA',
                'mensaje': f"Lote vence el {insumo_data.get('proxima_vencimiento')}"
            })

        return alertas

    def _tiene_stock_bajo(self, insumo_data: Dict) -> bool:
        """Verificar si tiene stock bajo"""
        stock_actual = insumo_data.get('stock_total', 0)
        stock_min = insumo_data.get('stock_min', 0)
        return stock_actual <= stock_min and stock_min > 0

    def _tiene_vencimiento_proximo(self, insumo_data: Dict, dias_adelante: int = 7) -> bool:
        """Verificar si tiene vencimiento próximo"""
        proxima_vencimiento = insumo_data.get('proxima_vencimiento')
        if not proxima_vencimiento:
            return False

        try:
            from datetime import datetime
            if isinstance(proxima_vencimiento, str):
                fecha_vencimiento = datetime.strptime(proxima_vencimiento, '%Y-%m-%d').date()
            else:
                fecha_vencimiento = proxima_vencimiento

            fecha_limite = date.today() + timedelta(days=dias_adelante)
            return fecha_vencimiento <= fecha_limite
        except:
            return False