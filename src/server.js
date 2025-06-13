const WebSocket = require('ws');

const server = new WebSocket.Server({ port: 8080 });

server.on('connection', (ws) => {
    console.log('New client connected');

    ws.on('message', (message) => {
        console.log(`Received: ${message}`);
        // Echo the message back to the client
        ws.send(`You said: ${message}`);
    });

    ws.on('close', () => {
        console.log('Client disconnected');
    });
});

server.on('listening', () => {
    console.log('WebSocket server is listening on ws://localhost:8080');
});