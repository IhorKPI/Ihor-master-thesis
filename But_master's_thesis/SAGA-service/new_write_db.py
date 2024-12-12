import asyncpg
import os
from datetime import datetime

DATABASE_CONFIG = {
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'database': os.getenv('DB_NAME', 'trips_db'),
    'host': os.getenv('DB_HOST', 'postgres-service1'),
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
        create_trips_table = """
            CREATE TABLE IF NOT EXISTS trips (
                id VARCHAR PRIMARY KEY,
                plate VARCHAR NOT NULL,
                transport_type VARCHAR NOT NULL,
                price NUMERIC(10, 2) NOT NULL,
                entry_gate VARCHAR NOT NULL,
                exit_gate VARCHAR NOT NULL,
                distance numeric(7,1) NOT NULL,
                entry_timestamp TIMESTAMP NOT NULL,
                exit_timestamp TIMESTAMP NOT NULL,
                consistent VARCHAR DEFAULT 'NOTCONSISTENT'
            );
        """

        create_index = """
            CREATE INDEX IF NOT EXISTS idx ON trips(id);
        """

        async with self.pool.acquire() as conn:
            await conn.execute(create_trips_table)
            await conn.execute(create_index)

    async def save_trip(self, full_trip_data):
        query = """
            INSERT INTO trips (
                id, plate, transport_type, price,
                entry_gate, exit_gate, distance,
                entry_timestamp, exit_timestamp
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """
        if not self.pool:
            await self.connect()

        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                full_trip_data["id"],
                full_trip_data["plate"],
                full_trip_data["transport_type"],
                full_trip_data["price"],
                full_trip_data["entry_gate"],
                full_trip_data["exit_gate"],
                full_trip_data["distance"],
                datetime.strptime(full_trip_data["entry_timestamp"], "%Y-%m-%dT%H:%M:%SZ"),
                datetime.strptime(full_trip_data["exit_timestamp"], "%Y-%m-%dT%H:%M:%SZ")
            )
            print(f"Trip {full_trip_data['id']} saved to database.")

    async def update_status(self, id, status):
        if not self.pool:
            await self.connect()

        update_query = """
            UPDATE trips
            SET consistent = $1
            WHERE id = $2
        """
        if not self.pool:
            await self.connect()
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(update_query, status, id)
                if result == "UPDATE 1":
                    print(f"Status updated for {id} with {status}")
                else:
                    print(f"No trip with {id}")

        except asyncpg.PostgresError as e:
            print(f"Database error occurred: {e}")