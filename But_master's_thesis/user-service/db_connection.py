
import os
import asyncpg

DATABASE_CONFIG = {
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'database': os.getenv('DB_NAME', 'users_db'),
    'host': os.getenv('DB_HOST', 'postgres-service3'),
    'port': int(os.getenv('DB_PORT', '5432')),
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

        create_user_role_type = """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role_enum') THEN
                CREATE TYPE user_role_enum AS ENUM ('user', 'admin');
            END IF;
        END $$;
        """

        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            username VARCHAR(50) NOT NULL,
            password VARCHAR(255) NOT NULL,
            role user_role_enum DEFAULT 'user'
        );
        """

        create_user_cars_table = """
            CREATE TABLE IF NOT EXISTS user_cars (
                id SERIAL PRIMARY KEY,               
                user_id INTEGER NOT NULL,             
                plate VARCHAR(30) NOT NULL,           
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE (user_id, plate)
            );
            """


        async with self.pool.acquire() as conn:
            await conn.execute(create_user_role_type)
            await conn.execute(create_users_table)
            await conn.execute(create_user_cars_table)

    async def get_user_by_email(self, email: str):
        if not self.pool:
            await self.connect()
        async with self.pool.acquire() as conn:
            query = "SELECT id, email, username, password, role FROM users WHERE email = $1"
            return await conn.fetchrow(query, email)

    async def insert_user(self, email: str, username: str, hashed_password: str):
        if not self.pool:
            await self.connect()
        async with self.pool.acquire() as conn:
            query = "INSERT INTO users (email, username, password) VALUES ($1, $2, $3)"
            await conn.execute(query, email, username, hashed_password)

    async def add_user_car(self, plate: str, user_id: int) -> bool:
        if not self.pool:
            await self.connect()
        async with self.pool.acquire() as conn:
            query = """
            INSERT INTO user_cars (plate, user_id)
            VALUES ($1, $2)
            ON CONFLICT (user_id, plate) DO NOTHING
            """
            result = await conn.execute(query, plate, user_id)
            return result == "INSERT 0 1"

    async def remove_user_car(self, plate: str, user_id: int):
        if not self.pool:
            await self.connect()
        async with self.pool.acquire() as conn:
            query = """
            DELETE FROM user_cars WHERE plate = $1 AND user_id = $2
            """
            await conn.execute(query, plate, user_id)

    async def get_user_cars(self, user_id: int):
        if not self.pool:
            await self.connect()
        async with self.pool.acquire() as conn:
            query = """
            SELECT plate FROM user_cars WHERE user_id = $1
            """
            return await conn.fetch(query, user_id)
