from app.models.pedido import PedidoModel
from app.models.orden_compra_model import OrdenCompraModel
from app.models.inventario import InventarioModel
from datetime import datetime, timedelta

class ReportesController:
    def __init__(self):
        self.pedido_model = PedidoModel()
        self.orden_compra_model = OrdenCompraModel()
        self.inventario_model = InventarioModel()

    def obtener_ingresos_vs_egresos(self, periodo='semanal'):
        hoy = datetime.now()
        if periodo == 'semanal':
            fecha_inicio = hoy - timedelta(days=hoy.weekday())
            delta = timedelta(days=1)
            labels = [(fecha_inicio + timedelta(days=i)).strftime('%A') for i in range(7)]
        elif periodo == 'mensual':
            fecha_inicio = hoy.replace(day=1)
            delta = timedelta(days=1)
            labels = [str(i) for i in range(1, (hoy.replace(month=hoy.month % 12 + 1, day=1) - timedelta(days=1)).day + 1)]
        else: # anual
            fecha_inicio = hoy.replace(month=1, day=1)
            delta = timedelta(days=30) # Aproximado
            labels = [f"Mes {i}" for i in range(1, 13)]
        
        fecha_fin = hoy

        ingresos_data = self.pedido_model.get_ingresos_en_periodo(fecha_inicio.isoformat(), fecha_fin.isoformat())
        egresos_data = self.orden_compra_model.get_egresos_en_periodo(fecha_inicio.isoformat(), fecha_fin.isoformat())

        ingresos = self._procesar_datos_periodo(ingresos_data.get('data', []), 'fecha_solicitud', labels, periodo)
        egresos = self._procesar_datos_periodo(egresos_data.get('data', []), 'fecha_emision', labels, periodo)

        return {"labels": labels, "ingresos": ingresos, "egresos": egresos}

    def _procesar_datos_periodo(self, data, fecha_field, labels, periodo):
        processed_data = [0] * len(labels)
        for item in data:
            fecha = datetime.fromisoformat(item[fecha_field])
            if periodo == 'semanal':
                index = fecha.weekday()
            elif periodo == 'mensual':
                index = fecha.day - 1
            else: # anual
                index = fecha.month - 1
            
            if 0 <= index < len(processed_data):
                processed_data[index] += float(item.get('total', 0))
        return processed_data

    def obtener_top_productos(self):
        result = self.pedido_model.get_top_selling_products()
        if not result.get('success'):
            return {"labels": [], "data": []}
        
        data = result.get('data', [])
        labels = [item.get('producto_nombre', 'N/A') for item in data]
        cantidades = [item.get('cantidad_total', 0) for item in data]
        return {"labels": labels, "data": cantidades}

    def obtener_stock_critico(self):
        result = self.inventario_model.get_stock_critico()
        if not result.get('success'):
            return {"labels": [], "data_actual": [], "data_minimo": []}

        data = result.get('data', [])
        labels = [item.get('nombre', 'N/A') for item in data]
        data_actual = [item.get('stock_actual', 0) for item in data]
        data_minimo = [item.get('stock_min', 0) for item in data]
        return {"labels": labels, "data_actual": data_actual, "data_minimo": data_minimo}

    def guardar_meta_flujo_caja(self, meta):
        import json
        try:
            with open('config_metas.json', 'w') as f:
                json.dump({'meta_flujo_caja': meta}, f)
        except IOError:
            # Manejar error de escritura
            pass

    def obtener_configuracion_metas(self):
        import json
        try:
            with open('config_metas.json', 'r') as f:
                config = json.load(f)
        except (IOError, json.JSONDecodeError):
            config = {'meta_flujo_caja': 0}

        # Calcular meta sugerida
        hoy = datetime.now()
        hace_3_meses = hoy - timedelta(days=90)
        ingresos_res = self.pedido_model.get_ingresos_en_periodo(hace_3_meses.isoformat(), hoy.isoformat())
        
        total_ingresos = 0
        if ingresos_res.get('success'):
            total_ingresos = sum(float(i.get('total', 0)) for i in ingresos_res.get('data', []))
        
        # Promedio mensual
        meta_sugerida = (total_ingresos / 3) if total_ingresos > 0 else 50000 # Un fallback por si no hay datos
        
        config['meta_sugerida'] = round(meta_sugerida, 2)
        return config
