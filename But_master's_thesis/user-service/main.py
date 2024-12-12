from fastapi import FastAPI, HTTPException, Depends, Form, Request, Cookie, Header
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jwt import decode, encode, ExpiredSignatureError, InvalidTokenError, ExpiredSignatureError
from datetime import datetime, timedelta
from db_connection import Database
from typing import Optional
import httpx
import asyncio
import aiobcrypt

SECRET_KEYS = {
    "admin": "admin_secret_key",
    "user": "user_secret_key"
}
ALGORITHM = "HS256"

app = FastAPI()
templates = Jinja2Templates(directory="templates")
db = Database()

async def hash_password(password: str) -> str:
    salt = await aiobcrypt.gensalt()
    hashed = await aiobcrypt.hashpw(password.encode('utf-8'), salt)
    hashed_str = hashed.decode('utf-8')
    return hashed_str

async def verify_password(plain_password: str, hashed_password: str) -> bool:
    return await aiobcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

async def create_jwt(user_id: int, email: str, username: str, role: str):
    if role == "admin":
        consumer_key = "admin-service"
        secret_key = SECRET_KEYS["admin"]
    else:
        consumer_key = "user-service"
        secret_key = SECRET_KEYS["user"]

    payload = {
        "sub": user_id,
        "email": email,
        "username": username,
        "role": role,
        "iss": consumer_key,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return await asyncio.to_thread(encode, payload, secret_key, algorithm=ALGORITHM)

async def get_user_id_from_cookie(token: Optional[str] = Cookie(None, alias="access_token")) -> Optional[dict]:
    if not token:
        return None
    try:
        decoded_token = await asyncio.to_thread(decode, token, options={"verify_signature": False})
        user_id = decoded_token.get("sub")
        email = decoded_token.get("email")
        role = decoded_token.get("role")
        username = decoded_token.get("username")
        return {"id": user_id, "email": email, "role": role, "username": username}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid token: {e}")


async def combine_trip_data_async(payment_data, history_data):
    def combine_sync():
        results = {}
        for number_plate, payment_trips in payment_data.items():
            combined_trips = []
            for payment_trip in payment_trips:
                trip_id = payment_trip["trip_id"]
                status = payment_trip["status"]
                history_trips = history_data.get(number_plate, [])
                for history_trip in history_trips:
                    if history_trip["id"] == trip_id:
                        combined_trip = history_trip.copy()
                        combined_trip["status"] = status
                        combined_trips.append(combined_trip)
            if combined_trips:
                results[number_plate] = combined_trips
        return results
    return await asyncio.to_thread(combine_sync)

def format_datetime(iso_string):
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    except ValueError:
        return iso_string

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/", response_class=HTMLResponse)
async def main_menu(request: Request):
    return templates.TemplateResponse("login-page.html", {"request": request})


@app.get("/signin", response_class=HTMLResponse)
async def signin_page(request: Request):
    return templates.TemplateResponse("signin.html", {"request": request, "error": None})


@app.post("/signin", response_class=HTMLResponse)
async def signin(request: Request, email: str = Form(...), password: str = Form(...)):
    user = await db.get_user_by_email(email)

    if user is None or not await verify_password(password, user["password"]):
        return templates.TemplateResponse(
            "signin.html",
            {"request": request, "error": "Invalid credentials"}
        )
    token = await create_jwt(user["id"], user["email"], user["username"], user["role"])
    role_redirect = "/admin" if user["role"] == "admin" else "/user"
    response = RedirectResponse(url=role_redirect, status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
    )
    return response

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request, "error": None})

@app.post("/signup", response_class=HTMLResponse)
async def signup(request: Request, email: str = Form(...), username: str = Form(...), password: str = Form(...)):
    existing_user = await db.get_user_by_email(email)
    if existing_user:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Email already exists."}
        )

    hashed_password = await hash_password(password)
    await db.insert_user(email, username, hashed_password)
    response = RedirectResponse(url="/signin", status_code=303)
    return response

@app.get("/user")
async def user_dashboard(request: Request, user: dict = Depends(get_user_id_from_cookie)):
    user_id = user["id"]
    username = user["username"]
    email = user["email"]

    try:
        cars = await db.get_user_cars(user_id)
        plates = [record['plate'] for record in cars]
    except Exception as e:
        plates = []
        print(f"Error retrieving user cars: {e}")

    if not plates:
        return templates.TemplateResponse("user_dashboard.html", {
            "request": request,
            "username": username,
            "email": email,
            "trips_by_plate": {},
            "has_unpaid": False,
            "total_debt": 0,
            "plates": plates,
            "all_unpaid_ids": []
        })

    PAYMENT_SERVICE_URL = "http://payment_service:5004/all-trips"
    HISTORY_SERVICE_URL = "http://get_trip_service:5002/all-trips"

    async with httpx.AsyncClient() as client:
        try:
            payment_response, history_response = await asyncio.gather(
                client.post(PAYMENT_SERVICE_URL, json={"number_plate": plates}),
                client.post(HISTORY_SERVICE_URL, json={"number_plate": plates}),
            )
            payment_data = payment_response.json()
            history_data = history_response.json()

            combined_data = await combine_trip_data_async(payment_data, history_data)

        except Exception as e:
            print(f"Error contacting external services: {e}")
            combined_data = {}

        total_debt = 0
        trips_by_plate = {}
        all_unpaid_ids = []

        for plate, trips in combined_data.items():
            unpaid_cost = 0
            unpaid_ids = []

            for trip in trips:
                trip["entry_timestamp"] = format_datetime(trip["entry_timestamp"])
                trip["exit_timestamp"] = format_datetime(trip["exit_timestamp"])

                if trip["status"] == "unpaid":
                    unpaid_cost += float(trip["price"])
                    unpaid_ids.append(trip["id"])

            trips_by_plate[plate] = {
                "trips": trips,
                "unpaid_cost": unpaid_cost,
                "unpaid_ids": unpaid_ids,
            }

            total_debt += unpaid_cost
            all_unpaid_ids.extend(unpaid_ids)

        has_unpaid = total_debt > 0

        return templates.TemplateResponse("user_dashboard.html", {
            "request": request,
            "username": username,
            "email": email,
            "trips_by_plate": trips_by_plate,
            "has_unpaid": has_unpaid,
            "total_debt": total_debt,
            "plates": plates,
            "all_unpaid_ids": all_unpaid_ids
        })

@app.post("/user/payment")
async def handle_payment(request: Request, trip_ids: list = Form(...)):
    print(f"Processing payment for trips: {trip_ids}")
    return RedirectResponse(url="/user", status_code=303)

@app.get("/user/add_car", response_class=HTMLResponse)
async def display_add_car_form(request: Request, user: dict = Depends(get_user_id_from_cookie)):
    return templates.TemplateResponse("add_car.html", {"request": request, "username": user["username"]})

@app.post("/user/add_car", response_class=HTMLResponse)
async def handle_add_car(request: Request, license_plate: str = Form(...), user: dict = Depends(get_user_id_from_cookie)):
    user_id = user["id"]
    try:
        success = await db.add_user_car(license_plate, user_id)
        if success:
            message = f"Номер машини {license_plate} успішно додано!"
        else:
            message = f"Ви вже маєте номер машини {license_plate}."
    except Exception as e:
        message = f"Помилка при додаванні номера: {e}"

    return templates.TemplateResponse("add_car_success.html", {"request": request, "license_plate": license_plate, "message": message})

@app.get("/user/remove_car", response_class=HTMLResponse)
async def display_remove_car_form(request: Request, user: dict = Depends(get_user_id_from_cookie)):
    user_id = user["id"]
    try:
        cars = await db.get_user_cars(user_id)
        plates = [record['plate'] for record in cars]
    except Exception as e:
        plates = []
        print(f"Ошибка при получении машин для удаления: {e}")

    return templates.TemplateResponse("remove_car.html", {"request": request, "plates": plates, "username": user["username"]})

@app.post("/user/remove_car", response_class=HTMLResponse)
async def handle_remove_car(request: Request, license_plate: str = Form(...), user: dict = Depends(get_user_id_from_cookie)):
    user_id = user["id"]
    try:
        await db.remove_user_car(license_plate, user_id)
        message = f"Номер машини {license_plate} успішно видалено!"
    except Exception as e:
        message = f"Помилка при видаленні номера: {e}"

    return templates.TemplateResponse("remove_car_success.html", {"request": request, "license_plate": license_plate, "message": message})


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(user: dict = Depends(get_user_id_from_cookie)):
    return {"id": user["id"], "email": user["email"], "role": user["role"]}

@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/signin", status_code=303)
    response.delete_cookie(key="access_token")
    return response

@app.get("/user/debug")
async def debug_headers(request: Request):
    return {"headers": dict(request.headers)}


@app.post("/user/pay", response_class=HTMLResponse)
async def process_total_payment(request: Request, trip_ids: str = Form(...), total_cost: float = Form(...)):
    return templates.TemplateResponse("user_pay.html", {
        "request": request,
        "trip_ids": trip_ids,
        "total_cost": total_cost
    })

@app.post("/user/pay_progress", response_class=HTMLResponse)
async def process_total_payment(request: Request, trip_ids: str = Form(...), total_cost: float = Form(...), payment_method: str = Form(...)):
    trip_ids = trip_ids.split(",")
    try:
        PAYMENT_HOLDING_SERVICE_URL = "http://payment_service:5004/process-payment"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                PAYMENT_HOLDING_SERVICE_URL,
                json={
                    "trip_ids": trip_ids,
                    "payment_method": payment_method,
                    "full_price": total_cost
                }
            )

            result = response.json()

            return templates.TemplateResponse("payment_result.html", {
                "request": request,
                "result": result,
            })

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")

@app.get("/checkbycar", response_class=HTMLResponse)
async def show_payment_form(request: Request):
    return templates.TemplateResponse("fast_user_pay.html", {
        "request": request,
        "plate": [],
        "unpaid_trips": [],
        "total_cost": [],
        "trip_ids": []
    })


@app.post("/checkbycar", response_class=HTMLResponse)
async def process_total_payment(request: Request, plate: str = Form(...)):
    PAYMENTS_SERVICE_URL = "http://payment_service:5004/unpaid/"
    TRIPS_SERVICE_URL = "http://get_trip_service:5002/all-trips-by-ids"
    unpaid_trips = []
    total_cost = 0.0

    if plate:
        async with httpx.AsyncClient() as client:
            response = await client.get(PAYMENTS_SERVICE_URL + plate)
            unpaid_trip_ids = response.json()
            if unpaid_trip_ids:
                trip_results_response = await client.post(
                    TRIPS_SERVICE_URL,
                    json={
                        "number_plate": plate,
                        "ids": unpaid_trip_ids
                    }
                )
                unpaid_trips = trip_results_response.json()

                for trip_id, trip in zip(unpaid_trip_ids, unpaid_trips):
                    trip['id'] = trip_id
                    dt = datetime.fromisoformat(trip["exit_timestamp"].replace("Z", "+00:00"))
                    trip['exit_timestamp'] = dt.strftime("%Y-%m-%d %H:%M:%S")
                    total_cost += float(trip["price"])

    print("AA", unpaid_trips)
    return templates.TemplateResponse("fast_user_pay.html", {
        "request": request,
        "plate": plate,
        "unpaid_trips": unpaid_trips,
        "total_cost": total_cost,
        "trip_ids": unpaid_trip_ids
    })


@app.post("/pay_progress", response_class=HTMLResponse)
async def process_total_payment(request: Request, trip_ids: str = Form(...), total_cost: float = Form(...), payment_method: str = Form(...)):
    trip_ids = trip_ids.split(",")
    try:
        PAYMENT_HOLDING_SERVICE_URL = "http://payment_service:5004/process-payment"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                PAYMENT_HOLDING_SERVICE_URL,
                json={
                    "trip_ids": trip_ids,
                    "payment_method": payment_method,
                    "full_price": total_cost
                }
            )

            result = response.json()

            return templates.TemplateResponse("payment_result.html", {
                "request": request,
                "result": result,
            })

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")
