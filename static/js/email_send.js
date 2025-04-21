// email_send.js
// Chứa toàn bộ logic gửi email tách từ script.js

document.addEventListener('DOMContentLoaded', () => {
    const bulkEmailForm = document.getElementById('bulk-email-form');
    const sendEmailButton = document.getElementById('send-email-button');
    const emailLoadingIndicator = document.getElementById('email-loading-indicator');
    const emailStatusMessagesDiv = document.getElementById('email-status-messages');

    function showNotification(message, type = 'info', duration = 4000) {
        const notificationPopup = document.getElementById('notification');
        const notificationMessage = document.getElementById('notification-message');
        if (!notificationPopup || !notificationMessage) return;
        notificationMessage.textContent = message;
        notificationPopup.className = `notification ${type}`;
        notificationPopup.style.display = 'block';
        setTimeout(() => {
            notificationPopup.style.display = 'none';
        }, duration);
    }

    if (bulkEmailForm && sendEmailButton && emailLoadingIndicator && emailStatusMessagesDiv) {
        bulkEmailForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            sendEmailButton.disabled = true;
            emailLoadingIndicator.style.display = 'inline-block';
            emailStatusMessagesDiv.innerHTML = '';
            const formData = new FormData(bulkEmailForm);
            try {
                await new Promise(resolve => setTimeout(resolve, 1500));
                emailStatusMessagesDiv.innerHTML = '<div class="status-message success">Emails sent successfully (simulation).</div>';
                showNotification('Bulk emails sent.', 'success');
                bulkEmailForm.reset();
            } catch (error) {
                emailStatusMessagesDiv.innerHTML = `<div class='status-message error'>Error: ${error.message}</div>`;
                showNotification('Error: ' + error.message, 'error');
            } finally {
                sendEmailButton.disabled = false;
                emailLoadingIndicator.style.display = 'none';
            }
        });
    }
});
