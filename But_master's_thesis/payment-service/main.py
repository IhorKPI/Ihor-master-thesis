from fastapi import FastAPI, HTTPException
from db_connection import Database
from pydantic import BaseModel

app = FastAPI()
db = Database()

class NumberPlateRequest(BaseModel):
    number_plate: list[str]

class MakePayment(BaseModel):
    trip_ids: list[str]
    payment_method: str
    full_price: float


@app.on_event("startup")
async def startup_event():
    await db.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await db.disconnect()

@app.get("/unpaid/{number_plate}")
async def get_unpaid_trips(number_plate: str):
    try:
        trips = await db.get_unpaid_trip_ids(number_plate)
        print("AAA", trips)
        return trips
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")

@app.post("/all-trips", response_model=dict[str, list[dict[str, str]]])
async def get_all_trip_statuses(input_data: NumberPlateRequest):
    try:
        trip_statuses = await db.get_all_trips(input_data.number_plate)
        return trip_statuses
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")

@app.post("/process-payment", response_model=dict[str, str])
async def process_payment(input_data: MakePayment):
    try:
        transaction_id = await db.process_payments(input_data.trip_ids, input_data.payment_method, input_data.full_price)
        return {
            "message": f"Транзакція {transaction_id} проведена успішно"
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")
