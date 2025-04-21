// static/js/em_send.js
// Logic for bulk email sending panel
document.addEventListener('DOMContentLoaded', () => {
    const bulkEmailForm = document.getElementById('bulk-email-form');
    const sendEmailButton = document.getElementById('send-email-button');
    const emailLoadingIndicator = document.getElementById('email-loading-indicator');
    const emailStatusMessagesDiv = document.getElementById('email-status-messages');

    function addStatusMessage(targetDiv, message, type = 'log') {
        if (!targetDiv) return;
        const p = document.createElement('p');
        p.textContent = message;
        p.classList.add(`${type}-message`);
        targetDiv.appendChild(p);
        targetDiv.scrollTop = targetDiv.scrollHeight;
    }

    function clearStatusMessages(targetDiv) {
        if (targetDiv) {
            targetDiv.innerHTML = '<p class="subtext">No activity yet.</p>';
        }
    }

    if (bulkEmailForm && sendEmailButton && emailLoadingIndicator && emailStatusMessagesDiv) {
        bulkEmailForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            sendEmailButton.disabled = true;
            emailLoadingIndicator.style.display = 'inline-block';
            clearStatusMessages(emailStatusMessagesDiv);
            addStatusMessage(emailStatusMessagesDiv, "Preparing to send emails...", 'info');
            // Simulate sending
            await new Promise(resolve => setTimeout(resolve, 1500));
            addStatusMessage(emailStatusMessagesDiv, "Emails sent successfully (simulation).", 'success');
            sendEmailButton.disabled = false;
            emailLoadingIndicator.style.display = 'none';
            bulkEmailForm.reset();
        });
    }
});
