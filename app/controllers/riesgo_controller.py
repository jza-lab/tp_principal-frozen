from app.controllers.base_controller import BaseController
from app.models.alerta_riesgo import AlertaRiesgoModel
from app.models.trazabilidad import TrazabilidadModel 
from app.schemas.alerta_riesgo_schema import AlertaRiesgoSchema
from app.controllers.nota_credito_controller import NotaCreditoController
from marshmallow import ValidationError
from flask import url_for
import logging

logger = logging.getLogger(__name__)

class RiesgoController(BaseController):
    def __init__(self):
        super().__init__()
        self.alerta_riesgo_model = AlertaRiesgoModel()
        self.alerta_riesgo_schema = AlertaRiesgoSchema()
        self.trazabilidad_model = TrazabilidadModel() 
        self.nota_credito_controller = NotaCreditoController()

    def crear_alerta_riesgo(self, datos_json):
        try:
            tipo_entidad = datos_json.get("tipo_entidad")
            id_entidad = datos_json.get("id_entidad")
            if not tipo_entidad or not id_entidad:
                return {"success": False, "error": "tipo_entidad y id_entidad son requeridos."}, 400

            afectados = self.trazabilidad_model.obtener_entidades_afectadas(tipo_entidad, id_entidad)
            
            count_res = self.alerta_riesgo_model.count()
            count = count_res.get('data', [{}])[0].get('count', 0) if count_res.get('success') else 0

            nueva_alerta_data = {"origen_tipo_entidad": tipo_entidad, "origen_id_entidad": str(id_entidad), "estado": "Borrador", "codigo": f"ALR-{count + 1}"}
            
            validated_data = self.alerta_riesgo_schema.load(nueva_alerta_data)
            resultado_alerta = self.alerta_riesgo_model.create(validated_data)
            if not resultado_alerta.get("success"): return resultado_alerta, 500

            nueva_alerta = resultado_alerta.get("data")[0]
            if afectados:
                self.alerta_riesgo_model.asociar_afectados(nueva_alerta['id'], afectados)

            return {"success": True, "data": nueva_alerta}, 201

        except ValidationError as err:
            return {"success": False, "errors": err.messages}, 400
        except Exception as e:
            logger.error(f"Error al crear alerta de riesgo: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def obtener_detalle_alerta_completo(self, codigo_alerta):
        """
        Obtiene todos los datos necesarios para la página de detalle de una alerta,
        incluyendo los detalles de las NC si ya fueron creadas.
        """
        try:
            alerta_res = self.alerta_riesgo_model.find_one_by('codigo', codigo_alerta)
            if not alerta_res.get("success") or not alerta_res.get("data"):
                 return {"success": False, "error": "Alerta no encontrada"}, 404
            
            alerta = alerta_res.get("data")[0]
            
            if alerta['estado'] == 'Activa':
                # Si la alerta ya está activa, buscar las NC asociadas
                ncs_asociadas_res = self.nota_credito_controller.obtener_detalle_nc_por_alerta(alerta['id'])
                alerta['notas_de_credito'] = ncs_asociadas_res.get('data', [])
            else:
                # Si está en borrador, obtener los detalles de los pedidos/lotes afectados
                afectados_data = self.alerta_riesgo_model.obtener_afectados_detalle(alerta['id'])
                alerta['afectados_detalle'] = afectados_data
            
            return {"success": True, "data": alerta}, 200
        
        except Exception as e:
            logger.error(f"Error al obtener detalle completo de alerta {codigo_alerta}: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def ejecutar_accion_riesgo(self, codigo_alerta, form_data):
        accion = form_data.get("accion")
        if accion == "nota_credito":
            return self._ejecutar_nota_de_credito(codigo_alerta, form_data)
        return {"success": False, "error": "Acción no válida."}, 400

    def _ejecutar_nota_de_credito(self, codigo_alerta, form_data):
        pedidos_seleccionados = form_data.getlist("pedido_ids")
        if not pedidos_seleccionados:
            return {"success": False, "error": "No se seleccionaron pedidos para la acción."}, 400

        try:
            alerta_res = self.alerta_riesgo_model.find_one_by('codigo', codigo_alerta)
            if not alerta_res.get('data'): return {"success": False, "error": "Alerta no encontrada."}, 404
            alerta = alerta_res.get('data')[0]
            
            resultados = self.nota_credito_controller.crear_notas_credito_para_pedidos_afectados(
                alerta_id=alerta['id'],
                pedidos_ids=pedidos_seleccionados,
                motivo=form_data.get('motivos'),
                detalle=form_data.get('detalle_motivo')
            )

            if not resultados['success']:
                return {"success": False, "error": "No se pudo crear ninguna Nota de Crédito.", "details": resultados.get('errors')}, 500

            self.alerta_riesgo_model.update(alerta['id'], {'estado': 'Activa', 'resolucion_seleccionada': 'nota_credito'})
            
            redirect_url = url_for('admin_riesgos.detalle_riesgo_page', codigo_alerta=codigo_alerta)

            return {"success": True, "message": f"Se procesaron {resultados['count']} notas de crédito.", "redirect_url": redirect_url}, 200

        except Exception as e:
            logger.error(f"Error al ejecutar nota de crédito: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500
