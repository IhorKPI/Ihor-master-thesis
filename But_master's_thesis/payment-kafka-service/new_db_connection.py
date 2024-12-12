import asyncpg
import os

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


    async def add_trip(self, trip_id, price, trip_date, trip_time, number_plate):
        if not self.pool:
            await self.connect()

        query = """
            INSERT INTO trips (trip_id, price, trip_date, trip_time, number_plate)
            VALUES ($1, $2, $3, $4, $5)
        """

        try:
            async with self.pool.acquire() as connection:
                await connection.execute(query, trip_id, price, trip_date, trip_time, number_plate)
            print(f"Record added successfully for Trip ID: {trip_id}")
        except asyncpg.PostgresError as e:
            print(f"Database error occurred: {e}")


