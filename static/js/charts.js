/**
 * CRISS - Admin Analytics & Chart.js Integration
 * Fetches real database metrics dynamically via REST APIs
 */

document.addEventListener('DOMContentLoaded', function () {
    initUtilizationChart();
    initUnmetDemandChart();
    initInventoryBreakdownChart();
});

// 1. Resource Utilization by Category (Bar Chart)
function initUtilizationChart() {
    const canvas = document.getElementById('utilizationChart');
    if (!canvas) return;

    fetch('/api/stats/utilization-by-category')
        .then(response => response.json())
        .then(data => {
            const ctx = canvas.getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [
                        {
                            label: 'Total Units',
                            data: data.total,
                            backgroundColor: 'rgba(30, 41, 59, 0.75)',
                            borderColor: '#1e293b',
                            borderWidth: 1,
                            borderRadius: 4
                        },
                        {
                            label: 'Active (Loan / Reserved)',
                            data: data.active,
                            backgroundColor: 'rgba(13, 148, 136, 0.85)',
                            borderColor: '#0d9488',
                            borderWidth: 1,
                            borderRadius: 4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { precision: 0 },
                            grid: { color: '#f1f5f9' }
                        },
                        x: {
                            grid: { display: false }
                        }
                    },
                    plugins: {
                        legend: { position: 'top' },
                        tooltip: {
                            callbacks: {
                                afterBody: function (context) {
                                    const index = context[0].dataIndex;
                                    return 'Utilization Rate: ' + data.utilization_pct[index] + '%';
                                }
                            }
                        }
                    }
                }
            });
        })
        .catch(err => console.error('Error loading utilization chart:', err));
}

// 2. Unmet Demand Rate by Category (Doughnut / Polar Chart)
function initUnmetDemandChart() {
    const canvas = document.getElementById('unmetDemandChart');
    if (!canvas) return;

    fetch('/api/stats/unmet-demand')
        .then(response => response.json())
        .then(data => {
            const ctx = canvas.getContext('2d');
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.labels,
                    datasets: [{
                        data: data.unfulfilled,
                        backgroundColor: [
                            '#ef4444', // Red
                            '#f59e0b', // Amber
                            '#0d9488', // Teal
                            '#6366f1', // Indigo
                            '#ec4899', // Pink
                            '#10b981'  // Emerald
                        ],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom' },
                        tooltip: {
                            callbacks: {
                                label: function (context) {
                                    const index = context.dataIndex;
                                    const count = data.unfulfilled[index];
                                    const rate = data.rates[index];
                                    return ` ${data.labels[index]}: ${count} unfulfilled (${rate}% unmet rate)`;
                                }
                            }
                        }
                    }
                }
            });
        })
        .catch(err => console.error('Error loading unmet demand chart:', err));
}

// 3. Physical Inventory Breakdown (Pie Chart)
function initInventoryBreakdownChart() {
    const canvas = document.getElementById('inventoryPieChart');
    if (!canvas) return;

    fetch('/api/stats/inventory-breakdown')
        .then(response => response.json())
        .then(res => {
            const statusMap = res.data;
            const labels = ['Available', 'On Loan', 'Reserved', 'Maintenance', 'Retired'];
            const dataCounts = [
                statusMap['available'] || 0,
                statusMap['on_loan'] || 0,
                statusMap['reserved'] || 0,
                statusMap['maintenance'] || 0,
                statusMap['retired'] || 0
            ];

            const ctx = canvas.getContext('2d');
            new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: labels,
                    datasets: [{
                        data: dataCounts,
                        backgroundColor: [
                            '#10b981', // green
                            '#0284c7', // blue
                            '#f59e0b', // yellow/amber
                            '#a855f7', // purple
                            '#94a3b8'  // slate gray
                        ],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'right' }
                    }
                }
            });
        })
        .catch(err => console.error('Error loading inventory breakdown chart:', err));
}
