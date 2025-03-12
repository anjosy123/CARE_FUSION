function appendMessage(data) {
    const messageContainer = document.getElementById('messageContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${data.is_self ? 'sent' : 'received'}`;
    
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-header">
                <span class="sender">${data.sender}</span>
                <span class="timestamp">${formatTimestamp(data.timestamp)}</span>
            </div>
            <div class="message-text">${data.message}</div>
        </div>
    `;
    
    messageContainer.appendChild(messageDiv);
    scrollToBottom();
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function toggleChatSize() {
    const chatWidget = document.getElementById('teamChat');
    chatWidget.classList.toggle('minimized');
    
    const button = document.querySelector('.btn-minimize i');
    button.className = chatWidget.classList.contains('minimized') ? 
        'fas fa-expand' : 'fas fa-minus';
}

// Add error handling for WebSocket
function handleSocketError(error) {
    console.error('WebSocket Error:', error);
    showErrorMessage('Connection lost. Attempting to reconnect...');
}

function showErrorMessage(message) {
    const messageContainer = document.getElementById('messageContainer');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message-error';
    errorDiv.textContent = message;
    messageContainer.appendChild(errorDiv);
} 