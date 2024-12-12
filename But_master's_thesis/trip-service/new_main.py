import asyncio
import json
from consumer import KafkaConsumer
from producer import KafkaProducer
from price_db import load_config, calculate_price

KAFKA_BROKER_URL = 'kafka:9092'
HISTORY_TOPIC = ['history']
GROUP_ID = 'toll-service-group'
FOR_ARCH = 'full-trip-data'

async def process_message(message, producer):
    try:
        data = json.loads(message.value.decode("utf-8"))
        print(f"Processing confirmed: {message}")
        transport_type = data["transport_type"]
        entry_gate = data["entry_gate"]
        exit_gate = data["exit_gate"]
        distance, price = calculate_price(entry_gate, exit_gate, transport_type)
        archive_message = {
            "id": data["id"],
            "plate": data["plate"],
            "transport_type": transport_type,
            "price": price,
            "entry_gate": entry_gate,
            "exit_gate": exit_gate,
            "distance": distance,
            "entry_timestamp": data["entry_timestamp"],
            "exit_timestamp": data["exit_timestamp"],
        }

        await producer.send_message(FOR_ARCH, archive_message)
        print("Message sent ", archive_message)

    except Exception as e:
        print(f"Error processing message: {e}")


async def consume_and_process():
    consumer = KafkaConsumer(HISTORY_TOPIC, KAFKA_BROKER_URL, GROUP_ID)
    producer = KafkaProducer(KAFKA_BROKER_URL)
    await load_config()

    try:
        await consumer.start()
        await producer.start()
        print("Consumer, producer, and database connection started successfully.")

        async for message in consumer.consume_messages():
            await process_message(message, producer)
            await consumer.commit()

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Shutting down gracefully...")
    except Exception as e:
        print(f"Unhandled exception: {e}")
    finally:

        await consumer.stop()
        await producer.flush()
        await producer.stop()
        print("Consumer, producer, and database connection stopped.")

if __name__ == "__main__":
    asyncio.run(consume_and_process())