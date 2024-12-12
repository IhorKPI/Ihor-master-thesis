import os
import asyncpg

DATABASE_CONFIG = {
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'database': os.getenv('DB_NAME', 'payments_db'),
    'host': os.getenv('DB_HOST', 'postgres-service2'),
    'port': int(os.getenv('DB_PORT', '5432'))
}

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        if not self.pool:
            self.pool = await asyncpg.create_pool(**DATABASE_CONFIG)
            await self.initialize_tables()

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def initialize_tables(self):
        create_transaction_table = """
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id SERIAL PRIMARY KEY,
                payment_method VARCHAR NOT NULL,
                price NUMERIC(10, 2) NOT NULL,
                transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """


        create_payments_table = """
            CREATE TABLE IF NOT EXISTS trips (
                id SERIAL PRIMARY KEY,
                trip_id VARCHAR NOT NULL,
                price NUMERIC(10, 2) NOT NULL,
                status VARCHAR DEFAULT 'unpaid',
                number_plate VARCHAR NOT NULL,
                trip_date DATE NOT NULL,
                trip_time TIME NOT NULL,
                transaction_id INTEGER,
                FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
            );
        """

        create_index = """
            CREATE INDEX IF NOT EXISTS idx_number_plate ON trips(number_plate);
        """


        async with self.pool.acquire() as conn:
            await conn.execute(create_transaction_table)
            await conn.execute(create_payments_table)
            await conn.execute(create_index)

    async def get_unpaid_trip_ids(self, number_plate: str):
        if not self.pool:
            await self.connect()

        query = """
            SELECT trip_id
            FROM trips
            WHERE number_plate = $1 AND status = 'unpaid'
        """
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(query, number_plate)
            trip_ids = [row['trip_id'] for row in rows]
            return trip_ids

    async def get_all_trips(self, number_plates: list[str]):
        if not self.pool:
            await self.connect()

        query = """
            SELECT number_plate, trip_id, status
            FROM trips
            WHERE number_plate = ANY($1::VARCHAR[])
        """
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(query, number_plates)
            result = {}
            for row in rows:
                plate = row["number_plate"]
                trip_id = row["trip_id"]
                status = row["status"]
                trip_info = {"trip_id": trip_id, "status": status}
                result.setdefault(plate, []).append(trip_info)

            return result

    async def process_payments(self, trip_ids: list[str], payment_method: str, full_price: float):
        if not self.pool:
            await self.connect()

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                check_paid_trips_query = """
                    SELECT trip_id FROM trips
                    WHERE trip_id = ANY($1::VARCHAR[]) AND status = 'paid'
                """
                paid_trips = await connection.fetch(check_paid_trips_query, trip_ids)
                if paid_trips:
                    return f"Trips already paid: {[record['trip_id'] for record in paid_trips]}"

                insert_transaction_query = """
                    INSERT INTO transactions (payment_method, price)
                    VALUES ($1, $2)
                    RETURNING transaction_id
                """
                transaction_record = await connection.fetchrow(insert_transaction_query, payment_method, full_price)
                transaction_id = transaction_record['transaction_id']

                update_trips_query = """
                    UPDATE trips
                    SET status = 'paid', transaction_id = $1
                    WHERE trip_id = ANY($2::VARCHAR[])
                """
                updated_count = await connection.execute(update_trips_query, transaction_id, trip_ids)
                if updated_count == "UPDATE 0":
                    return updated_count

                return transaction_id



