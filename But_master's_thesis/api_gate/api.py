import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from aiokafka import AIOKafkaProducer
import json
import asyncio

app = FastAPI()

INITIAL_TOKEN = os.getenv("INITIAL_API_TOKEN", default="123456")
AUTHORIZED_API_KEYS = set()
AUTHORIZED_API_KEYS.add("111")

KAFKA_BROKER_URL = 'kafka:9092'
TOPIC_TRAFFIC_IN = 'transport-in'
TOPIC_TRAFFIC_OUT = 'transport-out'


producer = AIOKafkaProducer(
    bootstrap_servers=KAFKA_BROKER_URL,
    acks="all",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

@app.on_event("startup")
async def startup_event():
    async def start_producer_with_retries():
        while True:
            try:
                await producer.start()
                print("Producer started successfully")
                break
            except Exception as e:
                print(f"Error starting producer: {e}")
                await asyncio.sleep(5)

    await start_producer_with_retries()

@app.on_event("shutdown")
async def shutdown_event():
    await producer.flush()
    await producer.stop()

class CameraData(BaseModel):
    token: str
    gate: str
    status: bool
    time: str
    plate: str
    transport_type: str


@app.post("/new-token/{existing_token}/{new_token}")
async def add_token(existing_token: str, new_token: str):
    if existing_token != INITIAL_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid existing token")
    AUTHORIZED_API_KEYS.add(new_token)
    return {"status": f"Token {new_token} added successfully"}


@app.post("/send-data/")
async def send_to_kafka(data: CameraData):
    if data.token not in AUTHORIZED_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API token")

    message = {
        "gate": data.gate,
        "timestamp": data.time,
        "plate": data.plate,
        "transport_type": data.transport_type
    }

    topic = TOPIC_TRAFFIC_IN if data.status else TOPIC_TRAFFIC_OUT

    try:
        await producer.send_and_wait(topic, message)
        print(f"Processing confirmed: {message}")
        return {"status": "Message sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kafka error: {str(e)}")