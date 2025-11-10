from app.controllers.base_controller import BaseController
from app.models.alerta_riesgo import AlertaRiesgoModel
from app.models.trazabilidad import TrazabilidadModel
from app.schemas.alerta_riesgo_schema import AlertaRiesgoSchema
from app.controllers.nota_credito_controller import NotaCreditoController
from app.controllers.inventario_controller import InventarioController
from app.controllers.lote_producto_controller import LoteProductoController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from marshmallow import ValidationError
from flask import flash, url_for
import logging

logger = logging.getLogger(__name__)

class RiesgoController(BaseController):
    def __init__(self):
        super().__init__()
        self.alerta_riesgo_model = AlertaRiesgoModel()
        self.alerta_riesgo_schema = AlertaRiesgoSchema()
        self.trazabilidad_model = TrazabilidadModel()
        self.nota_credito_controller = NotaCreditoController()
        self.inventario_controller = InventarioController()
        self.lote_producto_controller = LoteProductoController()
        self.orden_produccion_controller = OrdenProduccionController()

    def previsualizar_riesgo(self, tipo_entidad, id_entidad):
        try:
            trazabilidad_completa = self.trazabilidad_model.obtener_trazabilidad_unificada(tipo_entidad, id_entidad, nivel='completo')
            
            resumen = trazabilidad_completa.get('resumen', {})
            diagrama = trazabilidad_completa.get('diagrama', {})
            
            afectados_set = set()

            def _safe_add_entity(tipo, id_val):
                try:
                    parsed_id = int(id_val)
                except (ValueError, TypeError):
                    parsed_id = str(id_val)
                afectados_set.add((tipo, parsed_id))

            _safe_add_entity(tipo_entidad, id_entidad)

            for grupo in ['origen', 'destino']:
                for item in resumen.get(grupo, []):
                    _safe_add_entity(item['tipo'], item['id'])
            
            for nodo in diagrama.get('nodes', []):
                try:
                    parts = nodo['id'].rsplit('_', 1)
                    if len(parts) == 2:
                        tipo, id_str = parts
                        _safe_add_entity(tipo, id_str)
                except (ValueError, KeyError):
                    continue

            afectados = [{'tipo_entidad': tipo, 'id_entidad': id_ent} for tipo, id_ent in afectados_set]

            if not afectados:
                return {"success": True, "data": {"afectados_detalle": {}}}, 200

            detalles = self.alerta_riesgo_model.obtener_afectados_detalle_para_previsualizacion(afectados)
            return {"success": True, "data": {"afectados_detalle": detalles}}, 200

        except Exception as e:
            logger.error(f"Error al previsualizar riesgo: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500
        
    def crear_alerta_riesgo_con_usuario(self, datos_json, usuario_id):
        try:
            tipo_entidad = datos_json.get("tipo_entidad")
            id_entidad = datos_json.get("id_entidad")
            motivo = datos_json.get("motivo")
            comentarios = datos_json.get("comentarios")
            url_evidencia = datos_json.get("url_evidencia")
            afectados = datos_json.get("afectados") # Usar la lista de afectados del frontend

            if not tipo_entidad or not id_entidad or not motivo:
                return {"success": False, "error": "tipo_entidad, id_entidad y motivo son requeridos."}, 400
            
            # Asegurarse de que el origen está en la lista de afectados
            origen_en_afectados = any(
                a['tipo_entidad'] == tipo_entidad and str(a['id_entidad']) == str(id_entidad)
                for a in afectados
            )
            if not origen_en_afectados:
                afectados.append({'tipo_entidad': tipo_entidad, 'id_entidad': id_entidad})
            
            count_res = self.alerta_riesgo_model.db.table(self.alerta_riesgo_model.get_table_name()).select('count', count='exact').execute()
            count = count_res.count
            
            nueva_alerta_data = {
                "origen_tipo_entidad": tipo_entidad, "origen_id_entidad": str(id_entidad),
                "estado": "Pendiente", "codigo": f"ALR-{count + 1}",
                "motivo": motivo, "comentarios": comentarios,
                "url_evidencia": url_evidencia, "id_usuario_creador": usuario_id
            }
            
            resultado_alerta = self.alerta_riesgo_model.create(nueva_alerta_data)
            if not resultado_alerta.get("success"):
                return resultado_alerta, 500

            nueva_alerta = resultado_alerta.get("data")[0]
            
            if afectados:
                self.alerta_riesgo_model.asociar_afectados(nueva_alerta['id'], afectados)
                self._procesar_efectos_alerta(afectados, motivo_alerta=f"Alerta {nueva_alerta['codigo']}", usuario_id=usuario_id)

            return {"success": True, "data": nueva_alerta}, 201

        except ValidationError as err:
            return {"success": False, "errors": err.messages}, 400
        except Exception as e:
            logger.error(f"Error al crear alerta de riesgo: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def _procesar_efectos_alerta(self, afectados, motivo_alerta, usuario_id):
        """
        Aplica los efectos secundarios de una alerta: marcar como alertado y poner en cuarentena/pausar.
        """
        mapeo_tablas = {
            'lote_insumo': {'tabla': 'insumos_inventario', 'id_field': 'id_lote'},
            'lote_producto': {'tabla': 'lotes_productos', 'id_field': 'id_lote'},
            'orden_produccion': {'tabla': 'ordenes_produccion', 'id_field': 'id'},
            'pedido': {'tabla': 'pedidos', 'id_field': 'id'}
        }

        for afectado in afectados:
            tipo = afectado['tipo_entidad']
            id_entidad = afectado['id_entidad']

            if tipo in mapeo_tablas:
                config = mapeo_tablas[tipo]
                try:
                    # 1. Marcar en_alerta = true
                    res = self.alerta_riesgo_model.db.table(config['tabla'])\
                        .update({'en_alerta': True})\
                        .eq(config['id_field'], str(id_entidad))\
                        .execute()
                    if res.data is None and res.error:
                         logger.error(f"Error DB al marcar en_alerta para {tipo} #{id_entidad}: {res.error}")

                except Exception as e:
                    logger.error(f"Error al marcar en_alerta para {tipo} #{id_entidad}: {e}", exc_info=True)

            # 2. Poner en cuarentena o pausar
            try:
                if tipo == 'lote_insumo':
                    res_cuarentena, _ = self.inventario_controller.poner_lote_en_cuarentena(
                        lote_id=str(id_entidad), motivo=motivo_alerta, cantidad=999999, usuario_id=usuario_id
                    )
                    if not res_cuarentena.get('success'):
                         logger.error(f"Fallo al poner lote_insumo #{id_entidad} en cuarentena: {res_cuarentena.get('error')}")

                elif tipo == 'lote_producto':
                    res_cuarentena, _ = self.lote_producto_controller.poner_lote_en_cuarentena(
                        lote_id=id_entidad, motivo=motivo_alerta, cantidad=999999, usuario_id=usuario_id
                    )
                    if not res_cuarentena.get('success'):
                         logger.error(f"Fallo al poner lote_producto #{id_entidad} en cuarentena: {res_cuarentena.get('error')}")

                elif tipo == 'orden_produccion':
                    op_res = self.orden_produccion_controller.model.find_by_id(id_entidad)
                    if op_res.get('success') and op_res.get('data'):
                        op = op_res['data'][0]
                        if op.get('estado', '').lower() != 'completada':
                            self.orden_produccion_controller.cambiar_estado_orden(op['id'], 'PAUSADA')
            except Exception as e:
                 logger.error(f"Error al aplicar efecto (cuarentena/pausa) para {tipo} #{id_entidad}: {e}", exc_info=True)
        
    def crear_alerta_riesgo(self, datos_json):
        try:
            tipo_entidad = datos_json.get("tipo_entidad")
            id_entidad = datos_json.get("id_entidad")
            if not tipo_entidad or not id_entidad:
                return {"success": False, "error": "tipo_entidad y id_entidad son requeridos."}, 400
            motivo = datos_json.get("motivo")
            comentarios = datos_json.get("comentarios")
            url_evidencia = datos_json.get("url_evidencia")

            if not tipo_entidad or not id_entidad or not motivo:
                return {"success": False, "error": "tipo_entidad, id_entidad y motivo son requeridos."}, 400
            
            afectados = self.trazabilidad_model.obtener_lista_afectados(tipo_entidad, id_entidad)
            
            count_res = self.alerta_riesgo_model.db.table(self.alerta_riesgo_model.get_table_name()).select('count').execute()
            count = count_res.data[0]['count'] if count_res and count_res.data else 0

            nueva_alerta_data = {
                "origen_tipo_entidad": tipo_entidad,
                "origen_id_entidad": str(id_entidad),
                "estado": "Pendiente",  # Nuevo estado por defecto
                "codigo": f"ALR-{count + 1}",
                "motivo": motivo,
                "comentarios": comentarios,
                "url_evidencia": url_evidencia
            }
            resultado_alerta = self.alerta_riesgo_model.create(nueva_alerta_data)
            if not resultado_alerta.get("success"): return resultado_alerta, 500

            nueva_alerta = resultado_alerta.get("data")
            if afectados:
                                # Corregido: Usar el método correcto para asociar afectados y añadir estado inicial
                self.alerta_riesgo_model.asociar_afectados(nueva_alerta['id'], afectados)

            return {"success": True, "data": nueva_alerta}, 201

        except ValidationError as err:
            return {"success": False, "errors": err.messages}, 400
        except Exception as e:
            logger.error(f"Error al crear alerta de riesgo: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def obtener_detalle_alerta_completo(self, codigo_alerta) -> dict:
        """
        Obtiene todos los datos necesarios para la página de detalle de una alerta,
        incluyendo los detalles de las NC si ya fueron creadas.
        """
        try:
            alerta_res = self.alerta_riesgo_model.obtener_por_codigo(codigo_alerta)
            if not alerta_res.get("success") or not alerta_res.get("data"):
                 return {"success": False, "error": "Alerta no encontrada"}, 404
            
            alerta = alerta_res.get("data")[0]

            from app.controllers.usuario_controller import UsuarioController
            usuario_controller = UsuarioController()

            # Obtener detalles del creador
            creador_id = alerta.get('id_usuario_creador')
            if creador_id:
                alerta['creador_info'] = usuario_controller.obtener_detalles_completos_usuario(creador_id)
            else:
                alerta['creador_info'] = None

            # Siempre obtener los detalles de las entidades afectadas y su estado
            afectados_con_estado = self.alerta_riesgo_model.obtener_afectados_con_estado(alerta['id'])
            participantes = {}
            for afectado in afectados_con_estado:
                resolutor_id = afectado.get('id_usuario_resolucion')
                if resolutor_id and afectado.get('estado') == 'resuelto':
                    if resolutor_id not in participantes:
                        participantes[resolutor_id] = {
                            'info': usuario_controller.obtener_detalles_completos_usuario(resolutor_id),
                            'acciones': []
                        }
                    
                    accion_desc = f"{afectado.get('resolucion_aplicada', 'Acción desconocida').replace('_', ' ').title()} sobre {afectado.get('tipo_entidad', '').replace('_', ' ')} #{afectado.get('id_entidad')}"
                    participantes[resolutor_id]['acciones'].append(accion_desc)
            
            alerta['participantes_resolucion'] = list(participantes.values())
            # --- Fin del procesamiento de participantes ---
            
            # Obtener los detalles completos (código, nombre, etc.)
            afectados_detalle = self.alerta_riesgo_model.obtener_afectados_detalle_para_previsualizacion(afectados_con_estado)

            # Enriquecer los detalles con el estado de resolución
            estado_map = {f"{a['tipo_entidad']}-{a['id_entidad']}": (a['estado'], a['resolucion_aplicada']) for a in afectados_con_estado}
            
            for tipo_entidad, lista_entidades in afectados_detalle.items():
                id_field = 'id' if tipo_entidad == 'pedidos' else 'id_lote'
                if tipo_entidad == 'ordenes_produccion': id_field = 'id'

                for entidad in lista_entidades:
                    key = f"{tipo_entidad.rstrip('es').replace('_', ' ')}-{entidad[id_field]}"
                    estado, resolucion = estado_map.get(key, ('pendiente', None))
                    entidad['estado_resolucion'] = estado
                    entidad['resolucion_aplicada'] = resolucion

            alerta['afectados_detalle'] = afectados_detalle

            # --- INICIO: Calcular porcentajes de afectación para pedidos ---
            if 'pedidos' in afectados_detalle:
                from app.controllers.pedido_controller import PedidoController
                pedido_controller = PedidoController()
                afectados_trazabilidad_completa = self.trazabilidad_model.obtener_lista_afectados(
                    alerta['origen_tipo_entidad'], 
                    alerta['origen_id_entidad']
                )
                lotes_producto_afectados_ids = [
                    str(afectado['id_entidad']) 
                    for afectado in afectados_trazabilidad_completa 
                    if afectado['tipo_entidad'] == 'lote_producto'
                ]

                for pedido in afectados_detalle['pedidos']:
                    try:
                        res_pedido, _ = pedido_controller.obtener_pedido_por_id(pedido['id'])
                        if not res_pedido.get('success'):
                            pedido['afectacion_items_str'] = "Error al cargar"
                            pedido['afectacion_valor_str'] = "Error"
                            continue

                        pedido_completo = res_pedido.get('data', {})
                        items_pedido = pedido_completo.get('items', [])

                        if not items_pedido:
                            pedido['afectacion_items_str'] = "0 de 0"
                            pedido['afectacion_valor_str'] = "0%"
                            continue
                        
                        total_items_count = len(items_pedido)
                        total_valor = 0
                        for item in items_pedido:
                            try:
                                # Acceder al precio unitario anidado
                                precio = float(item.get('producto_nombre', {}).get('precio_unitario', 0))
                                cantidad = float(item.get('cantidad', 0))
                                total_valor += cantidad * precio
                            except (ValueError, TypeError):
                                continue

                        items_afectados_count = 0
                        valor_afectado = 0.0
                        
                        from app.models.pedido import PedidoModel
                        pedido_model = PedidoModel()

                        for item in items_pedido:
                            reservas_del_item = pedido_model.get_reservas_for_item(item['id'])
                            item_es_afectado = any(
                                str(reserva.get('lote_producto_id')) in lotes_producto_afectados_ids 
                                for reserva in reservas_del_item
                            )

                            if item_es_afectado:
                                items_afectados_count += 1
                                try:
                                    precio = float(item.get('producto_nombre', {}).get('precio_unitario', 0))
                                    cantidad = float(item.get('cantidad', 0))
                                    valor_afectado += cantidad * precio
                                except (ValueError, TypeError):
                                    continue

                        pedido['afectacion_items_str'] = f"{items_afectados_count} de {total_items_count}"
                        
                        if total_valor > 0:
                            porcentaje_valor = round((valor_afectado / total_valor) * 100)
                            pedido['afectacion_valor_str'] = f"{porcentaje_valor}%"
                        else:
                            pedido['afectacion_valor_str'] = "0%"
                            
                    except Exception as e:
                        logger.error(f"Error al calcular afectación para pedido {pedido['id']}: {e}", exc_info=True)
                        pedido['afectacion_items_str'] = "Error"
                        pedido['afectacion_valor_str'] = "Error"
            # --- FIN: Calcular porcentajes de afectación para pedidos ---

            if alerta['estado'] in ['Resuelta', 'Cerrada']:
                ncs_asociadas_res = self.nota_credito_controller.obtener_detalle_nc_por_alerta(alerta['id'])
                alerta['notas_de_credito'] = ncs_asociadas_res.get('data', [])
            
            return {"success": True, "data": alerta}, 200
        
        except Exception as e:
            logger.error(f"Error al obtener detalle completo de alerta {codigo_alerta}: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def ejecutar_accion_riesgo(self, codigo_alerta, form_data, usuario_id):
        accion = form_data.get("accion")
        acciones = {
            "nota_credito": self._ejecutar_nota_de_credito,
            "inhabilitar_pedido": self._ejecutar_inhabilitar_pedidos
        }

        if accion in acciones:
            # Todas las funciones de ejecución ahora devuelven un tuple (dict, status_code)
            return acciones[accion](codigo_alerta, form_data, usuario_id)
        
        return ({"success": False, "error": "Acción no válida."}, 400)
        

    def _ejecutar_nota_de_credito(self, codigo_alerta, form_data, usuario_id):
        pedidos_seleccionados = form_data.getlist("pedido_ids")
        recrear_pedido = form_data.get("recrear_pedido") == "on"
        if not pedidos_seleccionados:
            return ({"success": False, "error": "No se seleccionaron pedidos."}, 400)

        try:
            alerta_res = self.alerta_riesgo_model.find_all({'codigo': codigo_alerta}, limit=1)
            if not alerta_res.get('data'): return ({"success": False, "error": "Alerta no encontrada."}, 404)
            alerta = alerta_res.get('data')[0]

            afectados_completo = self.trazabilidad_model.obtener_lista_afectados(
                alerta['origen_tipo_entidad'], 
                alerta['origen_id_entidad']
            )
            lotes_producto_afectados_ids = [
                a['id_entidad'] for a in afectados_completo if a['tipo_entidad'] == 'lote_producto'
            ]
            resultados_nc = self.nota_credito_controller.crear_notas_credito_para_pedidos_afectados(
                alerta_id=alerta['id'],
                pedidos_ids=pedidos_seleccionados,
                motivo=f"Alerta de Riesgo {codigo_alerta}",
                detalle=alerta.get('motivo'),
                lotes_producto_afectados_ids=lotes_producto_afectados_ids
            )
            if not resultados_nc['success']:
                logger.error(f"Error al crear notas de crédito para alerta {codigo_alerta}: {resultados_nc.get('errors')}")
                return ({"success": False, "error": "No se pudo crear Nota de Crédito.", "details": resultados_nc.get('errors')}, 500)
            
            notas_creadas = resultados_nc.get('data', [])
            for nc in notas_creadas:
                pedido_id_resuelto = nc['pedido_origen_id']
                self.alerta_riesgo_model.actualizar_estado_afectados(alerta['id'], [pedido_id_resuelto], 'nota_credito', 'pedido', usuario_id, nc['id'])



            # Lógica para recrear pedidos
            if recrear_pedido:
                for pedido_id in pedidos_seleccionados:
                    self._recrear_pedido_sin_lotes_afectados(pedido_id, lotes_producto_afectados_ids)
            
            return ({"success": True, "message": f"Se procesaron {resultados_nc['count']} notas de crédito."}, 200)

        except Exception as e:
            logger.error(f"Error al ejecutar nota de crédito: {e}", exc_info=True)
            return ({"success": False, "error": f"Error interno: {str(e)}"}, 500)

    def _ejecutar_inhabilitar_pedidos(self, codigo_alerta, form_data, usuario_id):
        pedidos_seleccionados = form_data.getlist("pedido_ids")
        recrear_pedido = form_data.get("recrear_pedido") == "on"
        if not pedidos_seleccionados:
            return ({"success": False, "error": "No se seleccionaron pedidos."}, 400)
        
        try:
            alerta_res = self.alerta_riesgo_model.obtener_por_codigo(codigo_alerta)
            if not alerta_res.get('data'): return ({"success": False, "error": "Alerta no encontrada."}, 404)
            alerta = alerta_res.get('data')[0]
            
            from app.controllers.pedido_controller import PedidoController
            pedido_controller = PedidoController()
            
            inhabilitados_count = 0
            for pedido_id in pedidos_seleccionados:
                res, _ = pedido_controller.cancelar_pedido(int(pedido_id))
                if res.get('success'):
                    self.alerta_riesgo_model.actualizar_estado_afectados(alerta['id'], [pedido_id], 'inhabilitado', 'pedido', usuario_id)
                    inhabilitados_count += 1

            if recrear_pedido:
                afectados = self.alerta_riesgo_model.obtener_afectados(alerta['id'])
                lotes_producto_afectados_ids = [a['id_entidad'] for a in afectados if a['tipo_entidad'] == 'lote_producto']

                for pedido_id in pedidos_seleccionados:
                    self._recrear_pedido_sin_lotes_afectados(pedido_id, lotes_producto_afectados_ids)

            if inhabilitados_count == 0:
                return ({"success": False, "error": "Ningún pedido pudo ser inhabilitado."}, 500)

            return ({"success": True, "message": f"Se inhabilitaron {inhabilitados_count} pedidos."}, 200)

        except Exception as e:
            logger.error(f"Error al cancelar pedidos: {e}", exc_info=True)
            return ({"success": False, "error": f"Error interno: {str(e)}"}, 500)

    def _recrear_pedido_sin_lotes_afectados(self, pedido_id_original, lotes_afectados_ids):
        from app.controllers.pedido_controller import PedidoController
        from flask_jwt_extended import get_current_user

        pedido_controller = PedidoController()
        
        # 1. Obtener datos del pedido original
        pedido_original_res, _ = pedido_controller.obtener_pedido_por_id(int(pedido_id_original))
        if not pedido_original_res.get('success'):
            logger.error(f"No se pudo encontrar el pedido original {pedido_id_original} para recrearlo.")
            return

        pedido_original = pedido_original_res.get('data')

        # 2. Filtrar items que NO están afectados
        items_no_afectados = pedido_controller.model.get_items_no_afectados(int(pedido_id_original), lotes_afectados_ids)
        
        if not items_no_afectados:
            logger.info(f"No hay items no afectados para recrear el pedido {pedido_id_original}.")
            return

        # 3. Crear el nuevo pedido
        nuevo_pedido_data = {
            "id_cliente": pedido_original['id_cliente'],
            "fecha_requerido": pedido_original['fecha_requerido'],
            "id_direccion_entrega": pedido_original['id_direccion_entrega'],
            "codigo": f"{pedido_original['codigo']}-R1",
            "items": items_no_afectados
        }
        
        # Simular un usuario del sistema si no hay contexto de request
        usuario_id = -1 # ID para 'SISTEMA'
        try:
             # Si hay un usuario logueado, lo usamos
             current_user = get_current_user()
             if current_user:
                usuario_id = current_user.id
        except RuntimeError:
             logger.warning("Creando pedido recreado fuera del contexto de una solicitud. Usando ID de SISTEMA.")


        pedido_controller.crear_pedido_con_items(nuevo_pedido_data, usuario_id=usuario_id)
        logger.info(f"Pedido {pedido_id_original} recreado como un nuevo pedido.")
    
    def _ejecutar_cuarentena_lotes(self, codigo_alerta, form_data):
        lote_insumo_ids = form_data.getlist("lote_insumo_ids")
        lote_producto_ids = form_data.getlist("lote_producto_ids")
        
        if not lote_insumo_ids and not lote_producto_ids:
            return ({"success": False, "error": "No se seleccionaron lotes."}, 400)

        from app.controllers.inventario_controller import InventarioController
        from app.controllers.lote_producto_controller import LoteProductoController
        from flask_jwt_extended import get_jwt_identity

        inventario_controller = InventarioController()
        lote_producto_controller = LoteProductoController()
        usuario_id = get_jwt_identity()
        
        count = 0
        alerta_res = self.alerta_riesgo_model.find_all({'codigo': codigo_alerta}, limit=1)
        if not alerta_res.get('data'): return ({"success": False, "error": "Alerta no encontrada."}, 404)
        alerta = alerta_res.get('data')[0]

        for lote_id in lote_insumo_ids:
            res, _ = inventario_controller.poner_lote_en_cuarentena(lote_id, f"Alerta {codigo_alerta}", 999999, usuario_id)
            if res.get('success'):
                self.alerta_riesgo_model.actualizar_estado_afectados(alerta['id'], [lote_id], 'cuarentena', 'lote_insumo')
                count += 1
        
        for lote_id in lote_producto_ids:
            res, _ = lote_producto_controller.poner_lote_en_cuarentena(lote_id, f"Alerta {codigo_alerta}", 999999)
            if res.get('success'):
                self.alerta_riesgo_model.actualizar_estado_afectados(alerta['id'], [lote_id], 'cuarentena', 'lote_producto')
                count += 1

        if count == 0:
             return ({"success": False, "error": "Ningún lote pudo ser puesto en cuarentena."}, 500)

        return ({"success": True, "message": f"Se pusieron {count} lotes en cuarentena."}, 200)

    def _ejecutar_pausar_ops(self, codigo_alerta, form_data):
        op_ids = form_data.getlist("op_ids")
        if not op_ids:
            return ({"success": False, "error": "No se seleccionaron Órdenes de Producción."}, 400)

        from app.controllers.orden_produccion_controller import OrdenProduccionController
        op_controller = OrdenProduccionController()
        
        alerta_res = self.alerta_riesgo_model.find_all({'codigo': codigo_alerta}, limit=1)
        if not alerta_res.get('data'): return ({"success": False, "error": "Alerta no encontrada."}, 404)
        alerta = alerta_res.get('data')[0]

        count = 0
        for op_id in op_ids:
            res, _ = op_controller.cambiar_estado_orden(int(op_id), "PAUSADA")
            if res.get('success'):
                self.alerta_riesgo_model.actualizar_estado_afectados(alerta['id'], [op_id], 'pausada', 'orden_produccion')
                count += 1
        
        if count == 0:
            return ({"success": False, "error": "Ninguna OP pudo ser pausada."}, 500)

        return ({"success": True, "message": f"Se pausaron {count} Órdenes de Producción."}, 200)


    def contactar_clientes_afectados(self, codigo_alerta, form_data):
        pedido_ids = form_data.getlist("pedido_ids[]")
        asunto = form_data.get("asunto")
        cuerpo = form_data.get("cuerpo")

        if not pedido_ids:
            return {"success": False, "error": "No se seleccionaron pedidos."}, 400
        if not asunto or not cuerpo:
            return {"success": False, "error": "El asunto y el cuerpo son requeridos."}, 400

        try:
            from app.controllers.pedido_controller import PedidoController
            from app.services.email_service import send_email
            
            pedido_controller = PedidoController()
            
            correos_enviados = 0
            errores = []

            for pedido_id in pedido_ids:
                res, _ = pedido_controller.obtener_pedido_por_id(int(pedido_id))
                if not res.get('success'):
                    errores.append(f"No se encontró el pedido #{pedido_id}.")
                    continue
                
                pedido_data = res.get('data')
                cliente_email = pedido_data.get('cliente', {}).get('email')
                
                if not cliente_email:
                    errores.append(f"El cliente del pedido #{pedido_id} no tiene un email registrado.")
                    continue

                try:
                    # Usar la configuración general de correo
                    send_email(cliente_email, asunto, cuerpo)
                    correos_enviados += 1
                except Exception as e:
                    logger.error(f"Error al enviar correo para pedido #{pedido_id}: {e}", exc_info=True)
                    errores.append(f"No se pudo enviar el correo para el pedido #{pedido_id}.")

            if correos_enviados == 0 and errores:
                 return {"success": False, "error": f"No se pudo enviar ningún correo. Detalles: {'; '.join(errores)}"}, 500
            
            mensaje = f"Se enviaron {correos_enviados} de {len(pedido_ids)} correos."
            if errores:
                mensaje += f" Errores: {'; '.join(errores)}"

            return {"success": True, "message": mensaje}, 200

        except Exception as e:
            logger.error(f"Error en contactar_clientes_afectados para alerta {codigo_alerta}: {e}", exc_info=True)
            return {"success": False, "error": "Error interno del servidor al procesar la solicitud."}, 500