const WebSocket = require('ws');

function formatMessage(type, content) {
    return JSON.stringify({ type, content });
}

function handleError(error) {
    console.error('WebSocket Error:', error);
}

module.exports = {
    formatMessage,
    handleError,
};