let chatSocket = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

function initializeChat() {
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        return; // Already connected
    }
    
    const ws_scheme = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${ws_scheme}://${window.location.host}/ws/patient/chat/`;
    console.log('Connecting to:', wsUrl);
    
    chatSocket = new WebSocket(wsUrl);
    
    chatSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        handleMessage(data);
    };
    
    chatSocket.onopen = function() {
        console.log('Chat connection established');
        reconnectAttempts = 0;
        clearErrorMessages();
    };
    
    chatSocket.onclose = function(e) {
        console.log('Chat socket closed unexpectedly');
        handleSocketClose();
    };

    chatSocket.onerror = function(e) {
        console.error('WebSocket error:', e);
        handleSocketError(e);
    };
}

function handleMessage(data) {
    if (data.type === 'typing_indicator') {
        const typingIndicator = document.getElementById('typingIndicator');
        typingIndicator.style.display = data.show ? 'block' : 'none';
    } else if (data.type === 'chat_message') {
        document.getElementById('typingIndicator').style.display = 'none';
        appendMessage(data.message, data.is_bot);
    } else if (data.type === 'error') {
        appendMessage(data.message, true);
    }
}

function handleSocketClose() {
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        setTimeout(initializeChat, 3000 * reconnectAttempts);
    } else {
        appendMessage("Connection lost. Please refresh the page to reconnect.", true);
    }
}

function handleSocketError(error) {
    console.error('WebSocket Error:', error);
}

function clearErrorMessages() {
    const messagesDiv = document.getElementById('chatMessages');
    const errorMessages = messagesDiv.querySelectorAll('.message.bot:last-child');
    errorMessages.forEach(msg => {
        if (msg.textContent.includes('Connection lost')) {
            msg.remove();
        }
    });
}

function appendMessage(message, isBot) {
    const messagesDiv = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isBot ? 'bot' : 'user'}`;
    messageDiv.textContent = message;
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function sendMessage(event) {
    event.preventDefault();
    const messageInput = document.querySelector('.message-input');
    const message = messageInput.value.trim();
    
    if (message && chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        appendMessage(message, false);
        chatSocket.send(JSON.stringify({
            'message': message
        }));
        messageInput.value = '';
    } else if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
        appendMessage("Connection lost. Attempting to reconnect...", true);
        initializeChat();
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage(event);
    }
}

function toggleChat() {
    const chatBody = document.querySelector('.chat-body');
    chatBody.style.display = chatBody.style.display === 'none' ? 'flex' : 'none';
}

// Initialize chat when document loads
document.addEventListener('DOMContentLoaded', initializeChat); 