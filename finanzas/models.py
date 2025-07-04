from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class registro_transacciones(models.Model):
    propietario = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha = models.DateField()
    descripcion = models.CharField(max_length=100)
    categoria = models.CharField(max_length=100)
    monto = models.DecimalField(max_digits=65, decimal_places=3)
    TIPO_CHOICES = [
        ('INGRESO', 'Ingreso'),
        ('GASTO', 'Gasto'),
        ('TRANSFERENCIA','Transferencia'),

    ]
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES)
    cuenta_origen = models.CharField(max_length=100)
    cuenta_destino = models.CharField(max_length=100)
    id_prestamo_ref = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return f"{self.id} - {self.descripcion}"
    
# NUEVO MODELO PARA CREDENCIALES DE GOOGLE
class GoogleCredentials(models.Model):
    # Un enlace uno-a-uno con el usuario de Django. Cada usuario solo puede tener un set de credenciales.
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Usamos TextField porque los tokens pueden ser largos
    token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    token_uri = models.CharField(max_length=255)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    scopes = models.TextField()

    def __str__(self):
        return f"Credenciales de Google para {self.user.username}"
    
# finanzas/models.py

# ... (tus otros modelos como registro_transacciones) ...

class TransaccionPendiente(models.Model):
    ESTADOS = (
        ('pendiente', 'Pendiente'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
    )
    
    propietario = models.ForeignKey(User, on_delete=models.CASCADE)
    datos_json = models.JSONField() # Aquí guardaremos el resultado de Gemini
    estado = models.CharField(max_length=10, choices=ESTADOS, default='pendiente')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        # Intenta mostrar una descripción o el total para que sea fácil de leer en el admin
        descripcion = self.datos_json.get('descripcion', self.datos_json.get('establecimiento', 'N/A'))
        return f"Pendiente de {self.propietario.username} - {descripcion}"