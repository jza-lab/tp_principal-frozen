from marshmallow import Schema, fields, validate

class AlertaRiesgoSchema(Schema):
    """
    Esquema de Marshmallow para la validación de datos de Alertas de Riesgo.
    """
    id = fields.Int(dump_only=True)
    codigo = fields.Str(dump_only=True)
    origen_tipo_entidad = fields.Str(required=True)
    origen_id_entidad = fields.Str(required=True)
    
    estado = fields.Str(
        validate=validate.OneOf(
            ["Borrador", "Activa", "Cerrada"],
            error="Estado no válido."
        ),
        load_default="Borrador",
        dump_default="Borrador"
    )
    
    motivos = fields.List(fields.Str(), required=False, allow_none=True)
    detalle_motivo = fields.Str(required=False, allow_none=True)
    resolucion_seleccionada = fields.Str(required=False, allow_none=True)

    fecha_creacion = fields.DateTime(dump_only=True)
