import redis.asyncio as redis
import json

class RedisClient:
    def __init__(self, redis_url):
        self.redis_url = redis_url
        self.redis = None

    async def connect(self):
        self.redis = redis.from_url(self.redis_url, decode_responses=True)


    async def get_car_entry(self, plate):

        if not self.redis:
            raise ConnectionError("Redis client is not connected.")
        entry = await self.redis.get(plate)
        return json.loads(entry) if entry else None

    async def delete_car_entry(self, plate):

        if not self.redis:
            raise ConnectionError("Redis client is not connected.")
        await self.redis.delete(plate)

    async def close(self):

        if self.redis:
            await self.redis.close()
