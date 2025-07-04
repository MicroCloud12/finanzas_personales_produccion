from django.test import TestCase
from django.contrib.auth.models import User
from datetime import date

# Create your tests here.
from .models import registro_transacciones


class RegistroTransaccionesModelTest(TestCase):
    def test_str_representation(self):
        user = User.objects.create(username="tester")
        trans = registro_transacciones.objects.create(
            propietario=user,
            fecha=date.today(),
            descripcion="Compra",
            categoria="General",
            monto=10,
            tipo="INGRESO",
            cuenta_origen="A",
            cuenta_destino="B",
        )

        self.assertEqual(str(trans), f"{trans.id} - Compra")