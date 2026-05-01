import asyncio, random
import discord
from typing import Dict, List, Optional

SIZE = 16
COLS = [chr(ord('A')+i) for i in range(SIZE)]
PIECES = ["🔴","🔺","🟩","🔹"]
EMPTY = "⬜"

class Game:
    def __init__(self, player_ids: List[int], gid: int, guild):
        if len(player_ids) < 2 or len(player_ids) > 4:
            raise ValueError("Допустимо от 2 до 4 игроков")
        self.id = gid
        self.guild = guild
        available = list(PIECES)
        random.shuffle(available)
        self.piece_of = {pid: available[i] for i, pid in enumerate(player_ids)}
        self.grid = [[None]*SIZE for _ in range(SIZE)]
        self.turn_order = list(player_ids)
        random.shuffle(self.turn_order)
        self.turn_index = 0
        self.winner: Optional[int] = None
        self.move_count = {pid: 0 for pid in player_ids}
        self.player_messages: Dict[int, int] = {}

    @property
    def players(self):
        return set(self.turn_order)

    @property
    def turn(self):
        if self.winner:
            return None
        return self.turn_order[self.turn_index]

    def cell_index(self, coord):
        col = COLS.index(coord[0].upper())
        row = int(coord[1:]) - 1
        return row, col

    def place(self, pid, coord):
        if pid not in self.players:
            raise ValueError("Вы не в игре")
        if self.winner:
            raise ValueError("Игра окончена")
        if pid != self.turn:
            raise ValueError("Не ваш ход")
        r, c = self.cell_index(coord)
        if self.grid[r][c] is not None:
            raise ValueError("Клетка занята")
        self.grid[r][c] = pid
        self.move_count[pid] += 1
        if self._check_win(pid, r, c):
            self.winner = pid
        else:
            self.turn_index = (self.turn_index + 1) % len(self.turn_order)
        return self.piece_of[pid]

    def _check_win(self, pid, r, c):
        if all(self.grid[r][x] == pid for x in range(SIZE)): return True
        if all(self.grid[x][c] == pid for x in range(SIZE)): return True
        if r == c and all(self.grid[i][i] == pid for i in range(SIZE)): return True
        if r+c == SIZE-1 and all(self.grid[i][SIZE-1-i] == pid for i in range(SIZE)): return True
        return False

    def remove_player(self, player_id):
        if player_id not in self.players:
            return False
        self.turn_order.remove(player_id)
        if self.turn_index >= len(self.turn_order):
            self.turn_index = 0
        self.move_count.pop(player_id, None)
        if len(self.turn_order) == 1:
            self.winner = self.turn_order[0]
            return False
        return True

    def render_board(self):
        # Заголовок: 3 пробела (как "1 "), затем буквы с одним пробелом после каждой
        header = "   " + "".join(f"{col} " for col in COLS)
        lines = [header]
        for i in range(SIZE):
            row_emojis = []
            for j in range(SIZE):
                pid = self.grid[i][j]
                row_emojis.append(self.piece_of[pid] if pid else EMPTY)
            # Строка: номер (2 символа) + пробел + эмодзи слитно (без пробелов)
            line = f"{i+1:2} " + "".join(row_emojis)
            lines.append(line)
        return "```\n" + "\n".join(lines) + "```"


class GameManager:
    def __init__(self, db):
        self.queue_2: List[int] = []
        self.queue_3: List[int] = []
        self.queue_4: List[int] = []
        self.player_queue: Dict[int, int] = {}
        self.games: Dict[int, Game] = {}
        self.player_game: Dict[int, int] = {}
        self.next_id = 1
        self.db = db

    async def add_to_queue(self, uid, guild, size):
        if uid in self.player_game:
            return "Вы уже в игре"
        if uid in self.player_queue:
            return "Вы уже в очереди"
        if size not in (2,3,4):
            return "Неверный размер игры"

        queue = getattr(self, f"queue_{size}")
        queue.append(uid)
        self.player_queue[uid] = size

        if len(queue) >= size:
            players = [queue.pop(0) for _ in range(size)]
            for p in players:
                del self.player_queue[p]
            gid = self.next_id
            self.next_id += 1
            game = Game(players, gid, guild)
            self.games[gid] = game
            for p in players:
                self.player_game[p] = gid
            return f"Соперники найдены! Игра #{gid} ({size} игроков) начинается."
        return f"Вы в очереди ({size} игроков). Ожидание соперников..."

    async def remove_from_queue(self, uid):
        if uid in self.player_queue:
            size = self.player_queue.pop(uid)
            queue = getattr(self, f"queue_{size}")
            queue.remove(uid)
            return f"Вы покинули очередь ({size} игроков)"
        return "Вас нет в очереди"

    async def make_move(self, uid, coord):
        gid = self.player_game.get(uid)
        if not gid: return "Вы не в игре", None
        game = self.games.get(gid)
        if not game: return "Игра не найдена", None
        try:
            piece = game.place(uid, coord)
        except ValueError as e:
            return str(e), None
        if game.winner:
            await self.db.add_win(game.winner)
            return f"Вы поставили {piece}. Поздравляем, вы победили!", game
        return f"Вы поставили {piece} на {coord}. Ход передан следующему игроку.", game

    async def player_exit(self, user_id):
        if user_id in self.player_queue:
            return await self.remove_from_queue(user_id)

        gid = self.player_game.get(user_id)
        if not gid:
            return "Вы не находитесь в игре."

        game = self.games.get(gid)
        if not game:
            self.player_game.pop(user_id, None)
            return "Игра не найдена."

        game_continues = game.remove_player(user_id)
        self.player_game.pop(user_id, None)

        if not game_continues:
            winner = game.winner
            if winner:
                await self.db.add_win(winner)
                await self._notify_exit(game, user_id, winner)
            self.end_game(gid)
            return "Вы вышли из игры. Игра завершена."
        else:
            await self._notify_exit(game, user_id, None)
            return "Вы вышли из игры. Игра продолжается."

    async def _notify_exit(self, game, leaver_id, winner_id=None):
        from main import bot
        try:
            msg_id = game.player_messages.get(leaver_id)
            if msg_id:
                user = bot.get_user(leaver_id) or await bot.fetch_user(leaver_id)
                if user:
                    msg = await user.fetch_message(msg_id)
                    embed = discord.Embed(title="Вы вышли из игры", color=0xFFA500)
                    await msg.edit(embed=embed, view=None)
        except Exception as e:
            print(f"Ошибка уведомления вышедшему: {e}")

        for pid in list(game.players):
            if pid == leaver_id:
                continue
            try:
                msg_id = game.player_messages.get(pid)
                if not msg_id:
                    continue
                member = game.guild.get_member(pid)
                if not member:
                    member = await game.guild.fetch_member(pid)
                if not member:
                    continue
                msg = await member.fetch_message(msg_id)
                embed = discord.Embed(
                    title="🧮 Тетрадь",
                    description=game.render_board(),
                    color=0xADD8E6
                )
                if winner_id:
                    embed.add_field(name="Победитель", value=f"<@{winner_id}> (соперник вышел)")
                else:
                    embed.add_field(name="Ходит", value=f"<@{game.turn}>")
                if pid == game.turn and not game.winner:
                    from ui import GameView
                    view = GameView(game, self, pid)
                    await msg.edit(embed=embed, view=view)
                else:
                    await msg.edit(embed=embed, view=None)
            except Exception as e:
                print(f"Ошибка уведомления игрока {pid}: {e}")

    def end_game(self, game_id):
        game = self.games.pop(game_id, None)
        if game:
            for pid in game.players:
                self.player_game.pop(pid, None)
            print(f"Игра #{game_id} завершена и удалена.")

    def is_in_game(self, uid):
        return uid in self.player_game
