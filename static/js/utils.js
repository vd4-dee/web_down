// static/js/utils.js
// Common utility functions for notification, select options, etc.

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

function fillSelectOptions(selectElement, optionsList, includeDefault = true, defaultText = "-- Select --", defaultVal = "") {
    if (!selectElement) return;
    const currentValue = selectElement.value;
    selectElement.innerHTML = '';
    if (includeDefault) {
        const defaultOption = document.createElement('option');
        defaultOption.value = defaultVal;
        defaultOption.textContent = defaultText;
        selectElement.appendChild(defaultOption);
    }
    optionsList.forEach(optionValue => {
        const option = document.createElement('option');
        if (typeof optionValue === 'object' && optionValue !== null && optionValue.value !== undefined) {
            option.value = optionValue.value;
            option.textContent = optionValue.text || optionValue.value;
        } else {
            option.value = String(optionValue);
            option.textContent = String(optionValue);
        }
        selectElement.appendChild(option);
    });
    const exists = optionsList.some(opt => (typeof opt === 'object' ? opt.value : String(opt)) === currentValue);
    if (currentValue && exists) {
        selectElement.value = currentValue;
    } else if (!includeDefault && optionsList.length > 0) {
        selectElement.selectedIndex = 0;
    }
}

function formatDate(date) {
    if (!(date instanceof Date) || isNaN(date)) return "";
    try {
        return date.toISOString().split('T')[0];
    } catch (e) {
        return "";
    }
}

function addStatusMessage(targetDiv, message, type = 'log') {
    if (!targetDiv) return;
    const p = document.createElement('p');
    p.textContent = message;
    p.classList.add(`${type}-message`);
    const defaultMsg = targetDiv.querySelector('p.subtext');
    if (defaultMsg && targetDiv.children.length === 1 && defaultMsg.textContent.includes('No activity yet')) {
        targetDiv.innerHTML = '';
    }
    targetDiv.appendChild(p);
    targetDiv.scrollTop = targetDiv.scrollHeight;
}

function clearStatusMessages(targetDiv) {
    if (targetDiv) {
        targetDiv.innerHTML = '<p class="subtext">No activity yet.</p>';
    }
}
