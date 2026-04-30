import aiosqlite

DB_PATH = "game.db"

class Database:
    def __init__(self):
        self.conn = None

    async def connect(self):
        self.conn = await aiosqlite.connect(DB_PATH)
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, wins INTEGER DEFAULT 0, rating INTEGER DEFAULT 1000)""")
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def get_connection(self):
        if self.conn is None:
            await self.connect()
        return self.conn

    async def get_user(self, user_id):
        conn = await self.get_connection()
        async with conn.execute("SELECT wins, rating FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row is None:
                await conn.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                await conn.commit()
                return user_id, 0, 1000
            return user_id, row[0], row[1]

    async def add_win(self, user_id):
        conn = await self.get_connection()
        uid, wins, rating = await self.get_user(user_id)
        await conn.execute("UPDATE users SET wins=?, rating=? WHERE user_id=?",
                           (wins+1, rating+10, user_id))
        await conn.commit()

    async def get_top(self, limit=10):
        conn = await self.get_connection()
        async with conn.execute("SELECT user_id, wins, rating FROM users ORDER BY wins DESC LIMIT ?", (limit,)) as cur:
            return await cur.fetchall()
