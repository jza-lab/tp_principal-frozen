from marshmallow import Schema, fields

class ReclamoProveedorSchema(Schema):
    id = fields.Int(dump_only=True)
    orden_compra_id = fields.Int(required=True)
    proveedor_id = fields.Int(required=True)
    fecha_creacion = fields.DateTime(dump_only=True)
    motivo = fields.Str(required=True)
    descripcion_problema = fields.Str(required=True)
    estado = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
