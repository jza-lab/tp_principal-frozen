from marshmallow import Schema, fields, validate

class TraspasoTurnoSchema(Schema):
    """
    Schema para la validación y serialización de los datos de un traspaso de turno.
    """
    id = fields.Int(dump_only=True)
    orden_produccion_id = fields.Int(
        required=True,
        error_messages={"required": "El ID de la orden de producción es obligatorio."}
    )
    usuario_saliente_id = fields.Int(
        required=True,
        error_messages={"required": "El ID del operario saliente es obligatorio."}
    )
    fecha_traspaso = fields.DateTime(
        required=True,
        error_messages={"required": "La fecha de traspaso es obligatoria."}
    )
    notas_novedades = fields.Str(
        required=False, 
        allow_none=True, 
        validate=validate.Length(max=500)
    )
    notas_insumos = fields.Str(
        required=False, 
        allow_none=True, 
        validate=validate.Length(max=500)
    )
    resumen_produccion = fields.Dict(
        required=True,
        error_messages={"required": "El resumen de producción es obligatorio."}
    )
    usuario_entrante_id = fields.Int(required=False, allow_none=True)
    fecha_recepcion = fields.DateTime(required=False, allow_none=True)

    class Meta:
        strict = True
        ordered = True
