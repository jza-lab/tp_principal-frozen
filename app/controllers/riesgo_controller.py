from app.controllers.base_controller import BaseController
from app.models.alerta_riesgo import AlertaRiesgoModel
from app.models.trazabilidad import TrazabilidadModel 
from app.schemas.alerta_riesgo_schema import AlertaRiesgoSchema
from app.controllers.nota_credito_controller import NotaCreditoController
from marshmallow import ValidationError
from flask import flash, url_for
from app.services.email_service import send_email
from app.models.usuario import UsuarioModel
from app.models.rol import RoleModel
import logging
import os


logger = logging.getLogger(__name__)

class RiesgoController(BaseController):
    def __init__(self):
        super().__init__()
        self.alerta_riesgo_model = AlertaRiesgoModel()
        self.alerta_riesgo_schema = AlertaRiesgoSchema()
        self.trazabilidad_model = TrazabilidadModel() 
        self.nota_credito_controller = NotaCreditoController()

    def previsualizar_riesgo(self, tipo_entidad, id_entidad):
        try:
            afectados = self.trazabilidad_model.obtener_afectados_para_alerta(tipo_entidad, id_entidad)
            
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
            if not tipo_entidad or not id_entidad:
                return {"success": False, "error": "tipo_entidad y id_entidad son requeridos."}, 400
            
            motivo = datos_json.get("motivo")
            comentarios = datos_json.get("comentarios")
            url_evidencia = datos_json.get("url_evidencia")

            if not tipo_entidad or not id_entidad or not motivo:
                return {"success": False, "error": "tipo_entidad, id_entidad y motivo son requeridos."}, 400
            
            afectados = self.trazabilidad_model.obtener_afectados_para_alerta(tipo_entidad, id_entidad)
            
            count_res = self.alerta_riesgo_model.db.table(self.alerta_riesgo_model.get_table_name()).select('count', count='exact').execute()
            count = count_res.count
            
            nueva_alerta_data = {
                "origen_tipo_entidad": tipo_entidad,
                "origen_id_entidad": str(id_entidad),
                "estado": "Pendiente",
                "codigo": f"ALR-{count + 1}",
                "motivo": motivo,
                "comentarios": comentarios,
                "url_evidencia": url_evidencia,
                "id_usuario_creador": usuario_id
            }
            
            resultado_alerta = self.alerta_riesgo_model.create(nueva_alerta_data)
            if not resultado_alerta.get("success"):
                return resultado_alerta, 500

            nueva_alerta = resultado_alerta.get("data")
            if isinstance(nueva_alerta, list):
                nueva_alerta = nueva_alerta[0]
                
            if afectados:
                self.alerta_riesgo_model.asociar_afectados(nueva_alerta['id'], afectados)
                # Procesar efectos secundarios después de crear la alerta
                self._procesar_efectos_secundarios_alerta(nueva_alerta, afectados, f"Alerta {nueva_alerta['codigo']}", usuario_id)
            
            self._enviar_notificaciones_alerta(nueva_alerta)


            return {"success": True, "data": nueva_alerta}, 201

        except ValidationError as err:
            return {"success": False, "errors": err.messages}, 400
        except Exception as e:
            logger.error(f"Error al crear alerta de riesgo: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def _procesar_efectos_secundarios_alerta(self, alerta, afectados, motivo_log, usuario_id):
        from app.controllers.inventario_controller import InventarioController
        from app.controllers.lote_producto_controller import LoteProductoController
        from app.controllers.orden_produccion_controller import OrdenProduccionController
        from app.models.inventario import InventarioModel
        inventario_model= InventarioModel()
        inventario_controller = InventarioController()
        lote_producto_controller = LoteProductoController()
        op_controller = OrdenProduccionController()
        
        logger.info(f"Procesando efectos para {len(afectados)} afectados. Motivo: {motivo_log}")

        for afectado in afectados:
            tipo = afectado['tipo_entidad']
            entidad_id = afectado['id_entidad']
            logger.info(f"Procesando: tipo={tipo}, id={entidad_id}")

            # 1. Marcar todas las entidades como 'en_alerta'
            self.alerta_riesgo_model._actualizar_flag_en_alerta_entidad(tipo, entidad_id, True)

            # 2. Poner lotes en cuarentena
            if tipo == 'lote_insumo':
                lote_info_res = inventario_model.find_by_id(entidad_id, id_field='id_lote')
                if lote_info_res.get('success') and lote_info_res.get('data') and len(lote_info_res.get('data')) > 0:
                    lote_info = lote_info_res.get('data')
                    if lote_info.get('cantidad_disponible', 0) <= 0:
                        logger.info(f"Lote de insumo {entidad_id} está agotado. Marcando como resuelto.")
                        self.alerta_riesgo_model.actualizar_estado_afectados(
                            alerta['id'], 
                            [entidad_id], 
                            'agotado', 
                            'lote_insumo', 
                            usuario_id
                        )
                    else:
                        inventario_controller.poner_lote_en_cuarentena(entidad_id, motivo_log, 999999, usuario_id)
                else:
                     inventario_controller.poner_lote_en_cuarentena(entidad_id, motivo_log, 999999, usuario_id)
            elif tipo == 'lote_producto':
                lote_producto_controller.poner_lote_en_cuarentena(entidad_id, motivo_log, 999999)


        
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
            
            afectados = self.trazabilidad_model.obtener_afectados_para_alerta(tipo_entidad, id_entidad)
            
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
            estado_map = {f"{a['tipo_entidad']}-{a['id_entidad']}": (a['estado'], a.get('resolucion_aplicada')) for a in afectados_con_estado}
            
            map_plural_a_singular = {
                'lotes_insumo': 'lote_insumo',
                'ordenes_produccion': 'orden_produccion',
                'lotes_producto': 'lote_producto',
                'pedidos': 'pedido'
            }

            for tipo_entidad_plural, lista_entidades in afectados_detalle.items():
                tipo_entidad_singular = map_plural_a_singular.get(tipo_entidad_plural)
                if not tipo_entidad_singular:
                    logger.warning(f"No se encontró mapeo para el tipo de entidad plural: {tipo_entidad_plural}")
                    continue

                id_field = 'id_lote' if 'lote' in tipo_entidad_singular else 'id'

                for entidad in lista_entidades:
                    entidad_id = entidad.get(id_field)
                    if not entidad_id:
                        continue
                        
                    key = f"{tipo_entidad_singular}-{entidad_id}"
                    estado, resolucion = estado_map.get(key, ('pendiente', None))
                    entidad['estado_resolucion'] = estado
                    entidad['resolucion_aplicada'] = resolucion

            alerta['afectados_detalle'] = afectados_detalle

            # --- INICIO: Calcular porcentajes de afectación para pedidos ---
            if 'pedidos' in afectados_detalle:
                from app.controllers.pedido_controller import PedidoController
                pedido_controller = PedidoController()
                afectados_trazabilidad_completa = self.trazabilidad_model.obtener_afectados_para_alerta(
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
                        # Lógica para el botón de resolución masiva
            
            hay_no_aptos = any(
                afectado.get('resolucion_aplicada') == 'no_apto'
                for afectado in afectados_con_estado if afectado.get('estado') == 'resuelto'
            )

            # Lógica mejorada para el botón de resolución masiva
            entidades_no_pedidos = [
                a for a in afectados_con_estado if a.get('tipo_entidad') != 'pedido'
            ]
            
            todos_no_pedidos_resueltos = all(
                a.get('estado') == 'resuelto' for a in entidades_no_pedidos
            )

            alerta['puede_resolver_pedidos_masivamente'] = todos_no_pedidos_resueltos and not hay_no_aptos

            return {"success": True, "data": alerta}, 200
        
        except Exception as e:
            logger.error(f"Error al obtener detalle completo de alerta {codigo_alerta}: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def ejecutar_accion_riesgo(self, codigo_alerta, form_data, usuario_id):
        accion = form_data.get("accion")
        acciones = {
            "nota_credito": self._ejecutar_nota_de_credito,
            "inhabilitar_pedido": self._ejecutar_inhabilitar_pedidos,
            "inhabilitar_pedido": self._ejecutar_inhabilitar_pedidos,
            "resolver_pedidos": self._ejecutar_resolver_pedidos
        }

        if accion in acciones:
            # Todas las funciones de ejecución ahora devuelven un tuple (dict, status_code)
            return acciones[accion](codigo_alerta, form_data, usuario_id)
        
        return ({"success": False, "error": "Acción no válida."}, 400)
        

    def _ejecutar_resolver_pedidos(self, codigo_alerta, form_data, usuario_id):
        """
        Marca todos los pedidos pendientes de una alerta como resueltos.
        Esta acción solo debe ser posible si no hay lotes 'no aptos'.
        """
        try:
            alerta_res = self.alerta_riesgo_model.find_all({'codigo': codigo_alerta}, limit=1)
            if not alerta_res.get('data'): return ({"success": False, "error": "Alerta no encontrada."}, 404)
            alerta = alerta_res.get('data')[0]

            afectados_pendientes = self.alerta_riesgo_model.db.table('alerta_riesgo_afectados').select('id_entidad').eq('alerta_id', alerta['id']).eq('tipo_entidad', 'pedido').eq('estado', 'pendiente').execute().data
            
            if not afectados_pendientes:
                return ({"success": True, "message": "No había pedidos pendientes para resolver."}, 200)

            pedido_ids_a_resolver = [p['id_entidad'] for p in afectados_pendientes]

            self.alerta_riesgo_model.actualizar_estado_afectados(
                alerta['id'], 
                pedido_ids_a_resolver, 
                'resuelto_automaticamente', 
                'pedido', 
                usuario_id
            )

            return ({"success": True, "message": f"Se marcaron {len(pedido_ids_a_resolver)} pedidos como resueltos."}, 200)

        except Exception as e:
            logger.error(f"Error en _ejecutar_resolver_pedidos: {e}", exc_info=True)
            return ({"success": False, "error": "Error interno al resolver pedidos."}, 500)
        
    def _ejecutar_nota_de_credito(self, codigo_alerta, form_data, usuario_id):
        pedidos_seleccionados = form_data.getlist("pedido_ids")
        recrear_pedido = form_data.get("recrear_pedido") == "on"
        if not pedidos_seleccionados:
            return ({"success": False, "error": "No se seleccionaron pedidos."}, 400)

        try:
            alerta_res = self.alerta_riesgo_model.find_all({'codigo': codigo_alerta}, limit=1)
            if not alerta_res.get('data'): return ({"success": False, "error": "Alerta no encontrada."}, 404)
            alerta = alerta_res.get('data')[0]

            # Validar si alguno de los lotes de producto sigue en cuarentena
            lotes_en_cuarentena = self.alerta_riesgo_model.db.table('lotes_productos').select('id_lote').in_('id_lote', lotes_producto_afectados_ids).eq('estado', 'CUARENTENA').execute().data
            if lotes_en_cuarentena:
                return ({"success": False, "error": "No se puede resolver el pedido. Uno o más lotes de producto asociados todavía están en cuarentena."}, 400)

            afectados_completo = self.trazabilidad_model.obtener_afectados_para_alerta(
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

            # Validar si alguno de los lotes de producto sigue en cuarentena
            afectados_completo = self.trazabilidad_model.obtener_afectados_para_alerta(alerta['origen_tipo_entidad'], alerta['origen_id_entidad'])
            lotes_producto_afectados_ids = [a['id_entidad'] for a in afectados_completo if a['tipo_entidad'] == 'lote_producto']
            lotes_en_cuarentena = self.alerta_riesgo_model.db.table('lotes_productos').select('id_lote').in_('id_lote', lotes_producto_afectados_ids).eq('estado', 'CUARENTENA').execute().data
            if lotes_en_cuarentena:
                return ({"success": False, "error": "No se puede inhabilitar el pedido. Uno o más lotes de producto asociados todavía están en cuarentena."}, 400)
            
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

    def _enviar_notificaciones_alerta(self, nueva_alerta):
        try:
            codigo_alerta = nueva_alerta.get('codigo')
            base_url = os.getenv("APP_BASE_URL", "http://localhost:5000")
            url_alerta = f"{base_url}/administrar/riesgos/{codigo_alerta}/detalle"
            
            mensaje = (
                f"<b>Nueva Alerta de Riesgo Creada</b>\n\n"
                f"<b>Código:</b> {codigo_alerta}\n"
                f"<b>Motivo:</b> {nueva_alerta.get('motivo')}\n"
                f"<b>Origen:</b> {nueva_alerta.get('origen_tipo_entidad')} ID: {nueva_alerta.get('origen_id_entidad')}\n\n"
                f"Puede ver los detalles en el siguiente enlace:\n"
                f"<a href='{url_alerta}'>Ver Alerta</a>"
            )
            asunto = f"Nueva Alerta de Riesgo Creada: {codigo_alerta}"

            # Enviar por Email al supervisor de calidad
            rol_model = RoleModel()
            rol_calidad_res = rol_model.find_by_codigo('CALIDAD')
            if not rol_calidad_res.get('success'):
                logger.error("No se encontró el rol 'CALIDAD' para enviar notificaciones por email.")
                return

            rol_calidad = rol_calidad_res.get('data')
            
            usuario_model = UsuarioModel()
            usuarios_calidad_res = usuario_model.find_all({'role_id': rol_calidad['id']})
            
            if not usuarios_calidad_res.get('success') or not usuarios_calidad_res.get('data'):
                logger.warning("No se encontraron usuarios con el rol 'CALIDAD' para notificar.")
                return

            for usuario in usuarios_calidad_res.get('data'):
                email_destinatario = usuario.get('email')
                if email_destinatario:
                    try:
                        send_email(email_destinatario, asunto, mensaje, is_html=True)
                        logger.info(f"Notificación de alerta {codigo_alerta} enviada a {email_destinatario}")
                    except Exception as e:
                        logger.error(f"No se pudo enviar email de notificación a {email_destinatario}: {e}")

        except Exception as e:
            logger.error(f"Error general en _enviar_notificaciones_alerta para {nueva_alerta.get('codigo')}: {e}", exc_info=True)

    def resolver_alerta_manualmente(self, codigo_alerta, usuario_id):
        try:
            alerta_res = self.alerta_riesgo_model.find_all({'codigo': codigo_alerta}, limit=1)
            if not alerta_res.get('success') or not alerta_res.get('data'):
                return {"success": False, "error": "Alerta no encontrada."}, 404
            alerta = alerta_res.get('data')[0]

            if alerta['estado'] != 'Pendiente':
                return {"success": False, "error": f"La alerta ya está en estado '{alerta['estado']}'."}, 400

            # Cambiar el estado principal de la alerta
            self.alerta_riesgo_model.update(alerta['id'], {'estado': 'Resuelta'})
            
            # Marcar todos los afectados como resueltos si aún están pendientes
            self.alerta_riesgo_model.db.table('alerta_riesgo_afectados').update({
                'estado': 'resuelto',
                'resolucion_aplicada': 'resuelta_manualmente',
                'id_usuario_resolucion': usuario_id
            }).eq('alerta_id', alerta['id']).eq('estado', 'pendiente').execute()

            # Quitar el flag 'en_alerta' de todas las entidades afectadas
            afectados = self.alerta_riesgo_model.obtener_afectados(alerta['id'])
            for afectado in afectados:
                sigue_en_alerta = self.alerta_riesgo_model.entidad_esta_en_otras_alertas_activas(
                    afectado['tipo_entidad'], 
                    afectado['id_entidad'],
                    alerta['id']
                )
                if not sigue_en_alerta:
                    self.alerta_riesgo_model._actualizar_flag_en_alerta_entidad(afectado['tipo_entidad'], afectado['id_entidad'], False)

            return {"success": True, "message": "La alerta ha sido marcada como resuelta manualmente."}, 200

        except Exception as e:
            logger.error(f"Error al resolver alerta manualmente: {e}", exc_info=True)
            return {"success": False, "error": "Error interno del servidor."}, 500