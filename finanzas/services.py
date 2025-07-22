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
import mercadopago
# ¡Importamos nuestra nueva función de utilidad!
from .utils import parse_date_safely
from .models import registro_transacciones, TransaccionPendiente, User
import os # Asegúrate de que User sea el modelo de usuario correcto
import requests
from alpha_vantage.timeseries import TimeSeries
from django.http import JsonResponse

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
        self.prompt_tickets = """
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
            - Quiero que revices bien si es ticket o transferencia, ya que la extracción de datos es diferente. y lo has estado haciendo mal.
            Por ejemplo, en las transferencias estas poniendo el nombre del usuario con el nombre del banco, y no es correcto.
            Lo correcto seria que pongas el concepto de la transferencia, que es lo que el usuario pone en la app de su banco. Y eso normalmente lo pone tal cual en la transferencia.
            - En caso de que el Establecimiento sea Express, sustituyelo por DIDI e igual en caso de que sea Tickets ponlos en mayusculas.

            Ahora, analiza la siguiente imagen:
        """
        self.prompt_inversion = """
            
        """
    def extract_data_from_image(self, image: Image.Image) -> dict:
        # ... (el resto de la función no cambia)
        response = self.model.generate_content([self.prompt_tickets, image])
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
        
    def extract_data_from_inversion(self, image: Image.Image) -> dict:
        """
        Extrae datos de una imagen de inversión utilizando Gemini.
        """
        # Aquí podrías usar un prompt diferente si es necesario
        response = self.model.generate_content([self.prompt_inversion, image])
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        
        try:
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
            tipo_documento = datos.get("tipo_documento")
            
            # Por defecto, usamos la descripción corta
            descripcion_final = datos.get("descripcion_corta", "Sin descripción")
            
            # Si es un ticket de compra, sobrescribimos con el nombre del establecimiento
            if tipo_documento == 'TICKET_COMPRA':
                descripcion_final = datos.get("establecimiento", "Compra sin establecimiento")
            
            # --- FIN DE LA LÓGICA ---
            # --- CAMBIO IMPORTANTE AQUÍ ---
            # Usamos nuestra función segura para procesar la fecha.
            # Ya no hay riesgo de que el programa se rompa por un formato incorrecto.
            fecha_segura = parse_date_safely(datos.get("fecha"))

            registro_transacciones.objects.create(
                propietario=user,
                fecha=fecha_segura, # Usamos la fecha limpia y validada
                #descripcion=datos.get("descripcion_corta", datos.get("establecimiento", "Sin descripción")),
                descripcion=descripcion_final.upper(),
                categoria=categoria,
                monto=Decimal(str(datos.get("total", 0.0))), # Convertir a string primero para mayor precisión con Decimal
                tipo=tipo_transaccion,
                cuenta_origen=cuenta
            )
            
            ticket.estado = 'aprobada'
            ticket.save()
            return ticket
        except TransaccionPendiente.DoesNotExist:
            return None
        
class MercadoPagoService:
    """
    Servicio para manejar la lógica de negocio con Mercado Pago.
    """
    def __init__(self):
        self.sdk = mercadopago.SDK(os.getenv('MERCADOPAGO_ACCESS_TOKEN'))
        self.plan_id = os.getenv('MERCADOPAGO_PLAN_ID')
        if not self.sdk or not self.plan_id:
            raise ValueError("Las credenciales o el Plan ID de Mercado Pago no están configurados en .env")
    
    def crear_link_suscripcion(self, user, back_url: str):
        """
        Construye el link de checkout para la suscripción.
        No requiere una llamada a la API.
        """
        # La URL base para el checkout de suscripciones
        base_url = "https://www.mercadopago.com.mx/subscriptions/checkout"
        
        # Construimos la URL final con el ID de nuestro plan
        checkout_url = f"{base_url}?preapproval_plan_id={self.plan_id}"
        
        # La back_url y el email del usuario se gestionan en la configuración
        # del plan en el panel de Mercado Pago y cuando el usuario inicia sesión allí.
        
        return checkout_url

class StockPriceService:
    """
    Servicio para obtener precios de acciones de Alpha Vantage.
    """
    def __init__(self):
        self.api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if not self.api_key:
            raise ValueError("No se encontró la clave de API de Alpha Vantage en .env")
        self.ts = TimeSeries(key=self.api_key, output_format='json')

    def get_current_price(self, ticker: str):
        """
        Obtiene el precio más reciente para un ticker.
        Ejemplo: 'AAPL' para Apple, 'BIMBOA.MX' para Bimbo en la BMV.
        """
        try:
            data, _ = self.ts.get_quote_endpoint(symbol=ticker)
            current_price = data.get('05. price')
            return float(current_price) if current_price else None
        except Exception as e:
            print(f"Error al llamar a la API de Alpha Vantage para {ticker}: {e}")
            return None
        
    def get_closing_price_for_date(self, ticker: str, target_date):
        """Obtiene el precio de cierre para un ticker en una fecha dada.

        Primero intenta usar la serie diaria completa. Si la fecha no se
        encuentra (por ejemplo, fin de semana o día inhábil), se consulta la
        serie mensual para obtener el cierre del mes correspondiente.
        """
        date_str = target_date.strftime('%Y-%m-%d')
        try:
            daily_data, _ = self.ts.get_daily(symbol=ticker, outputsize='full')
            if date_str in daily_data:
                return float(daily_data[date_str]['4. close'])
        except Exception as e:
            print(f"Error al obtener datos diarios de {ticker}: {e}")

        # Fallback a la serie mensual
        try:
            monthly_data, _ = self.ts.get_monthly(symbol=ticker)
            month_prefix = target_date.strftime('%Y-%m')
            for key, values in monthly_data.items():
                if key.startswith(month_prefix):
                    return float(values['4. close'])
        except Exception as e:
            print(f"Error al obtener datos mensuales de {ticker}: {e}")

        return None 
