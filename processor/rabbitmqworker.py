import asyncio
import json
import os
from typing import Dict, Any
import aio_pika
from aio_pika import Message, connect_robust
from aio_pika.abc import AbstractIncomingMessage
import logging

logger = logging.getLogger(__name__)

class RabbitMQWorker:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.input_queue = None
        self.output_queue = None
        self.rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://admin:admin123@localhost:5672/')
    
    async def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            # Connect with retry logic
            for attempt in range(10):
                try:
                    self.connection = await connect_robust(
                        self.rabbitmq_url,
                        client_properties={"connection_name": "processor-worker"}
                    )
                    break
                except Exception as e:
                    if attempt == 9:
                        raise
                    logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(3)
            
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=5)
            
            # Declare queues (ensure they exist)
            self.input_queue = await self.channel.declare_queue(
                'input_queue', 
                durable=True
            )
            self.output_queue = await self.channel.declare_queue(
                'output_queue', 
                durable=True
            )
            
            logger.info("Processor connected to RabbitMQ successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def process_message(self, message_data: Dict[str, Any]) -> str:
        """Process the incoming message and return response"""
        try:
            original_message = message_data.get('message', '')
            correlation_id = message_data.get('correlation_id', '')
            
            logger.info(f"Processing message: '{original_message}' with correlation_id: {correlation_id}")
            
            # Simple processing: append "world" to the message
            if original_message.lower().strip() == 'hello':
                processed_message = 'hello world'
            else:
                processed_message = f"{original_message} world"
            
            # Simulate some processing time
            await asyncio.sleep(0.5)
            
            logger.info(f"Processed message: '{processed_message}'")
            return processed_message
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return f"Error processing: {str(e)}"
    
    async def publish_response(self, response: str, correlation_id: str):
        """Publish processed response to output queue"""
        try:
            response_data = {
                'response': response,
                'correlation_id': correlation_id,
                'timestamp': asyncio.get_event_loop().time()
            }
            
            await self.channel.default_exchange.publish(
                Message(
                    json.dumps(response_data).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key='output_queue'
            )
            
            logger.info(f"Published response to output_queue: {response} (correlation_id: {correlation_id})")
            
        except Exception as e:
            logger.error(f"Failed to publish response: {e}")
            raise
    
    async def handle_message(self, message: AbstractIncomingMessage):
        """Handle incoming message from input queue"""
        try:
            # Parse message
            message_body = message.body.decode()
            message_data = json.loads(message_body)
            
            correlation_id = message_data.get('correlation_id', 'unknown')
            
            # Process the message
            response = await self.process_message(message_data)
            
            # Publish response
            await self.publish_response(response, correlation_id)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message JSON: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def start_consuming(self):
        """Start consuming messages from input queue"""
        try:
            logger.info("Starting to consume from input_queue...")
            
            # Set up consumer
            await self.input_queue.consume(
                self.handle_message,
                no_ack=False
            )
            
            logger.info("Processor is now listening for messages")
            
        except Exception as e:
            logger.error(f"Error starting consumer: {e}")
            raise
    
    async def start(self):
        """Start the worker"""
        await self.connect()
        await self.start_consuming()
    
    async def stop(self):
        """Stop the worker and close connections"""
        try:
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
                logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")