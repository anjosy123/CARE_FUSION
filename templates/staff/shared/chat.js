function toggleChat() {
    const chatBody = document.getElementById('chatBody');
    chatBody.style.display = chatBody.style.display === 'none' ? 'flex' : 'none';
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage(event);
    }
}

function sendMessage(event) {
    event.preventDefault();
    const messageInput = document.querySelector('.message-input');
    const message = messageInput.value.trim();
    
    if (message) {
        chatSocket.send(JSON.stringify({
            'type': 'message',
            'message': message,
            'team': teamId
        }));
        messageInput.value = '';
    }
}

// Initialize WebSocket connection
function initializeWebSocket() {
    const ws_scheme = window.location.protocol === "https:" ? "wss" : "ws";
    const chatSocket = new WebSocket(
        ws_scheme + '://' + window.location.host + '/ws/staff/' + staffId + '/'
    );
    
    chatSocket.onmessage = handleMessage;
    chatSocket.onclose = handleSocketClose;
    
    return chatSocket;
}

function handleMessage(event) {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'message':
            appendMessage(data);
            break;
        case 'typing_start':
            showTypingIndicator(data.sender);
            break;
        case 'typing_stop':
            hideTypingIndicator();
            break;
    }
}

function handleSocketClose() {
    console.log('Chat connection closed. Attempting to reconnect...');
    setTimeout(initializeWebSocket, 3000);
} 