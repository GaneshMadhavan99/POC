import asyncio
import logging
from rabbitmq_worker import RabbitMQWorker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main entry point for the processor"""
    logger.info("Starting RabbitMQ Processor...")
    
    worker = RabbitMQWorker()
    
    try:
        await worker.start()
        logger.info("Processor started successfully")
        
        # Keep the processor running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Processor error: {e}")
        raise
    finally:
        await worker.stop()
        logger.info("Processor stopped")

if __name__ == "__main__":
    asyncio.run(main())