from marshmallow import Schema, fields
from app.schemas.reclamo_proveedor_item_schema import ReclamoProveedorItemSchema

class ReclamoProveedorSchema(Schema):
    id = fields.Int(dump_only=True)
    orden_compra_id = fields.Int(required=False, allow_none=True)
    proveedor_id = fields.Int(required=True)
    motivo = fields.Str(required=True)
    descripcion_problema = fields.Str(required=True)
    estado = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)

    # Nuevos campos para el cierre
    fecha_cierre = fields.DateTime(dump_only=True)
    comentario_cierre = fields.Str()

    # Campo para múltiples órdenes de compra
    orden_compra_ids = fields.Str(required=False, allow_none=True)

    # Campo anidado para los ítems del reclamo
    items = fields.Nested(ReclamoProveedorItemSchema, many=True, required=False)
