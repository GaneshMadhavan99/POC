# RabbitMQ WebSocket Message Processor

A complete asynchronous message processing system using FastAPI, RabbitMQ, and WebSockets.

## Architecture

```
Client ↔ FastAPI (WebSocket) → RabbitMQ (input_queue) → Processor → RabbitMQ (output_queue) → FastAPI → Client
```

## Features

- **WebSocket Communication**: Real-time bidirectional messaging
- **HTTP Streaming**: Alternative streaming response endpoint
- **Async Processing**: Fully asynchronous using `aio-pika` and FastAPI
- **Docker Compose**: Complete containerized setup
- **Message Correlation**: Proper request/response correlation using UUIDs
- **Multiple Connections**: Support for concurrent WebSocket connections
- **Health Monitoring**: Health check endpoint

## Project Structure

```
learn-test-solution/
│
├── docker-compose.yml
│
├── api/
│   ├── main.py              # FastAPI application with WebSocket
│   ├── rabbitmq_client.py   # RabbitMQ async client
│   ├── websocket_manager.py # WebSocket connection manager
│   ├── requirements.txt
│   └── Dockerfile
│
├── processor/
│   ├── main.py              # Processor entry point
│   ├── rabbitmq_worker.py   # Message processing worker
│   ├── requirements.txt
│   └── Dockerfile
│
└── README.md
```

## Quick Start

### 1. Clone and Run

```bash
# Clone the repository
git clone <your-repo-url>
cd learn-test-solution

# Start all services
docker-compose up --build
```

### 2. Access Services

- **FastAPI Docs**: http://localhost:8000/docs
- **RabbitMQ Management**: http://localhost:15672 (admin/admin123)
- **Health Check**: http://localhost:8000/health

## Usage Examples

### WebSocket Connection (Recommended)

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = function(event) {
    console.log('Connected to WebSocket');
    
    // Send a message
    ws.send('hello');
};

ws.onmessage = function(event) {
    console.log('Received:', event.data);
    // Expected: "hello world"
};
```

### HTTP Streaming Endpoint

```bash
# Test streaming response
curl -N http://localhost:8000/stream/hello

# Expected output:
# data: hello world
```

### Using Postman

1. **WebSocket**: 
   - Create new WebSocket request
   - URL: `ws://localhost:8000/ws`
   - Send message: `hello`
   - Receive: `hello world`

2. **HTTP Streaming**:
   - GET request to: `http://localhost:8000/stream/hello`
   - Should receive streaming response

## Testing Multiple Connections

```python
import asyncio
import websockets

async def test_websocket(client_id):
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        await websocket.send(f"hello from client {client_id}")
        response = await websocket.recv()
        print(f"Client {client_id} received: {response}")

# Run multiple clients
async def main():
    tasks = [test_websocket(i) for i in range(5)]
    await asyncio.gather(*tasks)

asyncio.run(main())
```

## How It Works

### Message Flow

1. **Client connects** to FastAPI WebSocket endpoint
2. **Client sends message** (e.g., "hello") via WebSocket
3. **FastAPI publishes** message to RabbitMQ `input_queue` with correlation ID
4. **Processor consumes** from `input_queue`, processes message (appends "world")
5. **Processor publishes** response to `output_queue` with same correlation ID
6. **FastAPI consumes** from `output_queue` and routes response back to correct WebSocket
7. **Client receives** processed message (e.g., "hello world")

### Key Components

- **Correlation IDs**: UUID-based message correlation for proper routing
- **Async Processing**: Non-blocking message processing using `asyncio`
- **Connection Management**: Proper WebSocket connection lifecycle management
- **Error Handling**: Comprehensive error handling and logging
- **Health Monitoring**: Service health and connection status endpoints

## Development

### Running Locally (without Docker)

```bash
# Terminal 1: Start RabbitMQ
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# Terminal 2: Start FastAPI
cd api
pip install -r requirements.txt
python main.py

# Terminal 3: Start Processor
cd processor
pip install -r requirements.txt
python main.py
```

### Environment Variables

- `RABBITMQ_URL`: RabbitMQ connection URL (default: `amqp://admin:admin123@localhost:5672/`)

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "active_websockets": 2,
  "pending_requests": 0
}
```

### RabbitMQ Management

Access the RabbitMQ management interface at http://localhost:15672:
- Username: `admin`
- Password: `admin123`

Monitor:
- Queue lengths
- Message rates
- Connection status
- Consumer activity

### Logs

```bash
# View all service logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f processor
docker-compose logs -f rabbitmq
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   ```bash
   # Check if services are running
   docker-compose ps
   
   # Restart services
   docker-compose restart
   ```

2. **WebSocket Connection Failed**
   - Ensure FastAPI service is running on port 8000
   - Check firewall settings
   - Verify WebSocket URL format

3. **No Response from Processor**
   - Check processor logs: `docker-compose logs processor`
   - Verify RabbitMQ connectivity
   - Check queue status in RabbitMQ management

4. **Message Not Processing**
   - Verify queue declarations match between services
   - Check message format and correlation IDs
   - Monitor RabbitMQ queues for stuck messages

### Debug Mode

Enable debug logging by modifying the logging level in both services:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Performance Considerations

- **Concurrent Connections**: FastAPI can handle thousands of concurrent WebSocket connections
- **Message Processing**: Processor uses prefetch_count=5 for controlled message consumption
- **Queue Durability**: Messages persist across service restarts
- **Connection Pooling**: RabbitMQ connections use connection pooling for efficiency

## Extensions

### Adding Authentication

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Depends(security)):
    # Validate token
    if not validate_token(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    # ... rest of the code
```

### Adding Message Persistence

```python
# Store messages in database
async def store_message(message: str, correlation_id: str):
    # Database storage logic
    pass
```

### Adding Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/stream/{message}")
@limiter.limit("10/minute")
async def stream_endpoint(request: Request, message: str):
    # ... existing code
```

## Testing

### Unit Tests

```python
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

### Integration Tests

```python
import asyncio
import websockets
import pytest

@pytest.mark.asyncio
async def test_websocket_echo():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        await websocket.send("hello")
        response = await websocket.recv()
        assert "world" in response.lower()
```

## Security Notes

- Change default RabbitMQ credentials in production
- Use environment variables for sensitive configuration
- Implement proper authentication for WebSocket connections
- Use TLS/SSL for production deployments
- Validate and sanitize all incoming messages

## License

This project is licensed under the MIT License.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review logs for error messages
3. Open an issue on GitHub with detailed information