from app.controllers.base_controller import BaseController
from app.models.alerta_riesgo import AlertaRiesgoModel
from app.models.trazabilidad import TrazabilidadModel
from app.schemas.alerta_riesgo_schema import AlertaRiesgoSchema
from app.controllers.nota_credito_controller import NotaCreditoController
from marshmallow import ValidationError
from flask import flash, url_for, current_app
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
            if any(s in estado_actual for s in ESTADOS_AFECTADOS.get(tipo, [])):
                self.alerta_riesgo_model._actualizar_flag_en_alerta_entidad(tipo, entidad_id, True)
                try:
                    if tipo in ['lote_insumo', 'lote_producto']:
                        controllers[tipo].poner_lote_en_cuarentena(entidad_id, motivo_log, 999999, usuario_id if tipo == 'lote_insumo' else None)
                    elif tipo == 'orden_produccion':
                        controllers[tipo].cambiar_estado_orden_simple(int(entidad_id), 'EN ESPERA')
                    elif tipo == 'pedido':
                        controllers[tipo].cambiar_estado_pedido(int(entidad_id), 'EN REVISION')
                except Exception as e:
                    logger.error(f"Fallo al procesar efecto secundario para {tipo}:{entidad_id}. Error: {e}", exc_info=True)

    def resolver_cuarentena_lote_desde_alerta(self, datos, usuario_id):
        lote_id, tipo_lote, resolucion, alerta_id = datos.get('lote_id'), datos.get('tipo_lote'), datos.get('resolucion'), datos.get('alerta_id')
        if not all([lote_id, tipo_lote, resolucion, alerta_id]):
            return {"success": False, "error": "Faltan parámetros requeridos."}, 400
        try:
            alerta_id = int(alerta_id)
            if tipo_lote == 'lote_insumo':
                return self._resolver_lote_insumo_apto(alerta_id, lote_id, usuario_id) if resolucion == 'apto' else self._resolver_lote_insumo_no_apto(alerta_id, lote_id, usuario_id)
            elif tipo_lote == 'lote_producto':
                return self._resolver_lote_producto_apto(alerta_id, lote_id, usuario_id) if resolucion == 'apto' else self._resolver_lote_producto_no_apto(alerta_id, lote_id, usuario_id)
            return {"success": False, "error": "Tipo de lote no válido."}, 400
        except Exception as e:
            logger.error(f"Error en resolver_cuarentena_lote_desde_alerta: {e}", exc_info=True)
            return {"success": False, "error": "Error interno del servidor."}, 500

    def _resolver_lote_insumo_apto(self, alerta_id, lote_insumo_id, usuario_id):
        from app.controllers.inventario_controller import InventarioController
        estado_previo = self.alerta_riesgo_model.obtener_estado_previo(alerta_id, 'lote_insumo', lote_insumo_id)
        nuevo_estado = 'disponible' if estado_previo and 'en revisión' in estado_previo.lower() else estado_previo
        InventarioController().liberar_lote_de_cuarentena(lote_insumo_id, 999999, nuevo_estado)
        self.alerta_riesgo_model.actualizar_estado_afectados(alerta_id, [lote_insumo_id], 'apto', 'lote_insumo', usuario_id)
        self._verificar_y_cerrar_alerta_si_corresponde(alerta_id)
        return {"success": True, "message": "Lote de insumo marcado como Apto. Proceda a verificar los lotes de producto afectados."}, 200

    def _resolver_lote_insumo_no_apto(self, alerta_id, lote_insumo_id, usuario_id):
        from app.controllers.inventario_controller import InventarioController
        InventarioController().marcar_lote_como_no_apto(lote_insumo_id, usuario_id, "Rechazado por alerta")
        self.alerta_riesgo_model.actualizar_estado_afectados(alerta_id, [lote_insumo_id], 'no_apto_retirado', 'lote_insumo', usuario_id)
        for afectado in self.trazabilidad_model.obtener_afectados_para_alerta('lote_insumo', lote_insumo_id):
            if afectado['tipo_entidad'] == 'orden_produccion':
                self._manejar_reemplazo_y_estado_op(alerta_id, afectado['id_entidad'], lote_insumo_id, usuario_id)
                self.alerta_riesgo_model.actualizar_estado_afectados(alerta_id, [afectado['id_entidad']], 'replanificar_por_insumo_no_apto', 'orden_produccion', usuario_id)
            elif afectado['tipo_entidad'] == 'lote_producto':
                self._resolver_lote_producto_no_apto(alerta_id, afectado['id_entidad'], usuario_id, f"derivado del lote de insumo no apto {lote_insumo_id}")
        self._verificar_y_cerrar_alerta_si_corresponde(alerta_id)
        return {"success": True, "message": "Lote de insumo No Apto. Efectos propagados a entidades dependientes."}, 200

    def _manejar_reemplazo_y_estado_op(self, alerta_id, op_id, lote_insumo_retirado_id, usuario_id):
        from app.controllers.orden_produccion_controller import OrdenProduccionController
        from app.models.inventario import InventarioModel
        op_controller = OrdenProduccionController()
        if InventarioModel().buscar_lote_reemplazo_para_op(op_id, lote_insumo_retirado_id):
            op_controller.cambiar_estado_orden_simple(op_id, 'LISTA PARA PRODUCIR')
        else:
            op_controller.cambiar_estado_orden_simple(op_id, 'PENDIENTE')

    def _resolver_lote_producto_apto(self, alerta_id, lote_producto_id, usuario_id):
        from app.controllers.lote_producto_controller import LoteProductoController
        estado_previo = self.alerta_riesgo_model.obtener_estado_previo(alerta_id, 'lote_producto', lote_producto_id)
        nuevo_estado = 'disponible' if estado_previo and 'en revisión' in estado_previo.lower() else estado_previo
        LoteProductoController().liberar_lote_de_cuarentena(lote_producto_id, 999999, nuevo_estado)
        self.alerta_riesgo_model.actualizar_estado_afectados(alerta_id, [lote_producto_id], 'apto', 'lote_producto', usuario_id)
        self._restaurar_entidades_padre_si_corresponde(alerta_id, lote_producto_id, usuario_id)
        self._verificar_y_cerrar_alerta_si_corresponde(alerta_id)
        return {"success": True, "message": "Lote de producto marcado como Apto."}, 200

    def _resolver_lote_producto_no_apto(self, alerta_id, lote_producto_id, usuario_id, motivo_adicional=""):
        from app.controllers.lote_producto_controller import LoteProductoController
        from app.controllers.pedido_controller import PedidoController
        lote_producto_controller, pedido_controller = LoteProductoController(), PedidoController()
        motivo = f"Lote no apto por alerta. {motivo_adicional}".strip()
        lote_producto_controller.marcar_lote_como_no_apto(lote_producto_id, usuario_id, motivo, "Inspección por Alerta")
        self.alerta_riesgo_model.actualizar_estado_afectados(alerta_id, [lote_producto_id], 'no_apto_retirado', 'lote_producto', usuario_id)
        
        from app.models.pedido import PedidoModel
        pedidos_res = PedidoModel().find_pedidos_by_lote_producto(lote_producto_id)

        if pedidos_res:
            for pedido in pedidos_res:
                if pedido.get('estado', '').lower() in ['en transito', 'recibido', 'completado']:
                    lote_producto_controller.model.update(lote_producto_id, {'estado': 'DEVOLUCION PENDIENTE'}, 'id_lote')
                    pedido_controller.cambiar_estado_pedido(pedido['id'], 'EN TRANSITO')
                    self.alerta_riesgo_model.actualizar_estado_afectados(alerta_id, [pedido['id']], 'devolucion_pendiente', 'pedido', usuario_id)
        self._verificar_y_cerrar_alerta_si_corresponde(alerta_id)
        return {"success": True, "message": "Lote de producto No Apto. Pedidos en tránsito actualizados para devolución."}, 200

    def _restaurar_entidades_padre_si_corresponde(self, alerta_id, lote_producto_id, usuario_id):
        from app.controllers.orden_produccion_controller import OrdenProduccionController
        from app.controllers.pedido_controller import PedidoController
        
        # Restaurar Orden de Producción
        op_res = self.trazabilidad_model.obtener_op_de_lote_producto(lote_producto_id)
        if op_res.get('success') and op_res.get('data'):
            op = op_res['data'][0] # Puede devolver una lista
            if self.alerta_riesgo_model.todos_afectados_dependientes_resueltos(alerta_id, 'orden_produccion', op['id']):
                estado_previo = self.alerta_riesgo_model.obtener_estado_previo(alerta_id, 'orden_produccion', op['id'])
                if estado_previo:
                    OrdenProduccionController().cambiar_estado_orden_simple(op['id'], estado_previo)
                    self.alerta_riesgo_model.actualizar_estado_afectados(alerta_id, [op['id']], 'no_afectado', 'orden_produccion', usuario_id)
                    logger.info(f"OP {op['id']} restaurada a su estado previo '{estado_previo}' tras resolución de lotes.")

        # Restaurar Pedidos
        pedidos_res = self.trazabilidad_model.obtener_pedidos_de_lote_producto(lote_producto_id)
        if pedidos_res.get('success') and pedidos_res.get('data'):
            for pedido in pedidos_res['data']:
                 if self.alerta_riesgo_model.todos_afectados_dependientes_resueltos(alerta_id, 'pedido', pedido['id']):
                    estado_previo = self.alerta_riesgo_model.obtener_estado_previo(alerta_id, 'pedido', pedido['id'])
                    if estado_previo:
                        PedidoController().cambiar_estado_pedido(pedido['id'], estado_previo)
                        self.alerta_riesgo_model.actualizar_estado_afectados(alerta_id, [pedido['id']], 'no_afectado', 'pedido', usuario_id)
                        logger.info(f"Pedido {pedido['id']} restaurado a su estado previo '{estado_previo}' tras resolución de lotes.")

    def _verificar_y_cerrar_alerta_si_corresponde(self, alerta_id):
        self.alerta_riesgo_model.verificar_y_cerrar_alerta(alerta_id)

    def finalizar_analisis_alerta(self, alerta_id, conclusion, usuario_id):
        alerta_res = self.alerta_riesgo_model.find_by_id(alerta_id)
        if not alerta_res.get('success') or not alerta_res.get('data'):
            return {"success": False, "error": "Alerta no encontrada."}, 404
        alerta = alerta_res['data']
        if alerta.get('estado') != 'Resuelta':
            return {"success": False, "error": f"La alerta debe estar en estado 'Resuelta', pero está en '{alerta.get('estado')}'."}, 400
        self.alerta_riesgo_model.update(alerta_id, {'estado': 'ANALISIS FINALIZADO', 'conclusion_final': conclusion, 'id_usuario_finalizacion': usuario_id})
        for afectado in self.alerta_riesgo_model.obtener_afectados(alerta_id):
            if not self.alerta_riesgo_model.entidad_esta_en_otras_alertas_activas(afectado['tipo_entidad'], afectado['id_entidad'], alerta_id):
                self.alerta_riesgo_model._actualizar_flag_en_alerta_entidad(afectado['tipo_entidad'], afectado['id_entidad'], False)
        return {"success": True, "message": "El análisis de la alerta ha sido finalizado."}, 200

    def obtener_detalle_alerta_completo(self, codigo_alerta) -> dict:
        try:
            alerta_res = self.alerta_riesgo_model.obtener_por_codigo(codigo_alerta)
            if not alerta_res.get("success") or not alerta_res.get("data"): return {"success": False, "error": "Alerta no encontrada"}, 404
            alerta = alerta_res.get("data")[0]
            from app.controllers.usuario_controller import UsuarioController
            usuario_controller = UsuarioController()
            creador_id = alerta.get('id_usuario_creador')
            alerta['creador_info'] = usuario_controller.obtener_detalles_completos_usuario(creador_id) if creador_id else None
            afectados_con_estado = self.alerta_riesgo_model.obtener_afectados_con_estado(alerta['id'])
            ids_por_tipo = {t: [a['id_entidad'] for a in afectados_con_estado if a['tipo_entidad'] == t] for t in {a['tipo_entidad'] for a in afectados_con_estado}}
            detalles_enriquecidos = {}
            if ids_por_tipo.get('lote_insumo'):
                detalles_enriquecidos['lote_insumo'] = {str(i['id_lote']): i for i in self.alerta_riesgo_model.db.table('insumos_inventario').select('id_lote,numero_lote_proveedor,f_ingreso,f_vencimiento,cantidad_en_cuarentena,insumos_catalogo:id_insumo(nombre,unidad_medida),proveedores:id_proveedor(nombre)').in_('id_lote', list(set(ids_por_tipo['lote_insumo']))).execute().data}
            if ids_por_tipo.get('orden_produccion'):
                detalles_enriquecidos['orden_produccion'] = {i['id']: i for i in self.alerta_riesgo_model.db.table('ordenes_produccion').select('id,codigo,cantidad_planificada,cantidad_producida,estado,fecha_inicio,productos(nombre)').in_('id', [int(i) for i in set(ids_por_tipo['orden_produccion'])]).execute().data}
            if ids_por_tipo.get('lote_producto'):
                detalles_enriquecidos['lote_producto'] = {i['id_lote']: i for i in self.alerta_riesgo_model.db.table('lotes_productos').select('id_lote,numero_lote,cantidad_en_cuarentena,fecha_produccion,fecha_vencimiento,productos(nombre)').in_('id_lote', [int(i) for i in set(ids_por_tipo['lote_producto'])]).execute().data}
            
            participantes = {}
            for afectado in filter(lambda a: a.get('id_usuario_resolucion') and a.get('resolucion_aplicada'), afectados_con_estado):
                resolutor_id = afectado['id_usuario_resolucion']
                if resolutor_id not in participantes:
                    participantes[resolutor_id] = {'info': usuario_controller.obtener_detalles_completos_usuario(resolutor_id), 'acciones': set()}
                participantes[resolutor_id]['acciones'].add(f"{afectado['resolucion_aplicada'].replace('_', ' ').title()} sobre {afectado['tipo_entidad'].replace('_', ' ')} #{afectado['id_entidad']}")
            alerta['participantes_resolucion'] = [{'info': p['info'], 'acciones': list(p['acciones'])} for p in participantes.values()]

            afectados_detalle = self.alerta_riesgo_model.obtener_afectados_detalle_para_previsualizacion(afectados_con_estado)
            map_plural_singular = {'lotes_insumo': 'lote_insumo', 'ordenes_produccion': 'orden_produccion', 'lotes_producto': 'lote_producto', 'pedidos': 'pedido'}

            for tipo_plural, entidades in afectados_detalle.items():
                tipo_singular = map_plural_singular.get(tipo_plural)
                if not tipo_singular or not entidades: continue
                id_field = 'id_lote' if 'lote' in tipo_singular else 'id'
                
                for entidad in entidades:
                    entidad_id_str = str(entidad.get(id_field))
                    
                    # Fusionar con detalles enriquecidos (que ya tienen el estado y otros campos)
                    if detalles_enriquecidos.get(tipo_singular, {}).get(entidad_id_str):
                        entidad.update(detalles_enriquecidos[tipo_singular][entidad_id_str])
                    
                    # Fusionar con el estado de resolución de la tabla 'afectados'
                    afectado_info = next((a for a in afectados_con_estado if a['tipo_entidad'] == tipo_singular and str(a['id_entidad']) == entidad_id_str), None)
                    if afectado_info:
                        entidad.update({
                            'estado_resolucion': afectado_info.get('estado', 'pendiente'),
                            'resolucion_aplicada': afectado_info.get('resolucion_aplicada')
                        })
                        if afectado_info.get('id_usuario_resolucion'):
                            entidad['resolutor_info'] = usuario_controller.obtener_detalles_completos_usuario(afectado_info['id_usuario_resolucion'])
                        if afectado_info.get('tipo_entidad') == 'pedido' and afectado_info.get('resolucion_aplicada') == 'nota_credito' and afectado_info.get('id_documento_relacionado'):
                            nc_res, _ = self.nota_credito_controller.obtener_detalles_para_pdf(afectado_info['id_documento_relacionado'])
                            if nc_res.get('success'):
                                entidad['nota_credito'] = nc_res['data']

            # Corrección para el estado de la alerta principal, insensible a mayúsculas/minúsculas
            if alerta.get('estado') and isinstance(alerta['estado'], str):
                if alerta['estado'].lower() == 'pendiente':
                    alerta['estado'] = 'Pendiente'
            
            if 'pedidos' in afectados_detalle:
                from app.controllers.pedido_controller import PedidoController
                from app.models.pedido import PedidoModel
                pedido_controller = PedidoController()
                lotes_afectados = {str(a['id_entidad']) for a in self.trazabilidad_model.obtener_afectados_para_alerta(alerta['origen_tipo_entidad'], alerta['origen_id_entidad']) if a['tipo_entidad'] == 'lote_producto'}
                for pedido in afectados_detalle['pedidos']:
                    res_pedido, _ = pedido_controller.obtener_pedido_por_id(pedido['id'])
                    if not res_pedido.get('success'): continue
                    pedido.update(res_pedido.get('data', {}))
                    items_afectados_count = sum(1 for item in pedido.get('items', []) if any(str(r.get('lote_producto_id')) in lotes_afectados for r in PedidoModel().get_reservas_for_item(item['id'])))
                    pedido['afectacion_items_str'] = f"{items_afectados_count} de {len(pedido.get('items', []))}"
                    total_valor = sum(float(i.get('producto_nombre', {}).get('precio_unitario', 0)) * i.get('cantidad', 0) for i in pedido.get('items', []))
                    valor_afectado = sum(float(i.get('producto_nombre', {}).get('precio_unitario', 0)) * i.get('cantidad', 0) for i in pedido.get('items', []) if any(str(r.get('lote_producto_id')) in lotes_afectados for r in PedidoModel().get_reservas_for_item(i['id'])))
                    pedido['afectacion_valor_str'] = f"{round((valor_afectado / total_valor) * 100)}%" if total_valor > 0 else "0%"

            alerta['afectados_detalle'] = afectados_detalle
            if alerta['estado'] in ['Resuelta', 'Cerrada', 'ANALISIS FINALIZADO']:
                alerta['notas_de_credito'] = self.nota_credito_controller.obtener_detalle_nc_por_alerta(alerta['id']).get('data', [])
            
            hay_no_aptos = any(a.get('resolucion_aplicada') and 'no_apto' in a['resolucion_aplicada'] for a in afectados_con_estado)
            todos_no_pedidos_resueltos = all(a.get('estado') == 'resuelto' for a in afectados_con_estado if a.get('tipo_entidad') != 'pedido')
            alerta['puede_resolver_pedidos_masivamente'] = todos_no_pedidos_resueltos and not hay_no_aptos
            
            if alerta.get('estado') == 'Resuelta':
                alerta['conclusion_sugerida'] = self._sugerir_conclusion_final(alerta, afectados_con_estado)

            return {"success": True, "data": alerta}, 200
        except Exception as e:
            logger.error(f"Error al obtener detalle completo de alerta {codigo_alerta}: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def _sugerir_conclusion_final(self, alerta, afectados_con_estado):
        if not afectados_con_estado:
            return "Falso positivo: La alerta se generó pero no se encontraron entidades afectadas en la trazabilidad."

        resoluciones = {a.get('resolucion_aplicada') for a in afectados_con_estado}
        
        todos_aptos = all(r in ['apto', 'no_afectado', None, 'insumos_liberados', 'sin_insumos_comprometidos'] for r in resoluciones)
        if todos_aptos:
            return "Falso positivo: Todas las entidades afectadas fueron inspeccionadas y resultaron ser aptas. El riesgo fue descartado."

        hay_devoluciones = any('devolucion_pendiente' in r for r in resoluciones if r)
        if hay_devoluciones:
            return "Mercancía recuperada: Se identificaron lotes no aptos que ya habían sido despachados y se inició el proceso de devolución."
        
        hay_notas_credito = any('nota_credito' in r for r in resoluciones if r)
        if alerta.get('origen_tipo_entidad') == 'pedido' and hay_notas_credito:
            return "Reclamo de cliente gestionado: La alerta se originó por un reclamo y se emitió una nota de crédito al cliente afectado."
            
        hay_retirados = any('no_apto_retirado' in r for r in resoluciones if r)
        if hay_retirados and not hay_devoluciones:
            return "Mercancía retirada: Se detectaron lotes no aptos que fueron retirados de circulación antes de ser despachados."

        return "Incidente gestionado: Se aplicaron diversas resoluciones a las entidades afectadas según correspondía."

    def ejecutar_accion_riesgo(self, codigo_alerta, form_data, usuario_id):
        accion = form_data.get("accion")
        alerta_res = self.alerta_riesgo_model.obtener_por_codigo(codigo_alerta)
        if not alerta_res.get('success') or not alerta_res.get('data'): return {"success": False, "error": "Alerta no encontrada."}, 404
        alerta = alerta_res.get('data')[0]
        if alerta.get('origen_tipo_entidad') == 'pedido' and accion != 'nota_credito':
             return ({"success": False, "error": "Para alertas originadas en un pedido, solo se puede generar una nota de crédito."}, 400)

        acciones = {"nota_credito": self._ejecutar_nota_de_credito, "inhabilitar_pedido": self._ejecutar_inhabilitar_pedidos,
                    "resolver_pedidos": self._ejecutar_resolver_pedidos}
        if accion in acciones: return acciones[accion](alerta, form_data, usuario_id)
        return {"success": False, "error": "Acción no válida."}, 400
        
    def _ejecutar_resolver_pedidos(self, alerta, form_data, usuario_id):
        pedidos_seleccionados = form_data.getlist("pedido_ids")
        if not pedidos_seleccionados: return {"success": False, "error": "No se seleccionaron pedidos."}, 400
        from app.controllers.pedido_controller import PedidoController
        for pedido_id in pedidos_seleccionados:
            estado_previo = self.alerta_riesgo_model.obtener_estado_previo(alerta['id'], 'pedido', pedido_id)
            if estado_previo: PedidoController().cambiar_estado_pedido(int(pedido_id), estado_previo)
        self.alerta_riesgo_model.actualizar_estado_afectados(alerta['id'], pedidos_seleccionados, 'no_afectado', 'pedido', usuario_id)
        self._verificar_y_cerrar_alerta_si_corresponde(alerta['id'])
        return {"success": True, "message": f"Se marcaron {len(pedidos_seleccionados)} pedidos como 'No Afectados'."}, 200

    def _ejecutar_nota_de_credito(self, alerta, form_data, usuario_id):
        pedidos_seleccionados = form_data.getlist("pedido_ids")
        if not pedidos_seleccionados: return {"success": False, "error": "No se seleccionaron pedidos."}, 400
        lotes_afectados_ids = [a['id_entidad'] for a in self.trazabilidad_model.obtener_afectados_para_alerta(alerta['origen_tipo_entidad'], alerta['origen_id_entidad']) if a['tipo_entidad'] == 'lote_producto']
        resultados_nc = self.nota_credito_controller.crear_notas_credito_para_pedidos_afectados(alerta['id'], pedidos_seleccionados, f"Alerta de Riesgo {alerta['codigo']}", alerta.get('motivo'), lotes_afectados_ids)
        if not resultados_nc['success']: return {"success": False, "error": "No se pudo crear Nota de Crédito.", "details": resultados_nc.get('errors')}, 500
        for nc in resultados_nc.get('data', []):
            self.alerta_riesgo_model.actualizar_estado_afectados(alerta['id'], [nc['pedido_origen_id']], 'nota_credito', 'pedido', usuario_id, nc['id'])
        if form_data.get("recrear_pedido") == "on":
            for pedido_id in pedidos_seleccionados: self._recrear_pedido_sin_lotes_afectados(pedido_id, lotes_afectados_ids)
        self._verificar_y_cerrar_alerta_si_corresponde(alerta['id'])
        return {"success": True, "message": f"Se procesaron {resultados_nc['count']} notas de crédito."}, 200

    def _ejecutar_inhabilitar_pedidos(self, alerta, form_data, usuario_id):
        pedidos_seleccionados = form_data.getlist("pedido_ids")
        if not pedidos_seleccionados: return {"success": False, "error": "No se seleccionaron pedidos."}, 400
        from app.controllers.pedido_controller import PedidoController
        inhabilitados_count = 0
        for pedido_id in pedidos_seleccionados:
            res, _ = PedidoController().cancelar_pedido(int(pedido_id))
            if res.get('success'):
                self.alerta_riesgo_model.actualizar_estado_afectados(alerta['id'], [pedido_id], 'inhabilitado', 'pedido', usuario_id)
                inhabilitados_count += 1
        if form_data.get("recrear_pedido") == "on":
            lotes_afectados = [a['id_entidad'] for a in self.alerta_riesgo_model.obtener_afectados(alerta['id']) if a['tipo_entidad'] == 'lote_producto']
            for pedido_id in pedidos_seleccionados: self._recrear_pedido_sin_lotes_afectados(pedido_id, lotes_afectados)
        if inhabilitados_count == 0: return {"success": False, "error": "Ningún pedido pudo ser inhabilitado."}, 500
        self._verificar_y_cerrar_alerta_si_corresponde(alerta['id'])
        return {"success": True, "message": f"Se inhabilitaron {inhabilitados_count} pedidos."}, 200

    def _recrear_pedido_sin_lotes_afectados(self, pedido_id_original, lotes_afectados_ids):
        from app.controllers.pedido_controller import PedidoController
        from flask_jwt_extended import get_current_user
        pedido_controller = PedidoController()
        pedido_original_res, _ = pedido_controller.obtener_pedido_por_id(int(pedido_id_original))
        if not pedido_original_res.get('success'): return
        pedido_original = pedido_original_res.get('data')
        items_no_afectados = pedido_controller.model.get_items_no_afectados(int(pedido_id_original), lotes_afectados_ids)
        if not items_no_afectados: return
        nuevo_pedido_data = {
            "id_cliente": pedido_original['id_cliente'], "fecha_requerido": pedido_original['fecha_requerido'],
            "id_direccion_entrega": pedido_original['id_direccion_entrega'], "codigo": f"{pedido_original['codigo']}-R1",
            "items": [{"id_producto": i['id_producto'], "cantidad": i['cantidad']} for i in items_no_afectados]
        }
        try:
            from flask_jwt_extended import get_jwt_identity
            usuario_id = get_jwt_identity()
        except RuntimeError: usuario_id = -1 # SISTEMA
        pedido_controller.crear_pedido_con_items(nuevo_pedido_data, usuario_id=usuario_id)

    def contactar_clientes_afectados(self, codigo_alerta, form_data):
        pedido_ids, asunto, cuerpo = form_data.getlist("pedido_ids[]"), form_data.get("asunto"), form_data.get("cuerpo")
        if not all([pedido_ids, asunto, cuerpo]): return {"success": False, "error": "Faltan datos."}, 400
        from app.controllers.pedido_controller import PedidoController
        enviados, errores = 0, []
        for pid in pedido_ids:
            res, _ = PedidoController().obtener_pedido_por_id(int(pid))
            if res.get('success') and res.get('data', {}).get('cliente', {}).get('email'):
                try:
                    send_email(res['data']['cliente']['email'], asunto, cuerpo.replace('\n', '<br>'), is_html=True)
                    enviados += 1
                except Exception: errores.append(f"#{pid}")
            else: errores.append(f"#{pid}")
        msg = f"Se enviaron {enviados} de {len(pedido_ids)} correos."
        if errores: msg += f" Fallaron: {', '.join(errores)}."
        return {"success": enviados > 0, "message": msg, "error": "No se pudo enviar ningún correo." if enviados == 0 else ""}, 200 if enviados > 0 else 500

    def _enviar_notificaciones_alerta(self, nueva_alerta):
        try:
            with current_app.app_context():
                url_alerta = url_for('admin_riesgo.detalle_alerta_riesgo', codigo_alerta=nueva_alerta['codigo'], _external=True)
                mensaje = f"<b>Nueva Alerta de Riesgo:</b> {nueva_alerta['codigo']}<br><b>Motivo:</b> {nueva_alerta.get('motivo')}<br><a href='{url_alerta}'>Ver Detalles</a>"
                asunto = f"Nueva Alerta de Riesgo: {nueva_alerta['codigo']}"
                rol_calidad = RoleModel().find_by_codigo('CALIDAD').get('data')
                if rol_calidad:
                    usuarios = UsuarioModel().find_all({'role_id': rol_calidad['id']}).get('data', [])
                    for user in filter(lambda u: u.get('email'), usuarios):
                        send_email(user['email'], asunto, mensaje, is_html=True)
        except Exception as e:
            logger.error(f"Error en _enviar_notificaciones_alerta: {e}", exc_info=True)

    def resolver_alerta_manualmente(self, codigo_alerta, usuario_id):
        alerta_res = self.alerta_riesgo_model.find_all({'codigo': codigo_alerta}, limit=1)
        if not alerta_res.get('success') or not alerta_res.get('data'): return {"success": False, "error": "Alerta no encontrada."}, 404
        alerta = alerta_res.get('data')[0]
        if alerta['estado'] != 'Pendiente': return {"success": False, "error": f"La alerta ya está en estado '{alerta['estado']}'."}, 400
        self.alerta_riesgo_model.update(alerta['id'], {'estado': 'ANALISIS FINALIZADO', 'conclusion_final': 'Resolución manual aplicada.'})
        self.alerta_riesgo_model.db.table('alerta_riesgo_afectados').update({'estado': 'resuelto', 'resolucion_aplicada': 'resuelta_manualmente', 'id_usuario_resolucion': usuario_id}).eq('alerta_id', alerta['id']).eq('estado', 'pendiente').execute()
        for afectado in self.alerta_riesgo_model.obtener_afectados(alerta['id']):
            if not self.alerta_riesgo_model.entidad_esta_en_otras_alertas_activas(afectado['tipo_entidad'], afectado['id_entidad'], alerta['id']):
                self.alerta_riesgo_model._actualizar_flag_en_alerta_entidad(afectado['tipo_entidad'], afectado['id_entidad'], False)
        return {"success": True, "message": "La alerta ha sido marcada como resuelta."}, 200