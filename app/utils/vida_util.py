from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)

def calcular_semaforo(fecha_inicio, fecha_fin, umbral_verde=75, umbral_amarillo=50, dias_alerta=None):
    """
    Calcula el porcentaje de vida útil restante y determina el color del semáforo.
    
    Fórmula: % Vida Restante = ((Fecha Vencimiento - Fecha Actual) / (Fecha Vencimiento - Fecha Inicio)) * 100
    
    Args:
        fecha_inicio (date|str): Fecha de producción o ingreso (fecha_produccion).
        fecha_fin (date|str): Fecha de vencimiento (fecha_vencimiento).
        umbral_verde (int|float|str): Porcentaje mínimo para color verde.
        umbral_amarillo (int|float|str): Porcentaje mínimo para color amarillo.
        dias_alerta (int|str|None): Si los días restantes son <= a este valor, fuerza el color ROJO.
        
    Returns:
        dict: {
            'color': 'success' | 'warning' | 'danger' | None,
            'percent': float | None
        }
    """
    if not fecha_inicio or not fecha_fin:
        return {'color': None, 'percent': None}
        
    try:
        # Convertir umbrales a float para evitar errores de comparación con strings
        try:
            u_verde = float(umbral_verde)
        except (ValueError, TypeError):
            u_verde = 75.0
            
        try:
            u_amarillo = float(umbral_amarillo)
        except (ValueError, TypeError):
            u_amarillo = 50.0
            
        # Convertir dias_alerta a int
        dias_alerta_val = None
        if dias_alerta is not None:
            try:
                dias_alerta_val = int(dias_alerta)
            except (ValueError, TypeError):
                dias_alerta_val = None

        # Convertir strings a objetos date si es necesario
        if isinstance(fecha_inicio, str):
            try:
                fecha_inicio = date.fromisoformat(fecha_inicio.split('T')[0])
            except ValueError:
                pass
                
        if isinstance(fecha_fin, str):
            try:
                fecha_fin = date.fromisoformat(fecha_fin.split('T')[0])
            except ValueError:
                pass

        # Asegurar que son objetos date
        if isinstance(fecha_inicio, datetime):
            fecha_inicio = fecha_inicio.date()
        if isinstance(fecha_fin, datetime):
            fecha_fin = fecha_fin.date()
            
        hoy = date.today()
        
        # Si ya venció (hoy > fin), 0% restante
        if hoy > fecha_fin:
            return {'color': 'danger', 'percent': 0.0}
            
        total_dias = (fecha_fin - fecha_inicio).days
        dias_restantes = (fecha_fin - hoy).days
        
        # Caso borde: Fecha fin anterior o igual a inicio (no debería pasar con check constraints, pero por si acaso)
        if total_dias <= 0:
            return {'color': 'danger', 'percent': 0.0}
        
        # Calcular porcentaje
        porcentaje = (dias_restantes / total_dias) * 100
        
        # Acotar porcentaje visualmente
        if porcentaje < 0: porcentaje = 0.0
        if porcentaje > 100: porcentaje = 100.0
        
        # Lógica base del semáforo
        color = 'danger'
        if porcentaje > u_verde:
            color = 'success'
        elif porcentaje > u_amarillo:
            color = 'warning'
            
        # Override de urgencia por días: Si faltan X días o menos, es ROJO
        # Nota: Si dias_restantes es negativo (vencido), ya retornamos arriba, así que aquí es >= 0.
        if dias_alerta_val is not None and dias_restantes <= dias_alerta_val:
            color = 'danger'
            
        return {
            'color': color,
            'percent': round(porcentaje, 1)
        }
        
    except Exception as e:
        logger.error(f"Error calculando semáforo vida útil: {e}")
        return {'color': None, 'percent': None}
