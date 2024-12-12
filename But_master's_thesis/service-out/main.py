import asyncio
from consumer import KafkaConsumer
from producer import KafkaProducer
from redis_client import RedisClient
import json
import uuid

KAFKA_BROKER_URL = 'kafka:9092'
TRANSPORT_OUT_TOPIC = 'transport-out'
ERROR_TOPIC = 'error'
FOR_HISTORY = 'history'
GROUP_ID = 'check-transport-in'
REDIS_URL = 'redis://redis:6379'


async def process_message(message, producer, redis_client):
    try:
        data = json.loads(message.value.decode("utf-8"))
        plate = data["plate"]
        transport_type = data["transport_type"]
        enter_transport_info = await redis_client.get_car_entry(plate)
        if not enter_transport_info:
            error_message = {
                "gate": data["gate"],
                "timestamp": data["timestamp"],
                "plate": plate,
                "transport_type": transport_type,
                "error": "Vehicle exit without enter"
            }
            await producer.send_message(ERROR_TOPIC, error_message)
            print(f"Sent error message: {error_message}")
        else:
            if enter_transport_info["transport_type"] != transport_type:
                error_message = {
                    "entry_gate": enter_transport_info["gate"],
                    "entry_timestamp": enter_transport_info["timestamp"],
                    "exit_gate": data["gate"],
                    "exit_timestamp": data["timestamp"],
                    "plate": plate,
                    "entry_transport_type": enter_transport_info["transport_type"],
                    "exit_transport_type": transport_type,
                    "error": "Transport type mismatch"
                }

                await producer.send_message(ERROR_TOPIC, error_message)
                print(f"Sent error message: {error_message}")

                await redis_client.delete_car_entry(plate)
            else:
                history_message = {
                    "id": str(uuid.uuid4()),
                    "plate": plate,
                    "transport_type": transport_type,
                    "entry_gate": enter_transport_info["gate"],
                    "entry_timestamp": enter_transport_info["timestamp"],
                    "exit_gate": data["gate"],
                    "exit_timestamp": data["timestamp"]

                }
                print(f"Processing confirmed: {message}")
                await producer.send_message(FOR_HISTORY, history_message)
                print(f"Sent history message: {history_message}")
                await redis_client.delete_car_entry(plate)
                print(f"Removed car entry from Redis: {plate}")

    except Exception as e:
        print(f"Error processing exit message: {e}")


async def consume_and_process():
    consumer = KafkaConsumer(TRANSPORT_OUT_TOPIC, KAFKA_BROKER_URL, GROUP_ID)
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
