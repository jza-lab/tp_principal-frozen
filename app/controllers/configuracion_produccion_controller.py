import logging
from datetime import date, timedelta
import holidays
import calendar
from app.controllers.base_controller import BaseController
from app.models.configuracion_produccion import ConfiguracionProduccionModel
from app.models.calendario_excepcion import CalendarioExcepcionModel

logger = logging.getLogger(__name__)

class ConfiguracionProduccionController(BaseController):
    """
    Controlador para gestionar la lógica de negocio de la configuración de producción.
    """
    DIA_SEMANA_MAP = {
        'monday': 1, 'lunes': 1,
        'tuesday': 2, 'martes': 2,
        'wednesday': 3, 'miercoles': 3, 'miércoles': 3,
        'thursday': 4, 'jueves': 4,
        'friday': 5, 'viernes': 5,
        'saturday': 6, 'sabado': 6, 'sábado': 6,
        'sunday': 7, 'domingo': 7
    }

    def __init__(self):
        super().__init__()
        self.model = ConfiguracionProduccionModel()
        self.excepcion_model = CalendarioExcepcionModel()

    def _normalize_day_to_iso(self, day_name):
        """Convierte nombre de día a ISO 1-7 (Lunes-Domingo)."""
        if isinstance(day_name, int):
            return day_name if 1 <= day_name <= 7 else None
        if not day_name:
            return None
        return self.DIA_SEMANA_MAP.get(str(day_name).lower(), None)

    def get_configuracion_produccion_map(self):
        """
        Obtiene la configuración y la mapea a un diccionario keyed por ISO weekday (1-7).
        Retorna: {1: {'id': PK, 'horas': X, 'dia_semana': 'Lunes'}, ...}
        """
        result = self.model.find_all()
        if not result.get('success'):
            return result

        data_list = result.get('data', [])
        config_map = {}
        
        for item in data_list:
            dia_str = item.get('dia_semana')
            iso_day = self._normalize_day_to_iso(dia_str)
            if iso_day:
                config_map[iso_day] = item
            else:
                try:
                    fallback_id = int(item.get('id'))
                    if 1 <= fallback_id <= 7:
                        config_map[fallback_id] = item
                except (ValueError, TypeError):
                    continue

        return {'success': True, 'data': config_map}

    def update_configuracion_produccion(self, configs_data):
        """
        Actualiza la configuración.
        'configs_data' debe ser una lista de diccionarios con 'id' (PK real) y 'horas'.
        """
        updated_configs = []
        for config in configs_data:
            config_id = config.get('id')
            horas = config.get('horas')
            if config_id is None:
                continue
            data_to_update = {'horas': horas}
            result = self.model.update(config_id, data_to_update)
            if not result.get('success'):
                return self.error_response(f"Error al actualizar la configuración para ID {config_id}.")
            updated_configs.append(result['data'])
        
        return self.success_response(updated_configs, "Configuración actualizada exitosamente.")

    def get_calendario_mensual(self, year: int, month: int):
        """
        Obtiene los datos del calendario para un mes específico.
        Logic Hierarchy: Exception > National Holiday > Standard Config
        """
        try:
            # 1. Obtener configuración estándar
            config_resp = self.get_configuracion_produccion_map()
            config_std = {}
            if config_resp.get('success'):
                for iso_day, data in config_resp.get('data', {}).items():
                    config_std[iso_day] = float(data.get('horas', 0))
            else:
                logger.warning(f"No se pudo cargar config. Usando default.")
                config_std = {1: 8.0, 2: 8.0, 3: 8.0, 4: 8.0, 5: 8.0, 6: 0.0, 7: 0.0}

            # 2. Calcular rango del mes
            _, num_days = calendar.monthrange(year, month)
            start_date = date(year, month, 1)
            end_date = date(year, month, num_days)

            # 3. Obtener feriados
            try:
                feriados_ar = holidays.country_holidays('AR', years=[year])
            except Exception:
                feriados_ar = {}

            # 4. Obtener Excepciones para este mes
            filtros_excepcion = {
                'fecha_gte': start_date.isoformat(),
                'fecha_lte': end_date.isoformat()
            }
            excepciones_resp = self.excepcion_model.find_all(filters=filtros_excepcion)
            excepciones_map = {}
            if excepciones_resp.get('success'):
                for ex in excepciones_resp.get('data', []):
                    excepciones_map[ex['fecha']] = ex

            # 5. Construir grilla
            dias_calendario = []
            total_horas_laborables = 0.0
            cal_matrix = calendar.monthcalendar(year, month)
            
            for week in cal_matrix:
                semana_data = []
                for day_num in week:
                    if day_num == 0:
                        semana_data.append(None)
                        continue
                    
                    fecha_actual = date(year, month, day_num)
                    fecha_iso = fecha_actual.isoformat()
                    weekday_iso = fecha_actual.isoweekday()
                    
                    # -- Default State --
                    horas_std = config_std.get(weekday_iso, 0.0)
                    es_laborable = horas_std > 0
                    horas_efectivas = horas_std
                    clase_css = "laborable" if es_laborable else "fin-semana"
                    estado_texto = "Laborable" if es_laborable else "Fin de Semana"
                    
                    # -- Check Holiday --
                    nombre_feriado = feriados_ar.get(fecha_actual)
                    es_feriado_nacional = nombre_feriado is not None
                    
                    if es_feriado_nacional:
                        es_laborable = False
                        horas_efectivas = 0.0
                        clase_css = "feriado"
                        estado_texto = nombre_feriado

                    # -- Check Exception (Highest Priority) --
                    excepcion = excepciones_map.get(fecha_iso)
                    es_excepcion = excepcion is not None
                    motivo_excepcion = ""
                    
                    if es_excepcion:
                        es_override_laborable = excepcion['es_laborable'] # True/False
                        motivo_excepcion = excepcion.get('motivo', 'Excepción manual')
                        
                        if es_override_laborable:
                            # Forcing Work Day (e.g., Extra Saturday)
                            es_laborable = True
                            try:
                                horas_efectivas = float(excepcion.get('horas', 0))
                            except:
                                horas_efectivas = 0.0
                            clase_css = "excepcion-laborable" # New class needed
                            estado_texto = motivo_excepcion
                        else:
                            # Forcing Day Off (e.g., Maintenance)
                            es_laborable = False
                            horas_efectivas = 0.0
                            clase_css = "excepcion-libre" # New class needed
                            estado_texto = motivo_excepcion

                    total_horas_laborables += horas_efectivas

                    semana_data.append({
                        'dia': day_num,
                        'fecha': fecha_iso,
                        'horas': horas_efectivas,
                        'es_laborable': es_laborable,
                        'clase': clase_css,
                        'titulo': estado_texto,
                        'es_feriado': es_feriado_nacional,
                        'es_excepcion': es_excepcion,
                        'excepcion_data': excepcion # Pass full object for modal
                    })
                dias_calendario.append(semana_data)

            return self.success_response({
                'calendario': dias_calendario,
                'total_horas': total_horas_laborables,
                'year': year,
                'month': month,
                'month_name': calendar.month_name[month],
                'dias_nombres': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
            })

        except Exception as e:
            logger.error(f"Error en get_calendario_mensual: {e}", exc_info=True)
            return self.success_response({
                'calendario': [],
                'total_horas': 0,
                'year': year, 'month': month, 'month_name': 'Error',
                'error': str(e)
            })

    def guardar_excepcion(self, data):
        """
        Crea o actualiza una excepción de calendario.
        """
        try:
            fecha = data.get('fecha')
            es_laborable = data.get('es_laborable') in ['true', 'True', True, '1', 1]
            motivo = data.get('motivo')
            horas = data.get('horas', 0)

            if not fecha:
                return self.error_response("Fecha requerida.", 400)

            # Check existing
            existing_resp = self.excepcion_model.find_all(filters={'fecha': fecha})
            existing_id = None
            if existing_resp.get('success') and existing_resp.get('data'):
                existing_id = existing_resp['data'][0]['id']

            payload = {
                'fecha': fecha,
                'es_laborable': es_laborable,
                'motivo': motivo,
                'horas': float(horas) if horas else 0
            }

            if existing_id:
                res = self.excepcion_model.update(existing_id, payload)
            else:
                res = self.excepcion_model.create(payload)

            if res.get('success'):
                return self.success_response(res['data'], "Excepción guardada.")
            else:
                return self.error_response(res.get('error', 'Error al guardar.'), 500)

        except Exception as e:
            logger.error(f"Error guardando excepcion: {e}", exc_info=True)
            return self.error_response(str(e), 500)

    def eliminar_excepcion(self, fecha):
        """
        Elimina una excepción por fecha.
        """
        try:
            # Find ID by date
            existing_resp = self.excepcion_model.find_all(filters={'fecha': fecha})
            if existing_resp.get('success') and existing_resp.get('data'):
                record_id = existing_resp['data'][0]['id']
                res = self.excepcion_model.delete(record_id, 'id')
                if res.get('success'):
                    return self.success_response(message="Excepción eliminada.")
                else:
                    return self.error_response("Error al eliminar.")
            else:
                return self.error_response("No se encontró excepción para esa fecha.", 404)
        except Exception as e:
            logger.error(f"Error eliminando excepcion: {e}", exc_info=True)
            return self.error_response(str(e), 500)
