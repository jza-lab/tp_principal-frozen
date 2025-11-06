from app.controllers.base_controller import BaseController
from app.models.alerta_riesgo import AlertaRiesgoModel
from app.models.trazabilidad import TrazabilidadModel 
from app.schemas.alerta_riesgo_schema import AlertaRiesgoSchema
from app.controllers.nota_credito_controller import NotaCreditoController
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

    def previsualizar_riesgo(self, tipo_entidad, id_entidad):
        try:
            afectados = self.alerta_riesgo_model.get_trazabilidad_afectados(tipo_entidad, id_entidad)
            
            if not afectados:
                return {"success": True, "data": {"afectados_detalle": {}}}, 200

            detalles = self.alerta_riesgo_model.obtener_afectados_detalle_para_previsualizacion(afectados)
            return {"success": True, "data": {"afectados_detalle": detalles}}, 200

        except Exception as e:
            logger.error(f"Error al previsualizar riesgo: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

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
            afectados = self.alerta_riesgo_model.get_trazabilidad_afectados(tipo_entidad, id_entidad)
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
                records = [{'alerta_id': nueva_alerta['id'], 'tipo_entidad': a['tipo_entidad'], 'id_entidad': str(a['id_entidad'])} for a in afectados]
                self.alerta_riesgo_model.create(records)


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
            # Siempre obtener los detalles de las entidades afectadas y su estado
            afectados_con_estado = self.alerta_riesgo_model.obtener_afectados_con_estado(alerta['id'])
            
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
            
            if alerta['estado'] in ['Resuelta', 'Cerrada']:
                ncs_asociadas_res = self.nota_credito_controller.obtener_detalle_nc_por_alerta(alerta['id'])
                alerta['notas_de_credito'] = ncs_asociadas_res.get('data', [])
            
            return {"success": True, "data": alerta}, 200
        
        except Exception as e:
            logger.error(f"Error al obtener detalle completo de alerta {codigo_alerta}: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def ejecutar_accion_riesgo(self, codigo_alerta, form_data):
        accion = form_data.get("accion")
        if accion == "nota_credito":
            return self._ejecutar_nota_de_credito(codigo_alerta, form_data)
        elif accion == "cancelar_pedidos":
            return self._ejecutar_cancelar_pedidos(codigo_alerta, form_data)
        return {"success": False, "error": "Acción no válida."}, 400

    def _ejecutar_nota_de_credito(self, codigo_alerta, form_data):
        pedidos_seleccionados = form_data.getlist("pedido_ids")
        recrear_pedido = form_data.get("recrear_pedido") == "on"
        if not pedidos_seleccionados:
            return {"success": False, "error": "No se seleccionaron pedidos para la acción."}, 400

        try:
            alerta_res = self.alerta_riesgo_model.find_all({'codigo': codigo_alerta}, limit=1)
            if not alerta_res.get('data'): return {"success": False, "error": "Alerta no encontrada."}, 404
            alerta = alerta_res.get('data')[0]

            afectados = self.alerta_riesgo_model.obtener_afectados(alerta['id'])
            lotes_producto_afectados_ids = [a['id_entidad'] for a in afectados if a['tipo_entidad'] == 'lote_producto']

            resultados_nc = self.nota_credito_controller.crear_notas_credito_para_pedidos_afectados(
                alerta_id=alerta['id'],
                pedidos_ids=pedidos_seleccionados,
                motivo=form_data.get('motivos'),
                detalle=form_data.get('detalle_motivo'),
                lotes_producto_afectados_ids=lotes_producto_afectados_ids
            )
            if not resultados_nc['success']:
                return {"success": False, "error": "No se pudo crear ninguna Nota de Crédito.", "details": resultados_nc.get('errors')}, 500
            
            notas_creadas = resultados_nc.get('data', [])
            for nc in notas_creadas:
                pedido_id_resuelto = nc['pedido_origen_id']
                self.alerta_riesgo_model.actualizar_estado_afectados(alerta['id'], [pedido_id_resuelto], 'nota_credito', nc['id'])

            # Lógica para recrear pedidos
            if recrear_pedido:
                for pedido_id in pedidos_seleccionados:
                    self._recrear_pedido_sin_lotes_afectados(pedido_id, lotes_producto_afectados_ids)
            
            redirect_url = url_for('admin_riesgos.detalle_riesgo_page', codigo_alerta=codigo_alerta)

            return {"success": True, "message": f"Se procesaron {resultados_nc['count']} notas de crédito.", "redirect_url": redirect_url}, 200

        except Exception as e:
            logger.error(f"Error al ejecutar nota de crédito: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def _ejecutar_cancelar_pedidos(self, codigo_alerta, form_data):
        pedidos_seleccionados = form_data.getlist("pedido_ids")
        recrear_pedido = form_data.get("recrear_pedido") == "on"
        if not pedidos_seleccionados:
            return {"success": False, "error": "No se seleccionaron pedidos para la acción."}, 400
        
        try:
            alerta_res = self.alerta_riesgo_model.obtener_por_codigo(codigo_alerta)
            if not alerta_res.get('data'): return {"success": False, "error": "Alerta no encontrada."}, 404
            alerta = alerta_res.get('data')[0]
            
            from app.controllers.pedido_controller import PedidoController
            pedido_controller = PedidoController()
            
            cancelados_count = 0
            for pedido_id in pedidos_seleccionados:
                res, _ = pedido_controller.cancelar_pedido(int(pedido_id))
                if res.get('success'):
                    self.alerta_riesgo_model.actualizar_estado_afectados(alerta['id'], [pedido_id], 'cancelacion')
                    cancelados_count += 1

            if recrear_pedido:
                afectados = self.alerta_riesgo_model.obtener_afectados(alerta['id'])
                lotes_producto_afectados_ids = [a['id_entidad'] for a in afectados if a['tipo_entidad'] == 'lote_producto']

                for pedido_id in pedidos_seleccionados:
                    self._recrear_pedido_sin_lotes_afectados(pedido_id, lotes_producto_afectados_ids)

            redirect_url = url_for('admin_riesgos.detalle_riesgo_page', codigo_alerta=codigo_alerta)
            return {"success": True, "message": f"Se cancelaron {cancelados_count} pedidos.", "redirect_url": redirect_url}, 200

        except Exception as e:
            logger.error(f"Error al cancelar pedidos: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

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