from marshmallow import Schema, fields

class ReclamoProveedorItemSchema(Schema):
    id = fields.Int(dump_only=True)
    reclamo_id = fields.Int(required=True)
    insumo_id = fields.UUID(required=True)
    cantidad_reclamada = fields.Float(required=True)
    motivo = fields.Str(required=False)
    created_at = fields.DateTime(dump_only=True)
