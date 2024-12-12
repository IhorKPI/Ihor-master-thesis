import asyncio
import json
from consumer import KafkaConsumer
from producer import KafkaProducer
from new_write_db import Database

KAFKA_BROKER_URL = 'kafka:9092'
LISTEN_TOPIC_HISTORY = 'full-trip-data'
LISTEN_TOPIC_SUCCESS = 'confirmation'
LISTEN_TOPIC_FAIL = 'transaction-failure'
GROUP_ID = 'SAGA'
SEND_TOPIC = 'first-transaction'
CONSUMER_TOPICS = [LISTEN_TOPIC_HISTORY, LISTEN_TOPIC_SUCCESS, LISTEN_TOPIC_FAIL]


async def process_topic_history(message, producer, db):
    data = json.loads(message.value.decode("utf-8"))
    try:
        await db.save_trip(data)
        await producer.send_message(SEND_TOPIC, data)
        print(f"Processing confirmed: {message}")

    except Exception as e:
        print(f"Error processing message: {e}")

async def process_topic_success(message, db):
    data = json.loads(message.value.decode("utf-8"))
    try:
        await db.update_status(data, "CONSISTENT")
        print(f"Processing confirmed: {message}")

    except Exception as e:
        print(f"Error processing message: {e}")

async def process_topic_fail(message, db):
    data = json.loads(message.value.decode("utf-8"))
    try:
        await db.update_status(data, "FAIL")
        print(f"Processing confirmed: {message}")

    except Exception as e:
        print(f"Error processing message: {e}")
async def process_message(message, producer, db):
    if message.topic == LISTEN_TOPIC_HISTORY:
        await process_topic_history(message, producer, db)
    elif message.topic == LISTEN_TOPIC_SUCCESS:
        await process_topic_success(message, db)
    elif message.topic == LISTEN_TOPIC_FAIL:
        await process_topic_fail(message, db)

async def consume_and_process():
    consumer = KafkaConsumer(CONSUMER_TOPICS, KAFKA_BROKER_URL, GROUP_ID)
    producer = KafkaProducer(KAFKA_BROKER_URL)
    db = Database()
    await db.connect()

    try:
        await consumer.start()
        await producer.start()
        print("Consumer, producer, and database connection started successfully.")

        async for message in consumer.consume_messages():
            await process_message(message, producer, db)
            await consumer.commit()

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Shutting down gracefully...")
    except Exception as e:
        print(f"Unhandled exception: {e}")
    finally:

        await consumer.stop()
        await producer.flush()
        await producer.stop()
        await db.disconnect()
        print("Consumer, producer, and database connection stopped.")

if __name__ == "__main__":
    asyncio.run(consume_and_process())