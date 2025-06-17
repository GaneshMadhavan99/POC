import asyncio
import os
from typing import AsyncGenerator

import aio_pika
from aio_pika import Message, connect_robust
from aio_pika.abc import AbstractIncomingMessage
import logging

logger = logging.getLogger(__name__)


class RabbitMQClient:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.input_queue = None
        self.output_queue = None
        self.rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://admin:admin123@rabbitmq:5672/")

    async def connect(self):
        """Establish connection with RabbitMQ and initialize queues."""
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                self.connection = await connect_robust(
                    self.rabbitmq_url,
                    client_properties={"connection_name": "fastapi-client"}
                )
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=10)

                self.input_queue = await self.channel.declare_queue("input_queue", durable=True)
                self.output_queue = await self.channel.declare_queue("output_queue", durable=True)

                logger.info("Connected to RabbitMQ successfully.")
                return

            except Exception as e:
                logger.warning(f"Attempt {attempt}/{max_retries} to connect failed: {e}")
                if attempt == max_retries:
                    logger.error("RabbitMQ connection failed after all retries.")
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

    async def publish_message(self, message: str):
        """Publish a message to the input queue."""
        try:
            if not self.channel or self.channel.is_closed:
                await self.connect()

            await self.channel.default_exchange.publish(
                Message(
                    body=message.encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key="input_queue"
            )
            logger.info(f"Published to input_queue: {message[:100]}...")

        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            raise

    async def consume_responses(self) -> AsyncGenerator[AbstractIncomingMessage, None]:
        """Yield messages from the output queue as they arrive."""
        try:
            if not self.channel or self.channel.is_closed:
                await self.connect()

            logger.info("Consuming messages from output_queue...")
            async with self.output_queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        logger.info(f"Received from output_queue: {message.body.decode()[:100]}...")
                        yield message

        except Exception as e:
            logger.error(f" Error while consuming responses: {e}")
            raise

    async def close(self):
        """Close RabbitMQ connection gracefully."""
        try:
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
                logger.info("RabbitMQ connection closed.")
        except Exception as e:
            logger.warning(f"Error closing RabbitMQ connection: {e}")
