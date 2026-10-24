/**
 * CRISS - Campus Resource Intelligence & Sharing System
 * Client-Side Interactivity & Notification Helper
 */

document.addEventListener('DOMContentLoaded', function () {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 6000);
    });

    // Tooltip initialization
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Confirmation for cancellations / state changes
    const confirmButtons = document.querySelectorAll('.btn-confirm-action');
    confirmButtons.forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            const message = btn.getAttribute('data-confirm-message') || 'Are you sure you wish to proceed?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
});

// Quick credential filler for demo accounts
function fillLogin(email, password) {
    const emailField = document.getElementById('login-email');
    const passwordField = document.getElementById('login-password');
    if (emailField && passwordField) {
        emailField.value = email;
        passwordField.value = password;
        emailField.focus();
    }
}
