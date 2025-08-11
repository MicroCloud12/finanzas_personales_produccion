import time
from decimal import Decimal
from django.core.management.base import BaseCommand
from finanzas.models import inversiones
from finanzas.services import StockPriceService

class Command(BaseCommand):
    help = 'Actualiza el precio actual de todas las inversiones en la base de datos usando la API de Alpha Vantage.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('🚀 Iniciando la actualización de precios de inversiones...'))
        
                # Obtenemos todas las inversiones y los tickers únicos
        investment_qs = inversiones.objects.exclude(emisora_ticker__isnull=True).exclude(emisora_ticker="")

        if not investment_qs:
            self.stdout.write(self.style.WARNING('No se encontraron inversiones de tipo "Acción" para actualizar.'))
            return

        price_service = StockPriceService()
        updated_count = 0
        
        # Iteramos sobre cada inversión
        #for investment in investment_list:
        #    ticker = investment.emisora_ticker
        #    if not ticker:
        #        continue # Saltamos si no tiene un ticker
        unique_tickers = investment_qs.values_list("emisora_ticker", flat=True).distinct()

        for ticker in unique_tickers:
            self.stdout.write(f'  - Obteniendo precio para {ticker}...', ending='')
            new_price_float = price_service.get_current_price(ticker)
            
            if new_price_float is not None:
                decimal_price = Decimal(str(new_price_float))
                investments_with_ticker = investment_qs.filter(emisora_ticker=ticker)
                for investment in investments_with_ticker:
                    investment.precio_actual_titulo = decimal_price
                    investment.save()  # Recalcula los campos dependientes
                    updated_count += 1
                
                self.style.SUCCESS(
                        f" ¡Actualizado a ${new_price_float:.2f}!"
                    )
                
            else:
                self.stdout.write(self.style.ERROR(' ¡Falló!'))

            # La API gratuita de Alpha Vantage tiene un límite de 5 llamadas por minuto.
            # Añadimos una pausa de 15 segundos para no exceder el límite.
            time.sleep(15)

        f"\n✅ Proceso completado. Se actualizaron {updated_count} de {investment_qs.count()} inversiones."