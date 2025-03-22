// Form validation and submission handling
document.addEventListener('DOMContentLoaded', function() {
    // Handle farm data form submission
    const farmDataForm = document.getElementById('farmDataForm');
    if (farmDataForm) {
        farmDataForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Basic form validation
            const location = document.getElementById('location').value;
            const landSize = document.getElementById('land_size').value;
            const soilType = document.getElementById('soil_type').value;
            const cropType = document.getElementById('crop_type').value;
            const lastYield = document.getElementById('last_yield').value;

            if (!location || !landSize || !soilType || !cropType || !lastYield) {
                alert('Please fill in all fields');
                return;
            }

            if (landSize <= 0) {
                alert('Land size must be greater than 0');
                return;
            }

            if (lastYield < 0) {
                alert('Last yield cannot be negative');
                return;
            }

            // Submit form
            fetch(farmDataForm.action, {
                method: 'POST',
                body: new FormData(farmDataForm),
            })
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    // Show success message
                    const alert = document.createElement('div');
                    alert.className = 'alert alert-success';
                    alert.textContent = data.message;
                    farmDataForm.insertAdjacentElement('beforebegin', alert);

                    // Reload page after 2 seconds
                    setTimeout(() => {
                        location.reload();
                    }, 2000);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                const alert = document.createElement('div');
                alert.className = 'alert alert-danger';
                alert.textContent = 'An error occurred while submitting the form.';
                farmDataForm.insertAdjacentElement('beforebegin', alert);
            });
        });
    }

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Handle modal events
    const farmerModals = document.querySelectorAll('.modal');
    farmerModals.forEach(modal => {
        modal.addEventListener('show.bs.modal', function(event) {
            // You can add custom logic here when modal is shown
        });

        modal.addEventListener('hidden.bs.modal', function(event) {
            // Clean up any dynamic content when modal is hidden
        });
    });

    // Add animation to progress bars
    const progressBars = document.querySelectorAll('.progress-bar');
    progressBars.forEach(bar => {
        bar.style.width = '0%';
        setTimeout(() => {
            bar.style.width = bar.getAttribute('aria-valuenow') + '%';
        }, 100);
    });
}); 