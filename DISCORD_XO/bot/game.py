import random
from typing import Dict, Optional, List, Tuple

SIZE = 8
COLUMNS = [chr(ord('A') + i) for i in range(SIZE)]
ROWS = list(range(1, SIZE + 1))
PIECES = ["🔴", "🔺", "🟩", "🔹"]
EMPTY_CELL = "⬜"

class Game:
    def __init__(self, player1_id: int, player2_id: int, game_id: int):
        self.game_id = game_id
        self.players = {player1_id, player2_id}
        available = list(PIECES)
        random.shuffle(available)
        self.piece_of = {player1_id: available[0], player2_id: available[1]}
        self.grid: List[List[Optional[int]]] = [
            [None for _ in range(SIZE)] for _ in range(SIZE)
        ]
        self.turn: int = player1_id
        self.winner: Optional[int] = None
        self.move_count = {player1_id: 0, player2_id: 0}
        self.cleanup_task = None

    def cell_index(self, coord: str) -> Tuple[int, int]:
        coord = coord.upper().strip()
        if len(coord) < 2:
            raise ValueError("Слишком короткая координата")
        col_letter, row_part = coord[0], coord[1:]
        if col_letter not in COLUMNS:
            raise ValueError(f"Недопустимая колонка: {col_letter}")
        col_idx = COLUMNS.index(col_letter)
        try:
            row_num = int(row_part)
        except ValueError:
            raise ValueError("Номер ряда должен быть числом")
        if row_num not in ROWS:
            raise ValueError(f"Номер ряда вне диапазона 1..{SIZE}")
        return row_num - 1, col_idx

    def place_piece(self, player_id: int, coord: str) -> str:
        if player_id not in self.players:
            raise ValueError("Вы не в игре")
        if self.winner is not None:
            raise ValueError("Игра окончена")
        if player_id != self.turn:
            raise ValueError("Не ваш ход")
        row, col = self.cell_index(coord)
        if self.grid[row][col] is not None:
            raise ValueError("Клетка занята")
        self.grid[row][col] = player_id
        self.move_count[player_id] += 1
        if self.check_win(player_id, row, col):
            self.winner = player_id
        else:
            other = next(p for p in self.players if p != player_id)
            self.turn = other
        return self.piece_of[player_id]

    def check_win(self, player_id: int, row: int, col: int) -> bool:
        # строка
        if all(self.grid[row][c] == player_id for c in range(SIZE)):
            return True
        # столбец
        if all(self.grid[r][col] == player_id for r in range(SIZE)):
            return True
        # главная диагональ
        if row == col and all(self.grid[i][i] == player_id for i in range(SIZE)):
            return True
        # побочная диагональ
        if row + col == SIZE - 1 and all(self.grid[i][SIZE - 1 - i] == player_id for i in range(SIZE)):
            return True
        return False

    def to_dict(self):
        """Представление для фронтенда"""
        board = []
        for r in range(SIZE):
            for c in range(SIZE):
                pid = self.grid[r][c]
                board.append(self.piece_of.get(pid, EMPTY_CELL))
        return {
            "board": board,
            "turn": self.turn,
            "winner": self.winner,
            "piece_of": {str(k): v for k, v in self.piece_of.items()},
            "move_count": self.move_count
        }