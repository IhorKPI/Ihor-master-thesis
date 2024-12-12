from aiokafka import AIOKafkaConsumer
import asyncio

class KafkaConsumer:
    def __init__(self, topic, broker_url, group_id):
        self.consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=broker_url,
            group_id=group_id,
            enable_auto_commit=False,
            auto_offset_reset='earliest'
        )
        self.connected = False

    async def start(self):
        while not self.connected:
            try:
                await self.consumer.start()
                self.connected = True
                print("Consumer connected successfully")
            except Exception as e:
                print(f"Consumer connection failed, retrying... Error: {e}")
                await asyncio.sleep(2)

    async def stop(self):
        await self.consumer.stop()

    async def commit(self):
        await self.consumer.commit()

    async def consume_messages(self):
        async for msg in self.consumer:
            yield msg