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
            motivo = datos_json.get("motivo")
            comentarios = datos_json.get("comentarios")
            url_evidencia = datos_json.get("url_evidencia")

            if not tipo_entidad or not id_entidad or not motivo:
                return {"success": False, "error": "tipo_entidad, id_entidad y motivo son requeridos."}, 400

            if tipo_entidad == 'orden_compra':
                from app.models.orden_compra_model import OrdenCompraModel
                oc_model = OrdenCompraModel()
                oc_res = oc_model.find_by_id(id_entidad)
                if oc_res.get('success') and oc_res.get('data'):
                    oc = oc_res['data']
                    if oc.get('estado', '').lower() in ['pendiente', 'aprobada', 'en espera llegada', 'completada', 'en transito', 'en recepcion']:
                        oc_model.update(id_entidad, {'estado': 'CANCELADA'})
                        nueva_alerta = self._crear_alerta_base(datos_json, usuario_id)
                        if not nueva_alerta:
                             return {"success": False, "error": "No se pudo crear la alerta base para la OC."}, 500

                        self.alerta_riesgo_model.update(nueva_alerta['id'], {
                            'estado': 'ANALISIS FINALIZADO',
                            'conclusion_final': 'Alerta resuelta automáticamente. La OC de origen fue cancelada antes del ingreso de la mercadería.'
                        })
                        return {"success": True, "data": nueva_alerta, "message": "La Orden de Compra fue cancelada y la alerta resuelta automáticamente."}, 201

            afectados = self.trazabilidad_model.obtener_afectados_para_alerta(tipo_entidad, id_entidad)
            nueva_alerta = self._crear_alerta_base(datos_json, usuario_id)
            if not nueva_alerta:
                 return {"success": False, "error": "No se pudo crear la alerta base."}, 500

            if afectados:
                estados_previos = self._obtener_estados_actuales(afectados)
                self.alerta_riesgo_model.asociar_afectados(nueva_alerta['id'], afectados, estados_previos)
                self._procesar_efectos_secundarios_alerta(nueva_alerta, afectados, estados_previos, f"Alerta {nueva_alerta['codigo']}", usuario_id)

            self._enviar_notificaciones_alerta(nueva_alerta)
            return {"success": True, "data": nueva_alerta}, 201

        except ValidationError as err:
            return {"success": False, "errors": err.messages}, 400
        except Exception as e:
            logger.error(f"Error al crear alerta de riesgo: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def _crear_alerta_base(self, datos_json, usuario_id):
        count_res = self.alerta_riesgo_model.db.table(self.alerta_riesgo_model.get_table_name()).select('count', count='exact').execute()
        count = count_res.count or 0
        nueva_alerta_data = {
            "origen_tipo_entidad": datos_json.get("tipo_entidad"), "origen_id_entidad": str(datos_json.get("id_entidad")),
            "estado": "Pendiente", "codigo": f"ALR-{count + 1}", "motivo": datos_json.get("motivo"),
            "comentarios": datos_json.get("comentarios"), "url_evidencia": datos_json.get("url_evidencia"), "id_usuario_creador": usuario_id
        }
        resultado_alerta = self.alerta_riesgo_model.create(nueva_alerta_data)
        if not resultado_alerta.get("success"): return None
        nueva_alerta = resultado_alerta.get("data")
        return nueva_alerta[0] if isinstance(nueva_alerta, list) else nueva_alerta

    def _obtener_estados_actuales(self, afectados: list) -> dict:
        estados = {}
        from app.models.inventario import InventarioModel
        from app.models.lote_producto import LoteProductoModel
        from app.models.orden_produccion import OrdenProduccionModel
        from app.models.pedido import PedidoModel
        models = {'lote_insumo': (InventarioModel(), 'id_lote'), 'lote_producto': (LoteProductoModel(), 'id_lote'),
                  'orden_produccion': (OrdenProduccionModel(), 'id'), 'pedido': (PedidoModel(), 'id')}
        for afectado in afectados:
            tipo, entidad_id = afectado['tipo_entidad'], afectado['id_entidad']
            if tipo in models:
                model, id_field = models[tipo]
                try:
                    res = model.find_by_id(int(entidad_id) if id_field == 'id' else entidad_id, id_field=id_field)
                    if res.get('success') and res.get('data'):
                        estados[(tipo, str(entidad_id))] = res['data'].get('estado', 'Desconocido')
                except Exception as e:
                    logger.error(f"No se pudo obtener el estado para {tipo}:{entidad_id}. Error: {e}")
        return estados

    def _procesar_efectos_secundarios_alerta(self, alerta, afectados, estados_previos, motivo_log, usuario_id):
        from app.controllers.inventario_controller import InventarioController
        from app.controllers.lote_producto_controller import LoteProductoController
        from app.controllers.orden_produccion_controller import OrdenProduccionController
        from app.controllers.pedido_controller import PedidoController
        controllers = {'lote_insumo': InventarioController(), 'lote_producto': LoteProductoController(),
                       'orden_produccion': OrdenProduccionController(), 'pedido': PedidoController()}
        ESTADOS_AFECTADOS = {
            'lote_insumo': ['disponible', 'agotado', 'reservado', 'vencido'], 'lote_producto': ['disponible', 'reservado', 'agotado', 'vencido'],
            'orden_produccion': ['en proceso', 'completada', 'lista para producir', 'en linea 1', 'en linea 2', 'en empaquetado', 'en control de calidad'],
            'pedido': ['en proceso', 'listo para entrega', 'en transito']
        }
        for afectado in afectados:
            tipo, entidad_id = afectado['tipo_entidad'], afectado['id_entidad']
            estado_actual = estados_previos.get((tipo, str(entidad_id)), '').lower()
            
            # Modificación: Si es insumo agotado pero afectado, forzamos la cuarentena para revisión
            if tipo == 'lote_insumo' and 'agotado' in estado_actual:
                pass # Se procesará abajo aunque esté agotado
            elif not any(s in estado_actual for s in ESTADOS_AFECTADOS.get(tipo, [])):
                continue

            self.alerta_riesgo_model._actualizar_flag_en_alerta_entidad(tipo, entidad_id, True)
            try:
                if tipo == 'lote_insumo':
                    # Si está agotado, poner cantidad 0 en cuarentena solo para marcar el estado
                    cantidad_a_cuarentena = 999999
                    if 'agotado' in estado_actual:
                        cantidad_a_cuarentena = 0 
                    
                    controllers[tipo].poner_lote_en_cuarentena(
                        lote_id=entidad_id, 
                        motivo=motivo_log, 
                        cantidad=cantidad_a_cuarentena, 
                        usuario_id=usuario_id,
                        resultado_inspeccion="Pendiente de revisión (Automático por Alerta)",
                        foto_file=None
                    )
                elif tipo == 'lote_producto':
                    controllers[tipo].poner_lote_en_cuarentena(
                        lote_id=entidad_id, 
                        motivo=motivo_log, 
                        cantidad=999999, 
                        usuario_id=None, # LoteProductoController no usa usuario_id en args posicionales, pero verificamos firma
                        resultado_inspeccion="Pendiente de revisión (Automático por Alerta)",
                        foto_file=None
                    )
                elif tipo == 'orden_produccion':
                    controllers[tipo].cambiar_estado_orden_simple(int(entidad_id), 'EN ESPERA')
                elif tipo == 'pedido':
                    controllers[tipo].cambiar_estado_pedido(int(entidad_id), 'EN REVISION')
            except Exception as e:
                logger.error(f"Fallo al procesar efecto secundario para {tipo}:{entidad_id}. Error: {e}", exc_info=True)


        
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
            alerta['creador_info'] = usuario_controller.obtener_detalles_completos_usuario(creador_id) if creador_id else None
            
            afectados_con_estado = self.alerta_riesgo_model.obtener_afectados_con_estado(alerta['id'])
            # --- INICIO: Enriquecimiento de datos ---
            ids_por_tipo = {tipo: [a['id_entidad'] for a in afectados_con_estado if a['tipo_entidad'] == tipo] for tipo in set(a['tipo_entidad'] for a in afectados_con_estado)}

            detalles_enriquecidos = {}
            if ids_por_tipo.get('lote_insumo'):
                insumos_res = self.alerta_riesgo_model.db.table('insumos_inventario').select('id_lote, numero_lote_proveedor, f_ingreso, f_vencimiento, cantidad_en_cuarentena, insumos_catalogo:id_insumo(nombre), proveedores:id_proveedor(nombre)').in_('id_lote', list(set(ids_por_tipo['lote_insumo']))).execute().data
                detalles_enriquecidos['lote_insumo'] = {str(i['id_lote']): i for i in insumos_res}

            if ids_por_tipo.get('orden_produccion'):
                ops_res = self.alerta_riesgo_model.db.table('ordenes_produccion').select('id, codigo, cantidad_planificada, estado, productos(nombre)').in_('id', [int(i) for i in set(ids_por_tipo['orden_produccion'])]).execute().data                
                detalles_enriquecidos['orden_produccion'] = {i['id']: i for i in ops_res}

            if ids_por_tipo.get('lote_producto'):
                lotes_res = self.alerta_riesgo_model.db.table('lotes_productos').select('id_lote, numero_lote, estado, cantidad_en_cuarentena,fecha_produccion, fecha_vencimiento, productos(nombre)').in_('id_lote', [int(i) for i in set(ids_por_tipo['lote_producto'])]).execute().data
                detalles_enriquecidos['lote_producto'] = {i['id_lote']: i for i in lotes_res}
            
            participantes = {}
            for afectado in afectados_con_estado:
                resolutor_id = afectado.get('id_usuario_resolucion')
                if resolutor_id and afectado.get('estado') == 'resuelto':
                    if resolutor_id not in participantes:
                        participantes[resolutor_id] = {'info': usuario_controller.obtener_detalles_completos_usuario(resolutor_id), 'acciones': []}
                    
                    accion_desc = f"{afectado.get('resolucion_aplicada', 'Acción desconocida').replace('_', ' ').title()} sobre {afectado.get('tipo_entidad', '').replace('_', ' ')} #{afectado.get('id_entidad')}"
                    participantes[resolutor_id]['acciones'].append(accion_desc)
            
            alerta['participantes_resolucion'] = list(participantes.values())
            # --- Fin del procesamiento de participantes ---
            
            # Obtener los detalles completos (código, nombre, etc.)
            afectados_detalle = self.alerta_riesgo_model.obtener_afectados_detalle_para_previsualizacion(afectados_con_estado)
            map_plural_a_singular = {'lotes_insumo': 'lote_insumo', 'ordenes_produccion': 'orden_produccion', 'lotes_producto': 'lote_producto', 'pedidos': 'pedido'}
            for tipo_plural, entidades in afectados_detalle.items():
                tipo_singular = map_plural_a_singular.get(tipo_plural)
                if not tipo_singular: continue
                id_field = 'id_lote' if 'lote' in tipo_singular else 'id'
                for entidad in entidades:
                    entidad_id = entidad.get(id_field)
                    if detalles_enriquecidos.get(tipo_singular, {}).get(entidad_id):
                        entidad.update(detalles_enriquecidos[tipo_singular][entidad_id])
             # --- INICIO: Enriquecer TODAS las entidades con detalles de resolución ---
            map_plural_a_singular = {'lotes_insumo': 'lote_insumo', 'ordenes_produccion': 'orden_produccion', 'lotes_producto': 'lote_producto', 'pedidos': 'pedido'}
            map_singular_a_plural = {v: k for k, v in map_plural_a_singular.items()}
            id_field_map = {
                'lote_insumo': 'id_lote',
                'orden_produccion': 'id',
                'lote_producto': 'id_lote',
                'pedido': 'id'
            }

            for afectado in afectados_con_estado:
                tipo_singular = afectado.get('tipo_entidad')
                if not tipo_singular: continue

                tipo_plural = map_singular_a_plural.get(tipo_singular)
                id_field = id_field_map.get(tipo_singular)
                
                if not tipo_plural or not id_field or not afectados_detalle.get(tipo_plural): continue

                entidad_id_str = afectado.get('id_entidad')
                
                try:
                    # El ID de la entidad en `afectados_detalle` puede ser int o str. Hay que comparar con el tipo correcto.
                    # Hacemos una comparación flexible.
                    entidad_en_detalle = next((e for e in afectados_detalle.get(tipo_plural, []) if str(e.get(id_field)) == str(entidad_id_str)), None)
                except (ValueError, TypeError):
                    logger.warning(f"No se pudo comparar el ID {entidad_id_str} para {tipo_singular}")
                    continue

                if not entidad_en_detalle: continue

                # Enriquecer la entidad
                entidad_en_detalle['estado_resolucion'] = afectado.get('estado', 'pendiente')
                entidad_en_detalle['resolucion_aplicada'] = afectado.get('resolucion_aplicada')
                
                if afectado.get('id_usuario_resolucion'):
                     entidad_en_detalle['resolutor_info'] = usuario_controller.obtener_detalles_completos_usuario(afectado['id_usuario_resolucion'])
                
                # Caso especial para notas de crédito en pedidos
                if tipo_singular == 'pedido' and afectado.get('resolucion_aplicada') == 'nota_credito' and afectado.get('id_documento_relacionado'):
                    from app.controllers.nota_credito_controller import NotaCreditoController
                    nc_controller = NotaCreditoController()
                    nc_res, _ = nc_controller.obtener_detalles_para_pdf(afectado['id_documento_relacionado'])
                    if nc_res.get('success'):
                        entidad_en_detalle['nota_credito'] = nc_res['data']

            if 'pedidos' in afectados_detalle:
                from app.controllers.pedido_controller import PedidoController
                pedido_controller = PedidoController()
                afectados_trazabilidad_completa = self.trazabilidad_model.obtener_afectados_para_alerta(alerta['origen_tipo_entidad'], alerta['origen_id_entidad'])
                lotes_producto_afectados_ids = {str(a['id_entidad']) for a in afectados_trazabilidad_completa if a['tipo_entidad'] == 'lote_producto'}


                for pedido in afectados_detalle['pedidos']:
                   
                    res_pedido, _ = pedido_controller.obtener_pedido_por_id(pedido['id'])
                    if not res_pedido.get('success'):
                        pedido.update({'afectacion_items_str': "Error", 'afectacion_valor_str': "Error"})
                        continue
                    
                    # Fusionar los datos completos del pedido (incluyendo el cliente) en el diccionario existente
                    pedido_completo = res_pedido.get('data', {})
                    pedido.update(pedido_completo)

                    items_pedido = pedido_completo.get('items', [])
                    total_items = len(items_pedido)
                    total_valor = sum(float(i.get('producto_nombre', {}).get('precio_unitario', 0)) * float(i.get('cantidad', 0)) for i in items_pedido)
                    
                    items_afectados_count = 0
                    valor_afectado = 0.0
                        
                    from app.models.pedido import PedidoModel
                    pedido_model = PedidoModel()

                    for item in items_pedido:
                        reservas = pedido_model.get_reservas_for_item(item['id'])
                        if any(str(r.get('lote_producto_id')) in lotes_producto_afectados_ids for r in reservas):
                            items_afectados_count += 1
                            valor_afectado += float(item.get('producto_nombre', {}).get('precio_unitario', 0)) * float(item.get('cantidad', 0))
                    
                    pedido['afectacion_items_str'] = f"{items_afectados_count} de {total_items}"
                    pedido['afectacion_valor_str'] = f"{round((valor_afectado / total_valor) * 100)}%" if total_valor > 0 else "0%"
            
            alerta['afectados_detalle'] = afectados_detalle
            # --- FIN: Calcular porcentajes de afectación para pedidos ---

            if alerta['estado'] in ['Resuelta', 'Cerrada']:
                ncs_asociadas_res = self.nota_credito_controller.obtener_detalle_nc_por_alerta(alerta['id'])
                alerta['notas_de_credito'] = ncs_asociadas_res.get('data', [])
                        # Lógica para el botón de resolución masiva
            hay_no_aptos = any(a.get('resolucion_aplicada') == 'no_apto' for a in afectados_con_estado if a.get('estado') == 'resuelto')
            todos_no_pedidos_resueltos = all(a.get('estado') == 'resuelto' for a in afectados_con_estado if a.get('tipo_entidad') != 'pedido')
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

            # Corregido: Primero obtener los lotes afectados, luego validar.
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
            self.alerta_riesgo_model.update(alerta['id'], {'estado': 'ANALISIS FINALIZADO', 'conclusion_final': 'Resolución manual aplicada por el administrador.'})
            
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
    
    
    def resolver_cuarentena_lote_desde_alerta(self, datos, usuario_id):
        lote_id = datos.get('lote_id')
        tipo_lote = datos.get('tipo_lote')
        resolucion = datos.get('resolucion')
        alerta_id = datos.get('alerta_id')

        if not all([lote_id, tipo_lote, resolucion, alerta_id]):
            return {"success": False, "error": "Faltan parámetros requeridos (lote_id, tipo_lote, resolucion, alerta_id)."}, 400

        try:
            if tipo_lote == 'lote_insumo':
                if resolucion.lower() == 'apto':
                    return self._resolver_lote_insumo_apto(alerta_id, lote_id, usuario_id)
                else:
                    return self._resolver_lote_insumo_no_apto(alerta_id, lote_id, usuario_id)
            elif tipo_lote == 'lote_producto':
                if resolucion.lower() == 'apto':
                    return self._resolver_lote_producto_apto(alerta_id, lote_id, usuario_id)
                else:
                    return self._resolver_lote_producto_no_apto(alerta_id, lote_id, usuario_id)
            else:
                return {"success": False, "error": "Tipo de lote no válido."}, 400

        except Exception as e:
            logger.error(f"Error en resolver_cuarentena_lote_desde_alerta: {e}", exc_info=True)
            return {"success": False, "error": "Error interno del servidor."}, 500

    def _resolver_lote_insumo_apto(self, alerta_id, lote_insumo_id, usuario_id):
        from app.controllers.inventario_controller import InventarioController
        inventario_controller = InventarioController()

        inventario_controller.liberar_lote_de_cuarentena_alerta(lote_insumo_id, usuario_id)
        self.alerta_riesgo_model.registrar_resolucion_afectado(alerta_id, 'lote_insumo', lote_insumo_id, 'resuelto', 'Apto', usuario_id)
        
        self.alerta_riesgo_model.verificar_y_cerrar_alerta(alerta_id)
        return {"success": True, "message": "Lote de insumo marcado como Apto. Se revisarán las entidades dependientes."}, 200


    def _resolver_lote_insumo_no_apto(self, alerta_id, lote_insumo_id, usuario_id):
        from app.controllers.inventario_controller import InventarioController
        from app.controllers.orden_produccion_controller import OrdenProduccionController

        inventario_controller = InventarioController()
        op_controller = OrdenProduccionController()

        inventario_controller.marcar_lote_retirado_alerta(lote_insumo_id, usuario_id)
        self.alerta_riesgo_model.registrar_resolucion_afectado(alerta_id, 'lote_insumo', lote_insumo_id, 'resuelto', 'No Apto (Retirado)', usuario_id)

        afectados_downstream_res = self.trazabilidad_model.obtener_trazabilidad_unificada('lote_insumo', lote_insumo_id, nivel='completo')
        
        afectados_downstream = self._transformar_trazabilidad_a_diccionario(afectados_downstream_res)
        
        for op_data in afectados_downstream.get('ordenes_produccion', []):
            op_controller.cambiar_estado_a_pendiente_con_reemplazo(op_data['id'])
            self.alerta_riesgo_model.registrar_resolucion_afectado(alerta_id, 'orden_produccion', op_data['id'], 'resuelto', 'Pendiente por insumo no apto', usuario_id)

        for lp_data in afectados_downstream.get('lotes_productos', []):
            self._resolver_lote_producto_no_apto(alerta_id, lp_data['id'], usuario_id, motivo_adicional=f"originado por insumo no apto {lote_insumo_id}")
        
        self.alerta_riesgo_model.verificar_y_cerrar_alerta(alerta_id)
        return {"success": True, "message": "Lote de insumo marcado como No Apto y entidades dependientes actualizadas."}, 200

    def _resolver_lote_producto_apto(self, alerta_id, lote_producto_id, usuario_id):
        from app.controllers.lote_producto_controller import LoteProductoController
        lote_producto_controller = LoteProductoController()
        
        lote_producto_controller.liberar_lote_de_cuarentena_alerta(lote_producto_id)
        self.alerta_riesgo_model.registrar_resolucion_afectado(alerta_id, 'lote_producto', lote_producto_id, 'resuelto', 'Apto', usuario_id)
        
        self.alerta_riesgo_model.verificar_y_cerrar_alerta(alerta_id)
        
        return {"success": True, "message": "Lote de producto marcado como Apto."}, 200

    def _resolver_lote_producto_no_apto(self, alerta_id, lote_producto_id, usuario_id, motivo_adicional=""):
        from app.controllers.lote_producto_controller import LoteProductoController
        from app.controllers.pedido_controller import PedidoController
        from app.models.lote_producto import LoteProductoModel
        
        lote_producto_controller = LoteProductoController()
        pedido_controller = PedidoController()
        lote_producto_model = LoteProductoModel()

        lote_producto_controller.marcar_lote_retirado_alerta(lote_producto_id)
        self.alerta_riesgo_model.registrar_resolucion_afectado(alerta_id, 'lote_producto', lote_producto_id, 'resuelto', f'No Apto (Retirado) {motivo_adicional}'.strip(), usuario_id)
        
        afectados_downstream_res = self.trazabilidad_model.obtener_trazabilidad_unificada('lote_producto', lote_producto_id, nivel='completo')
        
        afectados_downstream = self._transformar_trazabilidad_a_diccionario(afectados_downstream_res)
        
        pedidos_afectados = afectados_downstream.get('pedidos', [])
        if pedidos_afectados:
            lote_producto_model.update(lote_producto_id, {'estado': 'DEVOLUCION_PENDIENTE'}, 'id_lote')
            for pedido_data in pedidos_afectados:
                pedido_id = int(pedido_data['id'])
                pedido_actual_res, _ = pedido_controller.obtener_pedido_por_id(pedido_id)
                if not pedido_actual_res.get('success'): continue

                estado_actual = pedido_actual_res.get('data', {}).get('estado', '').lower()
                
                if estado_actual in ['recibido', 'completado']:
                    pedido_controller.cambiar_estado_pedido(pedido_id, 'en_transito')
        else:
            # Si no hay pedidos, se retira directamente
            lote_producto_controller.marcar_lote_retirado_alerta(lote_producto_id)

        self.alerta_riesgo_model.verificar_y_cerrar_alerta(alerta_id)
        return {"success": True, "message": "Lote de producto marcado como No Apto y pedidos afectados actualizados."}, 200

    def ejecutar_accion_riesgo_api(self, alerta_id: int, accion: str, data: dict, usuario_id: int):
        acciones = {'resolver_lote': self._ejecutar_resolucion_lote, 'finalizar_analisis': self._ejecutar_finalizar_analisis}
        handler = acciones.get(accion)
        if not handler:
            return {'success': False, 'message': f"Acción desconocida: {accion}"}, 400
        try:
            return handler(alerta_id, data, usuario_id)
        except Exception as e:
            logger.error(f"Error ejecutando la acción '{accion}' para la alerta {alerta_id}: {e}", exc_info=True)
            return {'success': False, 'message': "Error interno del servidor al procesar la acción."}, 500

    def _ejecutar_resolucion_lote(self, alerta_id: int, data: dict, usuario_id: int):
        lote_id, tipo_lote, resolucion = data.get('lote_id'), data.get('tipo_lote'), data.get('resolucion')
        if not all([lote_id, tipo_lote, resolucion, alerta_id]):
            return {'success': False, 'message': "Faltan parámetros requeridos (lote_id, tipo_lote, resolucion, alerta_id)."}, 400

        from app.controllers.inventario_controller import InventarioController
        from app.controllers.lote_producto_controller import LoteProductoController
        
        if tipo_lote == 'lote_insumo':
            if resolucion == 'Apto':
                InventarioController().liberar_lote_de_cuarentena_alerta(lote_id, usuario_id)
                self._verificar_lotes_producto_asociados(lote_id, alerta_id, usuario_id)
            else: # No Apto
                InventarioController().marcar_lote_retirado_alerta(lote_id, usuario_id)
                self._actualizar_op_y_lotes_producto_por_insumo_no_apto(lote_id, alerta_id, usuario_id)
        elif tipo_lote == 'lote_producto':
            if resolucion == 'Apto':
                LoteProductoController().liberar_lote_de_cuarentena_alerta(lote_id)
            else: # No Apto
                LoteProductoController().marcar_lote_retirado_alerta(lote_id)
                self._gestionar_devolucion_pedidos_por_lote_producto(lote_id, alerta_id, usuario_id)
        
        self.alerta_riesgo_model.registrar_resolucion_afectado(alerta_id, tipo_lote, lote_id, 'resuelto', f"Marcado como '{resolucion}'", usuario_id)
        self.alerta_riesgo_model.verificar_y_cerrar_alerta(alerta_id)
        
        return {'success': True, 'message': f"Lote {lote_id} procesado como {resolucion}."}, 200

    def _transformar_trazabilidad_a_diccionario(self, trazabilidad_res):
        """
        Convierte la respuesta del nuevo método de trazabilidad a la estructura
        de diccionario anidado que esperaba el código anterior.
        """
        diccionario_afectados = {}
        if not trazabilidad_res or 'resumen' not in trazabilidad_res:
            return diccionario_afectados

        for item in trazabilidad_res['resumen'].get('destino', []):
            tipo = item.get('tipo')
            if not tipo: continue
            
            # Mapeo simple de singular a plural para las claves del diccionario
            map_plural = {
                'pedido': 'pedidos',
                'lote_insumo': 'lotes_insumo',
                'orden_produccion': 'ordenes_produccion',
                'lote_producto': 'lotes_productos'
            }
            tipo_plural = map_plural.get(tipo, f"{tipo}s")

            if tipo_plural not in diccionario_afectados:
                diccionario_afectados[tipo_plural] = []
            diccionario_afectados[tipo_plural].append(item)
            
        return diccionario_afectados

    def _verificar_lotes_producto_asociados(self, lote_insumo_id, alerta_id, usuario_id):
        from app.models.trazabilidad import TrazabilidadModel
        afectados_res = TrazabilidadModel().obtener_trazabilidad_unificada('lote_insumo', lote_insumo_id, nivel='completo')
        afectados_dicc = self._transformar_trazabilidad_a_diccionario(afectados_res)
        
        for lp in afectados_dicc.get('lotes_productos', []):
            self._ejecutar_resolucion_lote(alerta_id, {'lote_id': lp['id'], 'tipo_lote': 'lote_producto', 'resolucion': 'Apto'}, usuario_id)

    def _actualizar_op_y_lotes_producto_por_insumo_no_apto(self, lote_insumo_id, alerta_id, usuario_id):
        from app.models.trazabilidad import TrazabilidadModel
        from app.controllers.orden_produccion_controller import OrdenProduccionController
        afectados_res = TrazabilidadModel().obtener_trazabilidad_unificada('lote_insumo', lote_insumo_id, nivel='completo')
        afectados_dicc = self._transformar_trazabilidad_a_diccionario(afectados_res)

        for op_data in afectados_dicc.get('ordenes_produccion', []):
            OrdenProduccionController().cambiar_estado_a_pendiente_con_reemplazo(op_data['id'])
            self.alerta_riesgo_model.registrar_resolucion_afectado(alerta_id, 'orden_produccion', op_data['id'], 'resuelto', 'OP a pendiente por insumo no apto', usuario_id)

        for lp_data in afectados_dicc.get('lotes_productos', []):
            self._ejecutar_resolucion_lote(alerta_id, {'lote_id': lp_data['id'], 'tipo_lote': 'lote_producto', 'resolucion': 'No Apto'}, usuario_id)

    def _gestionar_devolucion_pedidos_por_lote_producto(self, lote_producto_id, alerta_id, usuario_id):
        from app.models.trazabilidad import TrazabilidadModel
        from app.controllers.pedido_controller import PedidoController
        from app.models.lote_producto import LoteProductoModel
        
        afectados_res = TrazabilidadModel().obtener_trazabilidad_unificada('lote_producto', lote_producto_id, nivel='completo')
        afectados_dicc = self._transformar_trazabilidad_a_diccionario(afectados_res)
        
        pedidos_afectados = afectados_dicc.get('pedidos', [])

        if pedidos_afectados:
            LoteProductoModel().update(lote_producto_id, {'estado': 'DEVOLUCION_PENDIENTE'}, 'id_lote')
            pedido_controller = PedidoController()
            for pedido_data in pedidos_afectados:
                pedido_id = int(pedido_data['id'])
                
                pedido_actual_res, _ = pedido_controller.obtener_pedido_por_id(pedido_id)
                if not pedido_actual_res.get('success'): continue

                estado_actual = pedido_actual_res.get('data', {}).get('estado', '').lower()
                
                if estado_actual in ['recibido', 'completado']:
                    pedido_controller.cambiar_estado_pedido(pedido_id, 'en_transito')

                self.alerta_riesgo_model.registrar_resolucion_afectado(alerta_id, 'pedido', pedido_id, 'resuelto', 'Devolución iniciada por lote producto no apto', usuario_id)
        else:
            from app.controllers.lote_producto_controller import LoteProductoController
            LoteProductoController().marcar_lote_retirado_alerta(lote_producto_id)

    def _ejecutar_finalizar_analisis(self, alerta_id: int, data: dict, usuario_id: int):
        conclusion = data.get('conclusion')
        if not conclusion:
            return {'success': False, 'message': 'La conclusión es obligatoria para finalizar el análisis.'}, 400
        
        self.alerta_riesgo_model.actualizar_alerta(alerta_id, {'estado': 'ANALISIS FINALIZADO', 'conclusion': conclusion})
        return {'success': True, 'message': 'La alerta ha sido marcada como finalizada.'}, 200

    def ejecutar_accion_riesgo_api(self, alerta_id: int, datos: dict, usuario_id: int):
        accion = datos.get('accion')
        data = datos.get('data', {})

        if not accion:
            return {"success": False, "error": "No se especificó una acción."}, 400

        acciones = {
            "resolver_lote": self._ejecutar_resolucion_lote_api,
            "recibir_devolucion": self._ejecutar_recibir_devolucion_api,
            "finalizar_analisis": self._ejecutar_finalizar_analisis_api,
            "nota_credito": self._ejecutar_nota_de_credito_api,
            "inhabilitar_pedido": self._ejecutar_inhabilitar_pedidos_api,
            "resolver_pedidos": self._ejecutar_resolver_pedidos_api,
            "resolver_op_individual": self._ejecutar_resolver_op_individual_api
        }

        handler = acciones.get(accion)

        if not handler:
            return {"success": False, "error": f"Acción '{accion}' no reconocida."}, 400

        try:
            return handler(alerta_id, data, usuario_id)
        except Exception as e:
            logger.error(f"Error al ejecutar la acción '{accion}' para la alerta {alerta_id}: {e}", exc_info=True)
            return {"success": False, "error": "Error interno del servidor al procesar la acción."}, 500

    def _ejecutar_resolucion_lote_api(self, alerta_id, data, usuario_id):
        # Extraer la decisión sobre OPs downstream
        accion_ops_downstream = data.get('accion_ops_downstream')
        # Pasarlo a la función legacy inyectando en 'data'
        data['alerta_id'] = alerta_id
        # El método legacy no espera 'accion_ops_downstream', así que mejor lo manejamos aquí si es No Apto
        resolucion = data.get('resolucion')
        
        if data.get('tipo_lote') == 'lote_insumo' and resolucion == 'No Apto' and accion_ops_downstream:
             # Lógica custom para este caso específico que reemplaza a _resolver_lote_insumo_no_apto estándar
             return self._resolver_lote_insumo_no_apto_custom(alerta_id, data.get('lote_id'), usuario_id, accion_ops_downstream)

        return self.resolver_cuarentena_lote_desde_alerta(data, usuario_id)

    def _resolver_lote_insumo_no_apto_custom(self, alerta_id, lote_insumo_id, usuario_id, accion_ops):
        from app.controllers.inventario_controller import InventarioController
        from app.controllers.orden_produccion_controller import OrdenProduccionController

        inventario_controller = InventarioController()
        op_controller = OrdenProduccionController()

        # 1. Retirar el insumo
        inventario_controller.marcar_lote_retirado_alerta(lote_insumo_id, usuario_id)
        self.alerta_riesgo_model.registrar_resolucion_afectado(alerta_id, 'lote_insumo', lote_insumo_id, 'resuelto', 'No Apto (Retirado)', usuario_id)

        # 2. Obtener afectados
        afectados_downstream_res = self.trazabilidad_model.obtener_trazabilidad_unificada('lote_insumo', lote_insumo_id, nivel='completo')
        afectados_downstream = self._transformar_trazabilidad_a_diccionario(afectados_downstream_res)
        
        # 3. Procesar OPs según la decisión del usuario
        ordenes_afectadas = afectados_downstream.get('ordenes_produccion', [])
        
        for op_data in ordenes_afectadas:
            op_id = op_data['id']
            if accion_ops == 'replanificar':
                # Lógica existente: Volver a pendiente y buscar reemplazo
                op_controller.cambiar_estado_a_pendiente_con_reemplazo(op_id)
                resolucion_texto = 'Pendiente por insumo no apto'
            else:
                # Dejar como está (solo se marca resuelto en la alerta)
                resolucion_texto = 'Mantenida (Insumo No Apto)'
            
            self.alerta_riesgo_model.registrar_resolucion_afectado(alerta_id, 'orden_produccion', op_id, 'resuelto', resolucion_texto, usuario_id)

        # 4. Procesar Lotes de Producto (Siempre se marcan No Aptos si el insumo es No Apto, por seguridad)
        # NOTA: Podríamos preguntar también, pero por defecto asumimos riesgo alto.
        for lp_data in afectados_downstream.get('lotes_productos', []):
            self._resolver_lote_producto_no_apto(alerta_id, lp_data['id'], usuario_id, motivo_adicional=f"originado por insumo no apto {lote_insumo_id}")
        
        self.alerta_riesgo_model.verificar_y_cerrar_alerta(alerta_id)
        return {"success": True, "message": "Lote de insumo retirado y OPs procesadas según selección."}, 200

    def _ejecutar_resolver_op_individual_api(self, alerta_id, data, usuario_id):
        op_id = data.get('op_id')
        sub_accion = data.get('sub_accion') # continuar, cancelar, replanificar
        motivo = data.get('motivo')

        if not all([op_id, sub_accion]):
            return {"success": False, "error": "Faltan datos (op_id, sub_accion)."}, 400

        from app.controllers.orden_produccion_controller import OrdenProduccionController
        op_controller = OrdenProduccionController()

        try:
            op_id = int(op_id)
            if sub_accion == 'continuar':
                # Restaurar estado previo si estaba pausada por alerta
                # Buscamos el estado previo en la tabla de afectados
                afectado = self.alerta_riesgo_model.db.table('alerta_riesgo_afectados').select('estado_previo').eq('alerta_id', alerta_id).eq('tipo_entidad', 'orden_produccion').eq('id_entidad', op_id).maybe_single().execute()
                
                estado_destino = 'EN_PROCESO' # Default seguro
                if afectado.data and afectado.data.get('estado_previo'):
                    estado_previo = afectado.data['estado_previo']
                    # Evitar volver a un estado que ya no tiene sentido o es el mismo de la alerta
                    if estado_previo not in ['PAUSADA', 'EN ESPERA', 'EN REVISION']:
                        estado_destino = estado_previo
                
                # Si estaba completada, no cambiamos el estado, solo resolvemos la alerta
                op_actual_res = op_controller.obtener_orden_por_id(op_id)
                if op_actual_res.get('success'):
                    estado_actual_op = op_actual_res['data'].get('estado')
                    if estado_actual_op != 'COMPLETADA':
                         op_controller.cambiar_estado_orden_simple(op_id, estado_destino)

                resolucion_texto = 'Continuada (Aprobada)'

            elif sub_accion == 'cancelar':
                op_controller.rechazar_orden(op_id, motivo or "Cancelada desde Alerta de Riesgo")
                resolucion_texto = 'Cancelada Definitivamente'

            elif sub_accion == 'replanificar':
                op_controller.cambiar_estado_orden_simple(op_id, 'PENDIENTE')
                # Opcional: Limpiar asignaciones previas si es necesario
                resolucion_texto = 'Replanificada (A Pendiente)'
            
            else:
                return {"success": False, "error": "Acción desconocida."}, 400

            # Marcar como resuelto en la alerta
            self.alerta_riesgo_model.registrar_resolucion_afectado(alerta_id, 'orden_produccion', op_id, 'resuelto', resolucion_texto, usuario_id)
            self.alerta_riesgo_model.verificar_y_cerrar_alerta(alerta_id)

            return {"success": True, "message": f"Orden procesada: {resolucion_texto}"}, 200

        except Exception as e:
            logger.error(f"Error en resolver_op_individual: {e}", exc_info=True)
            return {"success": False, "error": "Error interno al procesar la OP."}, 500

    def _ejecutar_finalizar_analisis_api(self, alerta_id, data, usuario_id):
        conclusion = data.get('conclusion')
        if not conclusion:
            return {"success": False, "error": "La conclusión es obligatoria."}, 400

        resultado = self.alerta_riesgo_model.update(alerta_id, {
            'estado': 'ANALISIS FINALIZADO',
            'conclusion_final': conclusion
        })
        
        if resultado.get('success'):
            return {"success": True, "message": "El análisis de la alerta ha finalizado."}, 200
        else:
            return {"success": False, "error": "No se pudo finalizar el análisis de la alerta."}, 500

    def _ejecutar_nota_de_credito_api(self, alerta_id, data, usuario_id):
        # Simula un `form_data` para reutilizar la lógica existente
        class FormDataMock:
            def __init__(self, data):
                self._data = data
            def get(self, key):
                return self._data.get(key)
            def getlist(self, key):
                return self._data.get(key, [])

        # Se necesita el código de alerta, no el ID, para la lógica existente.
        alerta_res = self.alerta_riesgo_model.find_by_id(alerta_id)
        if not alerta_res.get('success') or not alerta_res.get('data'):
             return {"success": False, "error": "Alerta no encontrada"}, 404
        codigo_alerta = alerta_res.get('data').get('codigo')
        
        form_data = FormDataMock({
            'pedido_ids': data.get('pedido_ids', []),
            'recrear_pedido': 'on' if data.get('recrear_pedido') else ''
        })
        return self._ejecutar_nota_de_credito(codigo_alerta, form_data, usuario_id)

    def _ejecutar_inhabilitar_pedidos_api(self, alerta_id, data, usuario_id):
        # Similar a la de nota de crédito, creamos un mock y obtenemos el código.
        class FormDataMock:
            def __init__(self, data):
                self._data = data
            def get(self, key):
                return self._data.get(key)
            def getlist(self, key):
                return self._data.get(key, [])

        alerta_res = self.alerta_riesgo_model.find_by_id(alerta_id)
        if not alerta_res.get('success') or not alerta_res.get('data'):
             return {"success": False, "error": "Alerta no encontrada"}, 404
        codigo_alerta = alerta_res.get('data').get('codigo')

        form_data = FormDataMock({
            'pedido_ids': data.get('pedido_ids', []),
            'recrear_pedido': 'on' if data.get('recrear_pedido') else ''
        })
        return self._ejecutar_inhabilitar_pedidos(codigo_alerta, form_data, usuario_id)

    def _ejecutar_resolver_pedidos_api(self, alerta_id, data, usuario_id):
        # Esta función ya usa el ID de la alerta internamente.
        alerta_res = self.alerta_riesgo_model.find_by_id(alerta_id)
        if not alerta_res.get('success') or not alerta_res.get('data'):
             return {"success": False, "error": "Alerta no encontrada"}, 404
        codigo_alerta = alerta_res.get('data').get('codigo')

        return self._ejecutar_resolver_pedidos(codigo_alerta, None, usuario_id) # form_data no es usado

    def _ejecutar_recibir_devolucion_api(self, alerta_id, data, usuario_id):
        lote_id = data.get('lote_id')
        if not lote_id:
            return {"success": False, "error": "Falta el ID del lote."}, 400

        from app.models.lote_producto import LoteProductoModel
        lote_producto_model = LoteProductoModel()
        
        # Corregido: Usar mayúsculas para el estado
        resultado = lote_producto_model.update(lote_id, {'estado': 'RETIRADO'}, 'id_lote')
        
        if resultado.get('success'):
            self.alerta_riesgo_model.registrar_resolucion_afectado(
                alerta_id, 'lote_producto', lote_id, 'resuelto', 'Retirado (Devolución Recibida)', usuario_id
            )
            return {"success": True, "message": "El lote ha sido marcado como RETIRADO."}, 200
        else:
            logger.error(f"Error al actualizar lote a RETIRADO: {resultado.get('error')}")
            return {"success": False, "error": "No se pudo actualizar el estado del lote."}, 500