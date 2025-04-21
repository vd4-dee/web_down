// static/js/dl_settings.js
// Logic for download settings panel (advanced settings)
document.addEventListener('DOMContentLoaded', () => {
    const otpSecretInput = document.getElementById('otp-secret');
    const driverPathInput = document.getElementById('driver-path');
    const downloadBasePathInput = document.getElementById('download-base-path');
    const saveAdvancedSettingsButton = document.getElementById('save-advanced-settings');
    const notificationPopup = document.getElementById('notification');
    const notificationMessage = document.getElementById('notification-message');
    let notificationTimeout = null;

    function showNotification(message, type = 'info', duration = 4000) {
        if (!notificationPopup || !notificationMessage) return;
        if (notificationTimeout) clearTimeout(notificationTimeout);
        notificationMessage.textContent = message;
        notificationPopup.className = 'notification show';
        if (type === 'success') {
            notificationPopup.classList.add('success');
        } else if (type === 'error') {
            notificationPopup.classList.add('error');
        } else if (type === 'warning') {
            notificationPopup.classList.add('warning');
        }
        notificationTimeout = setTimeout(() => {
            notificationPopup.classList.remove('show');
        }, duration);
    }

    if (saveAdvancedSettingsButton) {
        saveAdvancedSettingsButton.addEventListener('click', async () => {
            const settings = {
                otp_secret: otpSecretInput ? otpSecretInput.value : undefined,
                driver_path: driverPathInput ? driverPathInput.value : undefined,
                download_base_path: downloadBasePathInput ? downloadBasePathInput.value : undefined
            };
            // TODO: Call backend API to save settings if implemented
            showNotification("Advanced settings saved (simulation).", "success");
        });
    }

    // Show/hide OTP Secret
    const toggleOtpBtnAdv = document.getElementById('toggle-otp-visibility-adv');
    if (toggleOtpBtnAdv && otpSecretInput) {
        toggleOtpBtnAdv.addEventListener('click', function() {
            const isHidden = otpSecretInput.type === 'password';
            otpSecretInput.type = isHidden ? 'text' : 'password';
            toggleOtpBtnAdv.innerHTML = `<i class="fas fa-${isHidden ? 'eye-slash' : 'eye'}"></i>`;
        });
    }
});
