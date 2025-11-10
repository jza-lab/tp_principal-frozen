from app.models.reclamo_proveedor_model import ReclamoProveedorModel
from app.schemas.reclamo_proveedor_schema import ReclamoProveedorSchema
from marshmallow import ValidationError

class ReclamoProveedorController:
    def __init__(self):
        self.model = ReclamoProveedorModel()
        self.schema = ReclamoProveedorSchema()

    def crear_reclamo(self, data):
        try:
            validated_data = self.schema.load(data)
            result = self.model.create(validated_data)
            return result
        except ValidationError as e:
            return {'success': False, 'error': e.messages}
        except Exception as e:
            return {'success': False, 'error': str(e)}
