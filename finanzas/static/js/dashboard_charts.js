// Espera a que todo el HTML esté cargado
// Espera a que toda la página se cargue
document.addEventListener('DOMContentLoaded', (event) => {
    // Busca todos los elementos de mensaje
    const messageWrapper = document.querySelector('.fixed.top-5.right-5');
        if (messageWrapper) {
            // Espera 5 segundos
            setTimeout(() => {
                // Inicia una transición para hacerlo desaparecer
                messageWrapper.style.transition = 'opacity 0.5s ease';
                messageWrapper.style.opacity = '0';
                    
                // Elimina el elemento por completo después de la transición
                setTimeout(() => messageWrapper.remove(), 500); 
            }, 5000); // 5000 milisegundos = 5 segundos
            }
        });
document.addEventListener('DOMContentLoaded', function() {
    
    // Función para inicializar el gráfico de gastos (Doughnut)
    function initGastosChart() {
        const ctx = document.getElementById('gastosPorCategoriaChart');
        if (!ctx) return; // Si el gráfico no está en la página, no hagas nada

        // Leemos la URL de la API desde el atributo data-url del canvas
        const url = ctx.dataset.url;
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            data: data.data,
                            backgroundColor: [ '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40' ],
                        }]
                    },
                    options: { responsive: true }
                });
            });
    }

    // Función para inicializar el gráfico de inversiones (Line)
    function initInversionesChart() {
        const ctx = document.getElementById('investmentLineChart');
        if (!ctx) return; // Si el gráfico no está en la página, no hagas nada

        // Leemos los datos desde los atributos del canvas
        const labels = JSON.parse(ctx.dataset.labels);
        const data = JSON.parse(ctx.dataset.values);
        
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Capital Invertido Acumulado',
                    data: data,
                    fill: true,
                    borderColor: '#4F46E5',
                    backgroundColor: 'rgba(79, 70, 229, 0.1)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => '$' + value.toLocaleString()
                        }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    // Llamamos a las funciones para que se ejecuten
    initGastosChart();
    initInversionesChart();
});