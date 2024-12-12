import json
from aiokafka import AIOKafkaProducer
import asyncio

class KafkaProducer:
    def __init__(self, broker_url):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=broker_url,
            acks="all",
            value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )
        self.connected = False

    async def start(self):
        while not self.connected:
            try:
                await self.producer.start()
                self.connected = True
                print("Producer connected successfully")
            except Exception as e:
                print(f"Producer connection failed, retrying... Error: {e}")
                await asyncio.sleep(2)

    async def stop(self):
        await self.producer.stop()

    async def flush(self):
        await self.producer.flush()

    async def send_message(self, topic, message):
        await self.producer.send_and_wait(topic, message)

