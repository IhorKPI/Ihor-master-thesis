import asyncio
from consumer import KafkaConsumer
from producer import KafkaProducer
from redis_client import RedisClient
import json

KAFKA_BROKER_URL = 'kafka:9092'
TRANSPORT_IN_TOPIC = 'transport-in'
ERROR_TOPIC = 'error'
GROUP_ID = 'check-transport-out'
REDIS_URL = 'redis://redis:6379'


async def process_message(message, producer, redis_client):
    try:
        data = json.loads(message.value.decode("utf-8"))
        plate = data["plate"]

        existing_entry = await redis_client.get_car_entry(plate)
        if existing_entry:
            await redis_client.delete_car_entry(plate)
            error_message = {
                "gate": existing_entry["gate"],
                "timestamp": existing_entry["timestamp"],
                "plate": existing_entry["plate"],
                "transport_type": existing_entry["transport_type"],
                "error": "Vehicle re-entered without exit"
            }

            await producer.send_message(ERROR_TOPIC, error_message)
            print(f"Sent error message: {error_message}")

        await redis_client.add_car_entry(plate, data)
        print(f"Processing confirmed: {message}")
        print(f"Added/Updated car entry in Redis: {data}")

    except Exception as e:
        print(f"Error processing message: {e}")


async def consume_and_process():
    consumer = KafkaConsumer(TRANSPORT_IN_TOPIC, KAFKA_BROKER_URL, GROUP_ID)
    producer = KafkaProducer(KAFKA_BROKER_URL)
    redis_client = RedisClient(REDIS_URL)

    try:
        await redis_client.connect()
        await consumer.start()
        await producer.start()
        print("Consumer and producer started successfully.")
        async for message in consumer.consume_messages():
            await process_message(message, producer, redis_client)
            await consumer.commit()
            print(f"Processing confirmed: {message}")

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Shutting down gracefully...")
    except Exception as e:
        print(f"Unhandled exception: {e}")
    finally:

        await consumer.stop()
        await producer.flush()
        await producer.stop()
        await redis_client.close()
        print("Consumer and producer stopped.")

if __name__ == "__main__":
    asyncio.run(consume_and_process())
