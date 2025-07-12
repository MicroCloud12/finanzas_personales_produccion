# finanzas/views.py
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
from .tasks import process_drive_tickets # Tarea principal actualizada
from .models import TransaccionPendiente
from celery.result import AsyncResult
from .services import TransactionService # Importamos el servicio de transacciones
from django.http import JsonResponse
from celery.result import AsyncResult, GroupResult

logger = logging.getLogger(__name__)


def home(request):
    return render(request, 'index.html')

# ... (tus vistas home, iniciosesion, registro, vista_dashboard, etc. se mantienen igual) ...
# ... (solo mostraremos las vistas que cambian) ...


@login_required
def iniciar_procesamiento_drive(request):
    """
    Inicia el proceso de descubrimiento y procesamiento paralelo de tickets.
    """
    try:
        # La lógica de token ahora está dentro del servicio, pero la vista
        # debe asegurarse de que la tarea se inicie.
        task = process_drive_tickets.delay(request.user.id)
        return JsonResponse({"task_id": task.id}, status=202)
    except Exception as e:
        # Captura errores generales durante el inicio de la tarea
        return JsonResponse({"error": f"No se pudo iniciar la tarea: {str(e)}"}, status=400)


@login_required
def aprobar_ticket(request, ticket_id):
    if request.method == 'POST':
        cuenta_seleccionada = request.POST.get('cuenta_origen')
        categoria_seleccionada = request.POST.get('categoria')
        tipo_seleccionado = request.POST.get('tipo', 'GASTO') # Valor por defecto 'GASTO'
        # Usamos el servicio para manejar la aprobación
        TransactionService.approve_pending_transaction(
            ticket_id=ticket_id,
            user=request.user,
            cuenta=cuenta_seleccionada,
            categoria=categoria_seleccionada,
            tipo_transaccion=tipo_seleccionado
        )
        
    return redirect('revisar_tickets')


# ... (el resto de tus vistas como `rechazar_ticket`, `get_task_status`, etc. se mantienen igual) ...

# El resto de vistas (home, registro, dashboard, etc.) no necesitan cambios.
# Solo hemos modificado las que interactúan directamente con el proceso de tickets.
# Aquí irían el resto de tus vistas sin modificar
def iniciosesion(request):
    return render(request, 'dashboard.html')

def registro(request):
    if request.method == 'POST':
        form = FormularioRegistroPersonalizado(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = FormularioRegistroPersonalizado()
    
    context = {'form': form}
    return render(request, 'registro.html', context)

@login_required
def vista_dashboard(request):
    current_year = datetime.now().year
    current_month = datetime.now().month
    year = int(request.GET.get('year', current_year))
    month = int(request.GET.get('month', current_month))
    transacciones = registro_transacciones.objects.filter(
        propietario=request.user, 
        fecha__year=year, 
        fecha__month=month
    )
    ingresos = transacciones.filter(tipo='INGRESO').exclude(categoria='Ahorro').filter(cuenta_origen = 'Efectivo Quincena').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    gastos = transacciones.filter(tipo='GASTO').exclude(categoria='Ahorro').filter(cuenta_origen = 'Efectivo Quincena').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    ahorro_total = transacciones.filter(tipo='INGRESO').filter(categoria='Ahorro').filter(cuenta_origen = 'Cuenta Ahorro').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    proviciones = transacciones.filter(tipo='GASTO').exclude(categoria='Ahorro').filter(cuenta_origen = 'Cuenta Ahorro').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    transferencias = transacciones.filter(tipo='TRANSFERENCIA').exclude(categoria='Ahorro').exclude(categoria='Ahorro').filter(cuenta_origen = 'Efectivo Quincena').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    balance = ingresos - gastos
    disponible_banco = ingresos - gastos - transferencias
    ahorro = ahorro_total - proviciones
    context = {
        'ingresos': ingresos,
        'gastos': gastos,
        'balance': balance,
        'transferencias':transferencias,
        'disponible_banco':disponible_banco,
        'ahorro': ahorro,
        'selected_year': year,
        'selected_month': month,
        'years': range(current_year, current_year - 5, -1),
        'months': range(1, 13)
    }
    return render(request, 'dashboard.html', context)

@login_required
def crear_transacciones(request):
    if request.method == 'POST':
        form = TransaccionesForm(request.POST)
        if form.is_valid():
            nueva_transaccion = form.save(commit=False)
            nueva_transaccion.propietario = request.user
            nueva_transaccion.save()
            return redirect('dashboard')
    else: 
        form = TransaccionesForm()
    context = {'form': form}
    return render(request, 'transacciones.html', context)

@login_required
def lista_transacciones(request):
    current_year = datetime.now().year
    current_month = datetime.now().month
    year = int(request.GET.get('year', current_year))
    month = int(request.GET.get('month', current_month))
    transacciones_del_mes = registro_transacciones.objects.filter(
        propietario=request.user,
        fecha__year=year,
        fecha__month=month
    ).order_by('-fecha')
    context = {'transacciones': transacciones_del_mes}
    return render(request, 'lista_transacciones.html', context)

@login_required
def datos_gastos_categoria(request):
    year = int(request.GET.get('year', datetime.now().year))
    month = int(request.GET.get('month', datetime.now().month))
    gastos_por_categoria = registro_transacciones.objects.filter(
        propietario=request.user,
        tipo='GASTO',
        fecha__year=year,
        fecha__month=month
    ).values('categoria').annotate(total=Sum('monto')).order_by('-total')
    data = {
        'labels': [item['categoria'] for item in gastos_por_categoria],
        'data': [item['total'] for item in gastos_por_categoria],
    }
    return JsonResponse(data)

@login_required
def datos_flujo_dinero(request):
    year = int(request.GET.get('year', datetime.now().year))
    month = int(request.GET.get('month', datetime.now().month))
    transacciones_del_mes = registro_transacciones.objects.filter(
        propietario=request.user,
        fecha__year=year,
        fecha__month=month
    )
    ingresos = transacciones_del_mes.filter(tipo='INGRESO').exclude(categoria='Ahorro').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    gastos = transacciones_del_mes.filter(tipo='GASTO').exclude(categoria='Ahorro').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    data = {
        'labels': ['Ingresos del Mes', 'Gastos del Mes'],
        'data': [ingresos, gastos],
    }
    return JsonResponse(data)


@login_required
def vista_procesamiento_automatico(request):
    return render(request, 'procesamiento_automatico.html')

@login_required
def revisar_tickets(request):
    tickets_pendientes = TransaccionPendiente.objects.filter(propietario=request.user, estado='pendiente')
    return render(request, 'revisar_tickets.html', {'tickets': tickets_pendientes})

# VISTA 1: Solo para la tarea inicial
@login_required
def get_initial_task_result(request, task_id):
    """
    Consulta el resultado de la tarea "lanzadora". Su único trabajo es
    esperar a que esta tarea termine para devolver el ID del grupo.
    """
    try:
        task_result = AsyncResult(task_id)
        if task_result.ready():
            return JsonResponse({"status": "SUCCESS", "result": task_result.result})
        else:
            return JsonResponse({"status": "PENDING"})
    except Exception as e:
        logger.error(f"Error en get_initial_task_result: {e}")
        return JsonResponse({"status": "FAILURE", "info": str(e)}, status=500)

# VISTA 2: Solo para el grupo de tareas
@login_required
def get_group_status(request, group_id):
    """
    Consulta el estado de un GroupResult para reportar el progreso.
    """
    try:
        group_result = GroupResult.restore(group_id)
        if not group_result:
             return JsonResponse({"status": "PENDING"})

        if group_result.ready():
            return JsonResponse({"status": "COMPLETED"})
        else:
            total = len(group_result)
            completed = group_result.completed_count()
            return JsonResponse({
                "status": "PROGRESS",
                "total": total,
                "completed": completed,
                "progress": int((completed / total) * 100) if total > 0 else 0
            })
    except Exception as e:
        logger.error(f"Error en get_group_status: {e}")
        return JsonResponse({"status": "FAILURE", "info": str(e)}, status=500)
     
@login_required
def rechazar_ticket(request, ticket_id):
    ticket = TransaccionPendiente.objects.get(id=ticket_id, propietario=request.user)
    ticket.estado = 'rechazada'
    ticket.save()
    return redirect('revisar_tickets')