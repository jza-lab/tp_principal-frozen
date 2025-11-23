import re
from datetime import datetime, timedelta
from app.controllers.base_controller import BaseController
from app.models.vehiculo import VehiculoModel

class VehiculoController(BaseController):
    def __init__(self):
        super().__init__()
        self.model = VehiculoModel()

    def _validar_datos_vehiculo(self, data, requerir_fechas=False):
        """
        Valida los datos de un vehículo.
        Devuelve un diccionario con {'success': True} o {'success': False, 'error': ...}
        """
        # Validación de patente
        patente = data.get('patente', '').strip().upper().replace(' ', '')
        if not re.match(r'^(?:[A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2})$', patente):
            return {'success': False, 'error': 'El formato de la patente no es válido. Use LLLNNN o LLNNNLL.'}
        data['patente'] = patente # Guardar formato normalizado

        # Validación de capacidad_kg
        try:
            capacidad_kg = float(data.get('capacidad_kg'))
            if not 100 <= capacidad_kg <= 500:
                return {'success': False, 'error': 'La capacidad de carga debe estar entre 100 y 500 kg.'}
        except (ValueError, TypeError):
            return {'success': False, 'error': 'La capacidad de carga debe ser un número válido.'}

        # Validación de nombre_conductor
        nombre_conductor = data.get('nombre_conductor', '').strip()
        if not nombre_conductor or len(nombre_conductor) < 3 or not all(c.isalpha() or c.isspace() for c in nombre_conductor):
            return {'success': False, 'error': 'El nombre del conductor es requerido, debe tener al menos 3 letras y no contener números.'}

        # Validación de dni_conductor
        dni_conductor = data.get('dni_conductor', '').strip()
        if not dni_conductor.isdigit() or not (7 <= len(dni_conductor) <= 8):
            return {'success': False, 'error': 'El DNI del conductor debe ser un número de 7 u 8 dígitos.'}

        # Validación de telefono_conductor
        telefono_conductor = data.get('telefono_conductor', '').strip()
        if telefono_conductor and (not telefono_conductor.isdigit() or len(telefono_conductor) < 7):
            return {'success': False, 'error': 'El teléfono del conductor debe ser un número de al menos 7 dígitos.'}
            
        # Validación de fechas obligatorias en creación
        if requerir_fechas:
            if not data.get('fecha_vtv_emision'):
                return {'success': False, 'error': 'La fecha de realización de VTV es obligatoria.'}
            if not data.get('fecha_licencia_emision'):
                return {'success': False, 'error': 'La fecha de emisión de la Licencia es obligatoria.'}

        return {'success': True}

    def _procesar_fechas(self, data):
        """
        Procesa las fechas de emisión para calcular vencimientos.
        """
        try:
            # Procesar VTV (Validez 1 año)
            if 'fecha_vtv_emision' in data and data['fecha_vtv_emision']:
                fecha_emision = datetime.strptime(data['fecha_vtv_emision'], '%Y-%m-%d')
                # Sumar 1 año (aprox 365 días, manejando bisiestos simple)
                # Mejor aproximación: mismo mes, mismo día, año siguiente.
                try:
                    fecha_vencimiento = fecha_emision.replace(year=fecha_emision.year + 1)
                except ValueError: # Caso 29 Feb
                     fecha_vencimiento = fecha_emision + timedelta(days=365)
                
                data['vtv_vencimiento'] = fecha_vencimiento.strftime('%Y-%m-%d')
            
            # Procesar Licencia (Validez 5 años)
            if 'fecha_licencia_emision' in data and data['fecha_licencia_emision']:
                fecha_emision = datetime.strptime(data['fecha_licencia_emision'], '%Y-%m-%d')
                try:
                    fecha_vencimiento = fecha_emision.replace(year=fecha_emision.year + 5)
                except ValueError:
                    fecha_vencimiento = fecha_emision.replace(day=28) + timedelta(days=4*365 + 1) # Simplificado
                
                data['licencia_vencimiento'] = fecha_vencimiento.strftime('%Y-%m-%d')

            # Limpiar campos auxiliares que no van a la BD (si el modelo es estricto, 
            # pero Supabase suele ignorar extras si no estan en el schema, aunque mejor limpiar)
            data.pop('fecha_vtv_emision', None)
            data.pop('fecha_licencia_emision', None)

        except ValueError:
            return {'success': False, 'error': 'Formato de fecha inválido.'}
        
        return {'success': True}

    def _enrich_vehicle_data(self, vehiculos_list):
        """
        Calcula alertas y formatea fechas para una lista de vehiculos.
        Modifica la lista in-place.
        """
        hoy = datetime.now().date()
        alerta_delta = timedelta(days=30)

        for vehiculo in vehiculos_list:
             # Alerta VTV
            vehiculo['alerta_vtv'] = False # Mantenido por compatibilidad legacy
            vehiculo['estado_vtv'] = 'AL_DIA' # AL_DIA, PRONTO_VENC, VENCIDA
            vehiculo['vtv_emision_estimada'] = None # Nuevo campo
            
            if vehiculo.get('vtv_vencimiento'):
                try:
                    # Manejar formato ISO o YYYY-MM-DD que pueda venir de DB
                    venc_str = str(vehiculo['vtv_vencimiento'])
                    # Supabase puede devolver timestamp con T
                    if 'T' in venc_str:
                            venc_str = venc_str.split('T')[0]
                    venc = datetime.strptime(venc_str, '%Y-%m-%d').date()
                    
                    # Lógica de 3 estados
                    if venc < hoy:
                        vehiculo['estado_vtv'] = 'VENCIDA'
                        vehiculo['alerta_vtv'] = True # Rojo
                    elif venc <= (hoy + alerta_delta):
                        vehiculo['estado_vtv'] = 'PRONTO_VENC'
                        vehiculo['alerta_vtv'] = True # Usamos esto para pintar de rojo/amarillo en front? Mejor diferenciar.
                    else:
                        vehiculo['estado_vtv'] = 'AL_DIA'

                    # Calcular emision estimada (vencimiento - 1 año)
                    try:
                        emision = venc.replace(year=venc.year - 1)
                    except ValueError:
                        emision = venc - timedelta(days=365)
                    vehiculo['vtv_emision_estimada'] = emision.strftime('%Y-%m-%d')

                    # Guardar formato limpio para vista
                    vehiculo['vtv_vencimiento'] = venc_str
                except (ValueError, TypeError):
                    pass

            # Alerta Licencia
            vehiculo['alerta_licencia'] = False
            vehiculo['estado_licencia'] = 'AL_DIA'
            vehiculo['licencia_emision_estimada'] = None 
            
            if vehiculo.get('licencia_vencimiento'):
                try:
                    venc_str = str(vehiculo['licencia_vencimiento'])
                    if 'T' in venc_str:
                            venc_str = venc_str.split('T')[0]
                    venc = datetime.strptime(venc_str, '%Y-%m-%d').date()
                    
                    # Lógica de 3 estados
                    if venc < hoy:
                        vehiculo['estado_licencia'] = 'VENCIDA'
                        vehiculo['alerta_licencia'] = True
                    elif venc <= (hoy + alerta_delta):
                        vehiculo['estado_licencia'] = 'PRONTO_VENC'
                        vehiculo['alerta_licencia'] = True
                    else:
                        vehiculo['estado_licencia'] = 'AL_DIA'
                        
                    # Calcular emision estimada (vencimiento - 5 años)
                    try:
                        emision = venc.replace(year=venc.year - 5)
                    except ValueError:
                         # Ajuste simple
                        emision = venc.replace(day=28) - timedelta(days=365*5) # Aprox
                    vehiculo['licencia_emision_estimada'] = emision.strftime('%Y-%m-%d')

                    vehiculo['licencia_vencimiento'] = venc_str
                except (ValueError, TypeError):
                    pass

    def crear_vehiculo(self, data):
        # Lógica para crear un nuevo vehículo
        validacion = self._validar_datos_vehiculo(data, requerir_fechas=True)
        if not validacion['success']:
            return validacion
            
        procesamiento = self._procesar_fechas(data)
        if not procesamiento['success']:
            return procesamiento

        data.pop('csrf_token', None) # Eliminar el token CSRF antes de crear
        response = self.model.create(data)
        
        if not response['success']:
            # Verificar error de duplicidad en el mensaje de error devuelto por el modelo
            error_msg = str(response.get('error', ''))
            if '23505' in error_msg or 'duplicate key' in error_msg:
                return {'success': False, 'error': f'La patente {data.get("patente")} ya existe.'}
        
        return response

    def obtener_vehiculo_por_id(self, vehiculo_id):
        response = self.model.find_by_id(vehiculo_id)
        if response['success'] and response['data']:
             # Si find_by_id devuelve un dict, lo metemos en lista para procesar
             lista = [response['data']]
             self._enrich_vehicle_data(lista)
             response['data'] = lista[0]
        return response

    def obtener_todos_los_vehiculos(self):
        response = self.model.find_all()
        if response['success'] and response['data']:
            self._enrich_vehicle_data(response['data'])
        return response

    def actualizar_vehiculo(self, vehiculo_id, data):
        validacion = self._validar_datos_vehiculo(data, requerir_fechas=False)
        if not validacion['success']:
            return validacion
            
        procesamiento = self._procesar_fechas(data)
        if not procesamiento['success']:
            return procesamiento
            
        data.pop('csrf_token', None) # Eliminar el token CSRF antes de actualizar
        response = self.model.update(vehiculo_id, data)
        
        if not response['success']:
            error_msg = str(response.get('error', ''))
            if '23505' in error_msg or 'duplicate key' in error_msg:
                return {'success': False, 'error': f'La patente {data.get("patente")} ya existe.'}
        
        return response

    def eliminar_vehiculo(self, vehiculo_id):
        """
        OBSOLETO: Usar cambiar_estado.
        Mantenido temporalmente o redirigido a cambiar_estado si se requiere conservar la ruta.
        Por ahora, mantenemos la eliminación física si se llama explícitamente a este método,
        pero la UI usará cambiar_estado.
        """
        return self.model.delete(vehiculo_id)

    def cambiar_estado(self, vehiculo_id):
        """
        Alterna el estado activo/inactivo de un vehículo.
        """
        response = self.model.find_by_id(vehiculo_id)
        if not response['success'] or not response['data']:
            return {'success': False, 'error': 'Vehículo no encontrado.'}
        
        # Obtener estado actual, default True si es None
        estado_actual = response['data'].get('activo')
        if estado_actual is None: 
            estado_actual = True
            
        nuevo_estado = not estado_actual
        
        return self.model.update(vehiculo_id, {'activo': nuevo_estado})

    def buscar_por_patente(self, patente=None, search=None):
        """
        Busca vehículos por patente (exacta o parcial) o búsqueda general.
        Solo devuelve vehículos con documentación al día o pronta a vencer,
        FILTRANDO los que tienen documentación VENCIDA.
        """
        filters = {}
        if patente:
             # Búsqueda exacta legacy
             filters['patente'] = patente.strip().upper()
        elif search:
             # Búsqueda parcial por patente
             search_term = search.strip().upper()
             filters['patente_ilike'] = f'%{search_term}%'
        
        response = self.model.find_all(filters=filters)
        if response['success'] and response['data']:
            # Enriquecer primero para calcular estados
            self._enrich_vehicle_data(response['data'])
            
            # FILTRADO: Eliminar vehículos con documentación VENCIDA
            # Solo permitimos AL_DIA y PRONTO_VENC (este ultimo es discutible si bloqueamos, 
            # pero el usuario dijo "no me tiene que poder dejar asignarle... o la licencia vencida".
            # "Al día" suele incluir "Pronto Venc" funcionalmente hasta el ultimo dia.
            # Asumimos que PRONTO_VENC es valido para despachar (sigue vigente).
            
            vehiculos_validos = []
            for v in response['data']:
                vtv_ok = v.get('estado_vtv') != 'VENCIDA'
                lic_ok = v.get('estado_licencia') != 'VENCIDA'
                activo_ok = v.get('activo', True)
                
                # Si ambas están OK (no vencidas) y el vehículo está activo
                if vtv_ok and lic_ok and activo_ok:
                    vehiculos_validos.append(v)
            
            response['data'] = vehiculos_validos
            
        return response
