import asyncio, random
import discord
from typing import Dict, Optional

SIZE = 16
COLS = [chr(ord('A')+i) for i in range(SIZE)]
PIECES = ["🔴","🔺","🟩","🔹"]
EMPTY = "⬜"

class Game:
    def __init__(self, p1_id, p2_id, gid, guild):
        self.id = gid
        self.players = {p1_id, p2_id}
        self.guild = guild
        pieces = list(PIECES)
        random.shuffle(pieces)
        self.piece_of = {p1_id: pieces[0], p2_id: pieces[1]}
        self.grid = [[None]*SIZE for _ in range(SIZE)]
        self.turn = p1_id
        self.winner = None
        self.move_count = {p1_id:0, p2_id:0}
        self.player_messages: Dict[int, int] = {}

    def cell_index(self, coord):
        col = COLS.index(coord[0].upper())
        row = int(coord[1:]) - 1
        return row, col

    def place(self, pid, coord):
        if pid not in self.players: raise ValueError("Не в игре")
        if self.winner: raise ValueError("Игра окончена")
        if pid != self.turn: raise ValueError("Не ваш ход")
        r, c = self.cell_index(coord)
        if self.grid[r][c] is not None: raise ValueError("Клетка занята")
        self.grid[r][c] = pid
        self.move_count[pid] += 1
        if self._check_win(pid, r, c):
            self.winner = pid
        else:
            other = next(p for p in self.players if p != pid)
            self.turn = other
        return self.piece_of[pid]

    def _check_win(self, pid, r, c):
        if all(self.grid[r][x] == pid for x in range(SIZE)): return True
        if all(self.grid[x][c] == pid for x in range(SIZE)): return True
        if r == c and all(self.grid[i][i] == pid for i in range(SIZE)): return True
        if r+c == SIZE-1 and all(self.grid[i][SIZE-1-i] == pid for i in range(SIZE)): return True
        return False

    def remove_player(self, player_id):
        if player_id in self.players:
            self.players.remove(player_id)
            if len(self.players) == 1:
                return next(iter(self.players))
        return None

def render_board(self):
    NBSP = '\u00a0'
    # Заголовок: для каждой буквы делаем "буква + обычный пробел + NBSP" (3 символа), затем разделяем обычным пробелом
    header_cells = [f"{col} {NBSP}" for col in COLS]   # B   (B, пробел, неразрывный пробел)
    # Начальный отступ: 4 пробела (под двузначный номер строки + разделитель)
    header = "    " + " ".join(header_cells)
    lines = [header]
    for i in range(SIZE):
        row_cells = []
        for j in range(SIZE):
            pid = self.grid[i][j]
            row_cells.append(self.piece_of[pid] if pid else EMPTY)   # эмодзи = 2 символа
        # Номер строки: два символа + обычный пробел + NBSP, чтобы занять ровно 4 символа как у заголовка
        lines.append(f"{i+1:2} {NBSP}" + " ".join(row_cells))
    return "```\n" + "\n".join(lines) + "```"


class GameManager:
    def __init__(self, db):
        self.queue = []
        self.games: Dict[int, Game] = {}
        self.player_game: Dict[int, int] = {}
        self.next_id = 1
        self.db = db

    async def add_to_queue(self, uid, guild):
        if uid in self.player_game: return "Вы уже в игре"
        if uid in self.queue: return "Вы уже в очереди"
        self.queue.append(uid)
        if len(self.queue) >= 2:
            p1 = self.queue.pop(0)
            p2 = self.queue.pop(0)
            gid = self.next_id
            self.next_id += 1
            game = Game(p1, p2, gid, guild)
            self.games[gid] = game
            self.player_game[p1] = gid
            self.player_game[p2] = gid
            return f"Соперник найден! Игра #{gid} начинается."
        return "Ожидание соперника..."

    async def remove_from_queue(self, uid):
        if uid in self.queue:
            self.queue.remove(uid)
            return "Вы покинули очередь"
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
        return f"Вы поставили {piece} на {coord}. Ход соперника.", game

    async def player_exit(self, user_id):
        if user_id in self.queue:
            self.queue.remove(user_id)
            return "Вы покинули очередь."

        gid = self.player_game.get(user_id)
        if not gid:
            return "Вы не находитесь в игре."

        game = self.games.get(gid)
        if not game:
            self.player_game.pop(user_id, None)
            return "Игра не найдена."

        remaining = game.remove_player(user_id)
        self.player_game.pop(user_id, None)

        if remaining is not None:
            game.winner = remaining
            await self.db.add_win(remaining)
            await self._notify_exit(game, user_id)
            self.end_game(gid)
            return "Вы вышли из игры. Победитель определён."
        else:
            self.end_game(gid)
            return "Вы вышли из игры. Игра завершена."

    async def _notify_exit(self, game, leaver_id):
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
            print(f"Не удалось уведомить вышедшего: {e}")

        winner_id = game.winner
        if winner_id:
            try:
                msg_id = game.player_messages.get(winner_id)
                if msg_id:
                    member = game.guild.get_member(winner_id)
                    if not member:
                        member = await game.guild.fetch_member(winner_id)
                    if member:
                        msg = await member.fetch_message(msg_id)
                        embed = discord.Embed(
                            title="🧮 Тетрадь",
                            description=game.render_board(),
                            color=0xADD8E6
                        )
                        embed.add_field(name="Победитель", value=f"<@{winner_id}> (соперник вышел)")
                        await msg.edit(embed=embed, view=None)
            except Exception as e:
                print(f"Не удалось уведомить победителя: {e}")

    def end_game(self, game_id):
        game = self.games.pop(game_id, None)
        if game:
            for pid in game.players:
                self.player_game.pop(pid, None)
            print(f"Игра #{game_id} завершена и удалена.")

    def is_in_game(self, uid):
        return uid in self.player_game
