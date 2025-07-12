# finanzas/services.py
import json
from io import BytesIO
from PIL import Image
from decimal import Decimal

from django.conf import settings
from allauth.socialaccount.models import SocialApp, SocialToken
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.generativeai as genai

# ¡Importamos nuestra nueva función de utilidad!
from .utils import parse_date_safely
from .models import registro_transacciones, TransaccionPendiente, User


class GoogleDriveService:
    # ... (esta clase no cambia)
    """
    Servicio para interactuar con la API de Google Drive.
    Encapsula la creación del cliente y las operaciones con archivos/carpetas.
    """
    def __init__(self, user: User):
        try:
            app = SocialApp.objects.get(provider='google')
            google_token = SocialToken.objects.get(account__user=user, account__provider='google')
            
            creds = Credentials(
                token=google_token.token,
                refresh_token=google_token.token_secret,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=app.client_id,
                client_secret=app.secret
            )
            self.service = build('drive', 'v3', credentials=creds)
        except (SocialToken.DoesNotExist, SocialApp.DoesNotExist) as e:
            raise ConnectionError("No se encontró una cuenta de Google vinculada o la configuración de la App Social.") from e

    def _get_folder_id(self, folder_name: str) -> str | None:
        try:
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            response = self.service.files().list(q=query, spaces='drive', fields='files(id)').execute()
            return response.get('files', [])[0]['id'] if response.get('files') else None
        except HttpError as error:
            print(f"Ocurrió un error al buscar la carpeta '{folder_name}': {error}")
            return None

    def list_files_in_folder(self, folder_name: str, mimetypes: list[str]) -> list[dict]:
        folder_id = self._get_folder_id(folder_name)
        if not folder_id:
            return []
        
        mime_query = " or ".join([f"mimeType='{m}'" for m in mimetypes])
        query = f"'{folder_id}' in parents and ({mime_query}) and trashed=false"
        
        try:
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            return results.get('files', [])
        except HttpError as error:
            print(f"Ocurrió un error al listar archivos: {error}")
            return []

    def get_file_content(self, file_id: str) -> BytesIO:
        request = self.service.files().get_media(fileId=file_id)
        return BytesIO(request.execute())


class GeminiService:
    """
    Servicio para interactuar con la API de Gemini de Google.
    """
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        
        # --- CAMBIO EN EL PROMPT ---
        # Reforzamos la instrucción de la fecha.
        self.prompt = """
            Eres un asistente experto en contabilidad para un sistema de finanzas personales.
            Tu tarea es analizar la imagen de un documento y extraer la información clave con la máxima precisión.
            Devuelve SIEMPRE la respuesta en formato JSON, sin absolutamente ningún texto adicional.

            ### CONTEXTO:
            El usuario ha subido una imagen de un ticket de compra o un comprobante de transferencia.
            Necesito que identifiques el tipo de documento y extraigas los siguientes campos:

            ### FORMATO DE SALIDA ESTRICTO (JSON):
            {
              "tipo_documento": "(TICKET_COMPRA|TRANSFERENCIA|OTRO)",
              "fecha": "YYYY-MM-DD",
              "establecimiento": "Nombre del comercio o beneficiario",
              "descripcion_corta": "Un resumen breve del gasto (ej. 'Renta depto', 'Supermercado', 'Cena con amigos')",
              "total": 0.00,
              "confianza_extraccion": "(ALTA|MEDIA|BAJA)"
            }
            
            ### REGLAS DE EXTRACCIÓN:
            1.  **fecha**: Busca la fecha principal. Si no la encuentras, usa la fecha actual. Formato YYYY-MM-DD.
            2.  **establecimiento**: El nombre principal de la tienda (ej. "Walmart", "Starbucks", "CFE"). Si es una transferencia, el nombre del beneficiario.
            3.  **descripcion_corta**: Si es un ticket con muchos artículos, pon "Supermercado" o "Compra tienda". Si es una transferencia, usa el concepto.
            4.  **total**: El monto TOTAL final. Debe ser un número (float), sin el símbolo de moneda.
            5.  **confianza_extraccion**: Evalúa tu propia certeza.
                - **ALTA**: Si la imagen es clara y todos los campos son obvios.
                - **MEDIA**: Si la imagen es un poco borrosa o un campo es ambiguo.
                - **BAJA**: Si la imagen es muy difícil de leer o faltan datos clave.

            ### EJEMPLOS:
            - **Ejemplo 1 (Ticket claro):**
              { "tipo_documento": "TICKET_COMPRA", "fecha": "2025-07-03", "establecimiento": "La Comer", "descripcion_corta": "Supermercado", "total": 854.50, "confianza_extraccion": "ALTA" }
            - **Ejemplo 2 (Transferencia):**
              { "tipo_documento": "TRANSFERENCIA", "fecha": "2025-07-01", "establecimiento": "N/A", "descripcion_corta": "Digitt002", "total": 7500.00, "confianza_extraccion": "ALTA" }
            - **Ejemplo 3 (Ticket borroso):**
              { "tipo_documento": "TICKET_COMPRA", "fecha": "2025-06-28", "establecimiento": "Restaurante El Sol", "descripcion_corta": "Comida", "total": 450.00, "confianza_extraccion": "MEDIA" }

            ### Nota importante:
            -Quiero que revices bien si es ticket o transferencia, ya que la extracción de datos es diferente. y lo has estado haciendo mal.
            Por ejemplo, en las transferencias estas poniendo el nombre del usuario con el nombre del banco, y no es correcto.
            Lo correcto seria que pongas el concepto de la transferencia, que es lo que el usuario pone en la app de su banco. Y eso normalmente lo pone tal cual en la transferencia.
            Ahora, analiza la siguiente imagen:
        """

    def extract_data_from_image(self, image: Image.Image) -> dict:
        # ... (el resto de la función no cambia)
        response = self.model.generate_content([self.prompt, image])
        print(f"Respuesta de Gemini: {response.text}")
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        
        try:
            print(f"Respuesta de Gemini: {json.loads(cleaned_response)}")
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            print(f"Error: La respuesta de Gemini no es un JSON válido: {cleaned_response}")
            return {
                "error": "Respuesta no válida de la IA",
                "raw_response": cleaned_response
            }


class TransactionService:
    """
    Servicio para manejar la lógica de negocio de las transacciones.
    """
    @staticmethod
    def create_pending_transaction(user: User, data: dict):
        # ... (esta función no cambia)
        if "error" in data:
            print(f"No se creará transacción pendiente debido a un error previo: {data['error']}")
            return None
        
        return TransaccionPendiente.objects.create(
            propietario=user,
            datos_json=data,
            estado='pendiente'
        )

    @staticmethod
    def approve_pending_transaction(ticket_id: int, user: User, cuenta: str, categoria: str, tipo_transaccion: str):
        try:
            ticket = TransaccionPendiente.objects.get(id=ticket_id, propietario=user)
            datos = ticket.datos_json
            print(f"Aprobando ticket: {ticket_id} con datos: {datos}")
            # --- CAMBIO IMPORTANTE AQUÍ ---
            # Usamos nuestra función segura para procesar la fecha.
            # Ya no hay riesgo de que el programa se rompa por un formato incorrecto.
            fecha_segura = parse_date_safely(datos.get("fecha"))

            registro_transacciones.objects.create(
                propietario=user,
                fecha=fecha_segura, # Usamos la fecha limpia y validada
                descripcion=datos.get("descripcion_corta"),
                categoria=categoria,
                monto=Decimal(str(datos.get("total", 0.0))), # Convertir a string primero para mayor precisión con Decimal
                tipo=tipo_transaccion.upper(),
                cuenta_origen=cuenta
            )
            
            ticket.estado = 'aprobada'
            ticket.save()
            return ticket
        except TransaccionPendiente.DoesNotExist:
            return None