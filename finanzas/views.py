from decimal import Decimal
from datetime import datetime
from django.db.models import Sum
from django.http import JsonResponse
from .forms import TransaccionesForm
from .models import registro_transacciones
from django.contrib.auth import login
from django.shortcuts import render, redirect
from .forms import FormularioRegistroPersonalizado
from django.contrib.auth.decorators import login_required
import logging
from .tasks import procesar_tickets_drive # Asegúrate de que esta línea esté al inicio
from django.contrib import messages
from allauth.socialaccount.models import SocialToken
from .models import registro_transacciones, TransaccionPendiente
from decimal import Decimal
from datetime import datetime
from django.http import JsonResponse
from celery.result import AsyncResult
from django.urls import reverse

logger = logging.getLogger(__name__)


def home(request):
    return render(request, 'index.html')

def iniciosesion(request):
    return render(request, 'dashboard.html')

def registro(request):
    if request.method == 'POST':
        form = FormularioRegistroPersonalizado(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard') # Redirigimos a la URL con nombre 'inicio'
    # Si el método NO es POST (es GET, una visita normal)...
    else:
        # Creamos un formulario vacío
        form = FormularioRegistroPersonalizado()
    
    # Preparamos el contexto y renderizamos la plantilla
    # Esta parte se ejecuta en ambos casos: GET o POST inválido
    context = {'form': form}
    return render(request, 'registro.html', context)

@login_required
def vista_dashboard(request):
 # Obtenemos el año y mes actual como punto de partida
    current_year = datetime.now().year
    current_month = datetime.now().month

    # Revisamos si el usuario está filtrando por un mes y año específicos
    # request.GET.get(...) busca un parámetro en la URL, ej: /dashboard?year=2024&month=5
    year = int(request.GET.get('year', current_year))
    month = int(request.GET.get('month', current_month))

    # Filtramos las transacciones por el usuario logueado, año y mes
    transacciones = registro_transacciones.objects.filter(
        propietario=request.user, 
        fecha__year=year, 
        fecha__month=month
    )
    
    # Obtenemos los diccionarios de la base de datos
    # La línea completa y corregida
    ingresos = transacciones.filter(tipo='INGRESO').exclude(categoria='Ahorro').filter(cuenta_origen = 'Efectivo Quincena').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    gastos = transacciones.filter(tipo='GASTO').exclude(categoria='Ahorro').filter(cuenta_origen = 'Efectivo Quincena').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    ahorro_total = transacciones.filter(tipo='INGRESO').filter(categoria='Ahorro').filter(cuenta_origen = 'Cuenta Ahorro').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    proviciones = transacciones.filter(tipo='GASTO').exclude(categoria='Ahorro').filter(cuenta_origen = 'Cuenta Ahorro').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    transferencias = transacciones.filter(tipo='TRANSFERENCIA').exclude(categoria='Ahorro').exclude(categoria='Ahorro').filter(cuenta_origen = 'Efectivo Quincena').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    '''
    # --- Registro de datos de depuración ---
    logger.debug("--- INICIANDO DEPURACIÓN DE VALORES FINALES ---")
    logger.debug("Valor de 'ingresos': %s (Tipo: %s)", ingresos, type(ingresos))
    logger.debug("Valor de 'gastos': %s (Tipo: %s)", gastos, type(gastos))
    logger.debug("---------------------------------------------")
    '''
    # Esta es la línea que da el error
    balance = ingresos - gastos
    disponible_banco = ingresos - gastos - transferencias
    ahorro = ahorro_total - proviciones
    # Preparamos el contexto para enviarlo a la plantilla
    context = {
        'ingresos': ingresos,
        'gastos': gastos,
        'balance': balance,
        'transferencias':transferencias,
        'disponible_banco':disponible_banco,
        'ahorro': ahorro,
        'selected_year': year,
        'selected_month': month,
        'years': range(current_year, current_year - 5, -1), # Para el dropdown de años
        'months': range(1, 13) # Para el dropdown de meses
    }

    return render(request, 'dashboard.html', context)

@login_required
# Create your views here.
def crear_transacciones(request):
    if request.method == 'POST':
        form = TransaccionesForm(request.POST)

        if form.is_valid():
            # --- AQUÍ ESTÁ LA LÓGICA CORREGIDA ---

            # 1. Crea el objeto en memoria, pero NO lo guardes en la DB todavía.
            nueva_transaccion = form.save(commit=False)

            # 2. Asigna el usuario actual (que está en request.user) como propietario.
            #    El decorador @login_required se asegura de que request.user siempre exista.
            nueva_transaccion.propietario = request.user

            # 3. Ahora sí, guarda el objeto completo en la base de datos.
            nueva_transaccion.save()

            # Redirigimos al dashboard.
            return redirect('dashboard')
    else: 
        form = TransaccionesForm()

    context = {
        'form': form
    }

    return render(request, 'transacciones.html', context)

@login_required
def lista_transacciones(request):
    # La lógica de filtros es idéntica a la del dashboard
    current_year = datetime.now().year
    current_month = datetime.now().month
    year = int(request.GET.get('year', current_year))
    month = int(request.GET.get('month', current_month))

    # Obtenemos las transacciones del mes y las ordenamos por fecha
    transacciones_del_mes = registro_transacciones.objects.filter(
        propietario=request.user,
        fecha__year=year,
        fecha__month=month
    ).order_by('-fecha') # order_by('-fecha') las ordena de más reciente a más antigua

    context = {
        'transacciones': transacciones_del_mes
    }

    return render(request, 'lista_transacciones.html', context)

@login_required
def datos_gastos_categoria(request):
    # La lógica de filtros es la misma que en el dashboard
    year = int(request.GET.get('year', datetime.now().year))
    month = int(request.GET.get('month', datetime.now().month))

    # ¡AQUÍ ESTÁ LA NUEVA MAGIA DEL ORM!
    # Agrupamos las transacciones por 'categoria' y sumamos el 'monto' de cada una.
    gastos_por_categoria = TransaccionesForm.gastos_por_categoria = registro_transacciones.objects.filter(
        propietario=request.user,
        tipo='GASTO',
        fecha__year=year,
        fecha__month=month
    ).values(
        'categoria'  # Agrupar por este campo
    ).annotate(
        total=Sum('monto') # Para cada grupo, sumar los montos y llamar al resultado 'total'
    ).order_by('-total') # Ordenar de mayor a menor gasto

    # Preparamos los datos en un formato simple para JavaScript
    data = {
        'labels': [item['categoria'] for item in gastos_por_categoria],
        'data': [item['total'] for item in gastos_por_categoria],
    }

    # Devolvemos los datos como una respuesta JSON
    return JsonResponse(data)

@login_required
def datos_flujo_dinero(request):
    # La lógica de filtros es idéntica
    year = int(request.GET.get('year', datetime.now().year))
    month = int(request.GET.get('month', datetime.now().month))

    # Obtenemos las transacciones del mes
    transacciones_del_mes = registro_transacciones.objects.filter(
        propietario=request.user,
        fecha__year=year,
        fecha__month=month
    )

    # Calculamos el total de ingresos y gastos para ese mes
    # Usamos la misma lógica de exclusión que en nuestro dashboard
    ingresos = transacciones_del_mes.filter(tipo='INGRESO').exclude(categoria='Ahorro').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    gastos = transacciones_del_mes.filter(tipo='GASTO').exclude(categoria='Ahorro').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    # Preparamos los datos en un formato simple para el gráfico
    data = {
        'labels': ['Ingresos del Mes', 'Gastos del Mes'],
        'data': [ingresos, gastos],
    }

    return JsonResponse(data)


@login_required
def vista_procesamiento_automatico(request):
    """
    Muestra la página dedicada para el procesamiento de tickets desde Drive.
    """
    return render(request, 'procesamiento_automatico.html')

@login_required
def iniciar_procesamiento_drive(request):
    """
    Inicia el proceso de descubrimiento y procesamiento paralelo de tickets.
    """
    try:
        google_token = SocialToken.objects.get(account__user=request.user, account__provider='google')
        token = google_token.token
        refresh_token = google_token.token_secret

        # Llamamos a la nueva tarea principal
        task = procesar_tickets_drive.delay(request.user.id, token, refresh_token)
        
        return JsonResponse({"task_id": task.id}, status=202)

    except SocialToken.DoesNotExist:
        return JsonResponse({"error": "No se encontró una cuenta de Google vinculada."}, status=400)


@login_required
def revisar_tickets(request):
    tickets_pendientes = TransaccionPendiente.objects.filter(propietario=request.user, estado='pendiente')
    return render(request, 'revisar_tickets.html', {'tickets': tickets_pendientes})

@login_required
def aprobar_ticket(request, ticket_id):
    if request.method == 'POST': # Solo si se envía el formulario
        ticket = TransaccionPendiente.objects.get(id=ticket_id, propietario=request.user)
        datos = ticket.datos_json
        
        # Obtenemos la cuenta del formulario que acabamos de enviar
        cuenta_seleccionada = request.POST.get('cuenta_origen')
        categoria_seleccionada = request.POST.get('categoria') # <-- NUEVA LÍNEA
        
        registro_transacciones.objects.create(
            propietario=request.user,
            fecha=datetime.strptime(datos.get("fecha"), "%Y-%m-%d").date(),
            descripcion=datos.get("descripcion", datos.get("establecimiento", "Sin descripción")),
            categoria=categoria_seleccionada, # <-- USAMOS LA CATEGORÍA SELECCIONADA
            monto=Decimal(datos.get("total", 0.0)),
            tipo='GASTO',
            cuenta_origen=cuenta_seleccionada # ¡Usamos la cuenta seleccionada!
        )
        
        ticket.estado = 'aprobada'
        ticket.save()
        
    return redirect('revisar_tickets')

# --- AÑADE ESTA NUEVA VISTA ---
@login_required
def get_task_status(request, task_id):
    """
    Consulta y devuelve el estado de una tarea de Celery.
    """
    task_result = AsyncResult(task_id)
    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result if task_result.ready() else None
    }
    return JsonResponse(result, status=200)

@login_required
def rechazar_ticket(request, ticket_id):
    ticket = TransaccionPendiente.objects.get(id=ticket_id, propietario=request.user)
    ticket.estado = 'rechazada'
    ticket.save()
    return redirect('revisar_tickets')