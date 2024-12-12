import asyncio
from consumer import KafkaConsumer
from db_connection import add_to_elasticsearch, close_connection, table_init, delete_from_elasticsearch
from producer import KafkaProducer
import json

KAFKA_BROKER_URL = 'kafka:9092'
TOPIC_INPUT = 'first-transaction'
TOPIC_FAIL = 'transaction-failure'

TOPIC_SUCCESS = 'second-transaction'
TOPIC_FAIL_PAYMENT = 'error-payment'

GROUP_ID = 'CQRS'

TOPICS_INPUT = [TOPIC_INPUT, TOPIC_FAIL_PAYMENT]

async def process_topic_add(message, producer):
    trip = json.loads(message.value.decode("utf-8"))
    print(f"Processing confirmed: {message}")
    try:
        await add_to_elasticsearch("trips", trip)
        success_message = {
            "id": trip["id"],
            "plate": trip["plate"],
            "price": trip["price"],
            "exit_timestamp": trip["exit_timestamp"]
        }
        await producer.send_message(TOPIC_SUCCESS, success_message)
        print("Message sent ", success_message)

    except Exception as e:
        failure_message = {
            "id": trip["id"],
            "error": "Error to add message to read DB",
        }
        await producer.send_message(TOPIC_FAIL, failure_message)
        print(f"Error processing message: {e}")


async def process_topic_backup(message, producer):
    data = json.loads(message.value.decode("utf-8"))
    try:
        await delete_from_elasticsearch("trips", data)
        print(f"Deleting confirmed: {message}")
        failure_message = {
            "id": data,
            "error": f"Deleted from readDB, error in payment service",
        }
        await producer.send_message(TOPIC_FAIL, failure_message)

    except Exception as e:
        failure_message = {
            "id": data,
            "error": f"Error in payment service, error with deletion readDB",
        }
        await producer.send_message(TOPIC_FAIL, failure_message)
        print(f"Failure message sent: {failure_message}")


async def process_message(message, producer):
    if message.topic == TOPIC_INPUT:
        await process_topic_add(message, producer)
    elif message.topic == TOPIC_FAIL_PAYMENT:
        await process_topic_backup(message, producer)


async def consume_and_process():
    consumer = KafkaConsumer(TOPICS_INPUT, KAFKA_BROKER_URL, GROUP_ID)
    producer = KafkaProducer(KAFKA_BROKER_URL)
    try:
        await consumer.start()
        await producer.start()
        await table_init()
        print("Consumer started successfully.")
        async for message in consumer.consume_messages():
            await process_message(message, producer)
            await consumer.commit()

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Shutting down gracefully...")
    except Exception as e:
        print(f"Unhandled exception: {e}")
    finally:
        await consumer.stop()
        await close_connection()

if __name__ == "__main__":
    asyncio.run(consume_and_process())
