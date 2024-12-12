import asyncio
import json
from datetime import datetime
from consumer import KafkaConsumer
from producer import KafkaProducer
from new_db_connection import Database

KAFKA_BROKER_URL = 'kafka:9092'
TOPIC_INPUT = 'second-transaction'

TOPIC_FAIL_PAYMENT = 'error-payment'
TOPIC_SUCCESS = 'confirmation'

GROUP_ID = 'full_trip_data_payment'

async def process_message(message, producer, db):
    data = json.loads(message.value.decode("utf-8"))

    try:
        trip_id = data["id"]
        number_plate = data["plate"]
        cost = data["price"]
        iso_timestamp = data["exit_timestamp"]

        iso_timestamp = iso_timestamp.replace('Z', '+00:00')
        dt_object = datetime.fromisoformat(iso_timestamp)
        trip_date = dt_object.date()
        trip_time = dt_object.time()

        await db.add_trip(trip_id, cost, trip_date, trip_time, number_plate)
        await producer.send_message('confirmation', data["id"])
        print(f"Processing confirmed: {message}")


    except Exception:
        await producer.send_message(TOPIC_FAIL_PAYMENT, data["id"])
        print("Failure message sent for ", data["id"])


async def consume_and_process():
    consumer = KafkaConsumer(TOPIC_INPUT, KAFKA_BROKER_URL, GROUP_ID)
    producer = KafkaProducer(KAFKA_BROKER_URL)
    db = Database()
    await db.connect()
    try:
        await consumer.start()
        await producer.start()
        print("Consumer started successfully.")

        async for message in consumer.consume_messages():
            await process_message(message, producer, db)
            await consumer.commit()

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Shutting down gracefully...")
    except Exception as e:
        print(f"Unhandled exception: {e}")
    finally:
        await consumer.stop()
        await db.disconnect()
        print("Consumer and database connection closed.")

if __name__ == "__main__":
    asyncio.run(consume_and_process())