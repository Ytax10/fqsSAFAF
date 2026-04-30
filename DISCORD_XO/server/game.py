import random

SIZE = 8
COLUMNS = [chr(ord('A') + i) for i in range(SIZE)]
PIECES = ["🔴", "🔺", "🟩", "🔹"]
EMPTY = "⬜"

class Game:
    def __init__(self, p1_id, p2_id, game_id):
        self.id = game_id
        self.players = {p1_id, p2_id}
        pieces = list(PIECES)
        random.shuffle(pieces)
        self.piece_of = {p1_id: pieces[0], p2_id: pieces[1]}
        self.grid = [[None]*SIZE for _ in range(SIZE)]
        self.turn = p1_id
        self.winner = None
        self.move_count = {p1_id: 0, p2_id: 0}

    def coord_to_index(self, coord):
        col_letter = coord[0].upper()
        row_num = int(coord[1:])
        col = COLUMNS.index(col_letter)
        row = row_num - 1
        return row, col

    def place(self, player_id, coord):
        if player_id not in self.players:
            raise ValueError("Вы не в игре")
        if self.winner:
            raise ValueError("Игра окончена")
        if player_id != self.turn:
            raise ValueError("Не ваш ход")
        row, col = self.coord_to_index(coord)
        if self.grid[row][col] is not None:
            raise ValueError("Клетка занята")
        self.grid[row][col] = player_id
        self.move_count[player_id] += 1
        if self._check_win(player_id, row, col):
            self.winner = player_id
        else:
            other = next(p for p in self.players if p != player_id)
            self.turn = other
        return self.piece_of[player_id]

    def _check_win(self, player_id, row, col):
        if all(self.grid[row][c] == player_id for c in range(SIZE)): return True
        if all(self.grid[r][col] == player_id for r in range(SIZE)): return True
        if row == col and all(self.grid[i][i] == player_id for i in range(SIZE)): return True
        if row + col == SIZE-1 and all(self.grid[i][SIZE-1-i] == player_id for i in range(SIZE)): return True
        return False

    def board_array(self):
        res = []
        for r in range(SIZE):
            for c in range(SIZE):
                pid = self.grid[r][c]
                res.append(self.piece_of[pid] if pid else EMPTY)
        return res

    def state_dict(self):
        return {
            "board": self.board_array(),
            "turn": self.turn,
            "winner": self.winner,
            "piece_of": self.piece_of,
            "move_count": self.move_count
        }