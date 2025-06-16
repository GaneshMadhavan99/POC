import asyncio
import json
import uuid
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import uvicorn
from app.rabbitmq_client import RabbitMQClient
from app.websocket_manager import WebSocketManager
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastapi_app")

app = FastAPI(title="RabbitMQ FastAPI Streaming App")

# Shared instances
rabbitmq_client: RabbitMQClient = None
websocket_manager = WebSocketManager()
pending_requests: Dict[str, asyncio.Future] = {}

@app.on_event("startup")
async def startup():
    global rabbitmq_client
    rabbitmq_client = RabbitMQClient()
    await rabbitmq_client.connect()
    asyncio.create_task(route_rabbitmq_responses())
    logger.info("FastAPI started and listening for messages.")

@app.on_event("shutdown")
async def shutdown():
    if rabbitmq_client:
        await rabbitmq_client.close()
        logger.info("RabbitMQ connection closed.")

async def route_rabbitmq_responses():
    async for message in rabbitmq_client.consume_responses():
        try:
            payload = json.loads(message.body.decode())
            correlation_id = payload.get("correlation_id")
            response = payload.get("response", "No response")

            # Stream to websocket if matching
            if correlation_id in websocket_manager.active_connections:
                ws = websocket_manager.active_connections[correlation_id]
                await ws.send_text(response)

            # Fulfill future for HTTP stream
            if correlation_id in pending_requests:
                future = pending_requests.pop(correlation_id)
                if not future.done():
                    future.set_result(response)

        except Exception as e:
            logger.error(f"Error processing message: {e}")

@app.websocket("/ws")
async def websocket_handler(websocket: WebSocket):
    conn_id = str(uuid.uuid4())
    await websocket_manager.connect(websocket, conn_id)
    await websocket.send_text(f"Connected with ID: {conn_id}")

    try:
        while True:
            client_msg = await websocket.receive_text()
            logger.info(f"Received from client: {client_msg}")

            corr_id = str(uuid.uuid4())
            websocket_manager.active_connections[corr_id] = websocket

            msg = {
                "message": client_msg,
                "correlation_id": corr_id,
                "timestamp": asyncio.get_event_loop().time(),
            }
            await rabbitmq_client.publish_message(json.dumps(msg))

    except WebSocketDisconnect:
        logger.info(f"WebSocket {conn_id} disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        websocket_manager.disconnect(conn_id)

@app.get("/stream/{message}")
async def stream_response(message: str):
    async def stream_generator():
        corr_id = str(uuid.uuid4())
        future = asyncio.Future()
        pending_requests[corr_id] = future

        await rabbitmq_client.publish_message(json.dumps({
            "message": message,
            "correlation_id": corr_id,
            "timestamp": asyncio.get_event_loop().time()
        }))

        try:
            response = await asyncio.wait_for(future, timeout=30.0)
            yield f"data: {response}\n\n"
        except asyncio.TimeoutError:
            yield f"data: Timeout\n\n"
        finally:
            pending_requests.pop(corr_id, None)

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "active_websockets": len(websocket_manager.active_connections),
        "pending_streams": len(pending_requests)
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
