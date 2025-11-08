from marshmallow import Schema, fields, validate

class ControlCalidadProductoSchema(Schema):
    """
    Schema para validar y serializar los registros de control de calidad de productos.
    """
    id = fields.Int(dump_only=True)
    lote_producto_id = fields.Int(required=True, error_messages={"required": "El ID del lote de producto es obligatorio."})
    orden_produccion_id = fields.Int(required=False, allow_none=True)
    usuario_supervisor_id = fields.Int(required=True, error_messages={"required": "El ID del usuario es obligatorio."})
    
    resultado_inspeccion = fields.Str(allow_none=True)
    comentarios = fields.Str(allow_none=True)
    foto_url = fields.URL(allow_none=True)
    
    decision_final = fields.Str(
        required=True,
        validate=validate.OneOf(["APROBADO", "EN_CUARENTENA", "RECHAZADO"], error="La decisión final debe ser 'APROBADO', 'EN_CUARENTENA' o 'RECHAZADO'."),
        error_messages={"required": "La decisión final es obligatoria."}
    )
    
    fecha_inspeccion = fields.DateTime(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    class Meta:
        unknown = "EXCLUDE"
