from marshmallow import Schema, fields, validate

class ControlCalidadInsumoSchema(Schema):
    """
    Schema para validar y serializar los registros de control de calidad de insumos.
    """
    id = fields.Int(dump_only=True)
    lote_insumo_id = fields.UUID(required=True, error_messages={"required": "El ID del lote de insumo es obligatorio."})
    orden_compra_id = fields.Int(required=True, error_messages={"required": "El ID de la orden de compra es obligatorio."})
    usuario_supervisor_id = fields.Int(required=True, error_messages={"required": "El ID del supervisor es obligatorio."})
    
    resultado_inspeccion = fields.Str(allow_none=True)
    comentarios = fields.Str(allow_none=True)
    foto_url = fields.URL(allow_none=True)
    
    decision_final = fields.Str(
        required=True,
        validate=validate.OneOf(["EN_CUARENTENA", "RECHAZADO"], error="La decisión final debe ser 'EN_CUARENTENA' o 'RECHAZADO'."),
        error_messages={"required": "La decisión final es obligatoria."}
    )
    
    fecha_inspeccion = fields.DateTime(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    class Meta:
        # Asegura que no se incluyan campos desconocidos en la carga de datos
        unknown = "EXCLUDE"
