document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('evalForm');
    if(form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Toggle UI states
            document.getElementById('btnText').classList.add('d-none');
            document.getElementById('btnSpinner').classList.remove('d-none');
            document.getElementById('submitBtn').disabled = true;
            document.getElementById('resultsArea').classList.add('d-none');
            document.getElementById('loadingState').classList.remove('d-none');

            const formData = new FormData(form);

            try {
                const response = await fetch('/api/evaluate', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if(data.status === 'Success') {
                    document.getElementById('countryName').innerText = data.country + ' Framework';
                    document.getElementById('gaugeChart').innerHTML = data.charts.gauge;
                    document.getElementById('summaryText').innerHTML = data.summary;
                    document.getElementById('barChart').innerHTML = data.charts.bar;
                    
                    document.getElementById('loadingState').classList.add('d-none');
                    document.getElementById('resultsArea').classList.remove('d-none');
                } else {
                    alert('Evaluation failed: ' + data.message);
                    document.getElementById('loadingState').classList.add('d-none');
                }
            } catch (error) {
                alert('Server connection error.');
                document.getElementById('loadingState').classList.add('d-none');
            } finally {
                document.getElementById('btnText').classList.remove('d-none');
                document.getElementById('btnSpinner').classList.add('d-none');
                document.getElementById('submitBtn').disabled = false;
            }
        });
    }
});
