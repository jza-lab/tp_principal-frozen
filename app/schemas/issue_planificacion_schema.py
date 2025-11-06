from marshmallow import Schema, fields, validate

class IssuePlanificacionSchema(Schema):
    """
    Schema para validar los datos de Issues de Planificación.
    """
    id = fields.Int(dump_only=True)
    orden_produccion_id = fields.Int(required=True)
    tipo_error = fields.Str(
        required=True,
        validate=validate.OneOf(['LATE_CONFIRM', 'SOBRECARGA_CAPACIDAD', 'SIN_LINEA'])
    )
    mensaje = fields.Str(required=True)
    estado = fields.Str(validate=validate.OneOf(['PENDIENTE', 'RESUELTO']))
    datos_snapshot = fields.Dict() # Para el JSONB
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
