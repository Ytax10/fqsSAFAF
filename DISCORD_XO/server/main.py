import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from game import Game

app = FastAPI()

# ------------------- Разрешаем Discord встраивать приложение (iframe) -------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "ALLOW-FROM https://discord.com"
        response.headers["Content-Security-Policy"] = "frame-ancestors https://discord.com;"
        response.headers["Access-Control-Allow-Origin"] = "https://discord.com"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ------------------- Монтируем папку static в корень -------------------
app.mount("/", StaticFiles(directory="../static", html=True), name="static")

# ------------------- Хранилище игр -------------------
games = {}
queue = []                     # пары (user_id, websocket)
connections = {}               # user_id -> websocket
next_game_id = 1

# ------------------- WebSocket эндпоинт -------------------
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    global next_game_id
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        user_id = data.get("user_id")
    except:
        await websocket.close()
        return

    connections[user_id] = websocket

    if queue:
        # Забираем соперника из очереди
        opp_id, opp_ws = queue.pop(0)
        game_id = next_game_id
        next_game_id += 1
        game = Game(opp_id, user_id, game_id)
        games[game_id] = game

        # Отправляем старт обоим
        await opp_ws.send_json({
            "type": "start", "your_turn": True,
            "piece": game.piece_of[opp_id], "state": game.state_dict()
        })
        await websocket.send_json({
            "type": "start", "your_turn": False,
            "piece": game.piece_of[user_id], "state": game.state_dict()
        })

        # Запускаем циклы приёма сообщений
        asyncio.create_task(player_loop(opp_ws, opp_id, game_id))
        asyncio.create_task(player_loop(websocket, user_id, game_id))
    else:
        queue.append((user_id, websocket))
        await websocket.send_json({"type": "waiting"})

# ------------------- Цикл обработки ходов игрока -------------------
async def player_loop(ws: WebSocket, user_id: str, game_id: int):
    try:
        while True:
            msg = await ws.receive_json()
            coord = msg.get("coord")
            if not coord:
                continue
            game = games.get(game_id)
            if not game:
                await ws.send_json({"type": "error", "message": "Игра не найдена"})
                continue
            try:
                game.place(user_id, coord)
            except ValueError as e:
                await ws.send_json({"type": "error", "message": str(e)})
                continue

            # Рассылаем обновление всем игрокам
            state = game.state_dict()
            for pid in game.players:
                if pid in connections:
                    await connections[pid].send_json({"type": "update", "state": state})

            if game.winner:
                # Финальное сообщение
                for pid in game.players:
                    if pid in connections:
                        await connections[pid].send_json({
                            "type": "gameover", "winner": game.winner, "state": state
                        })
                asyncio.create_task(cleanup_game(game_id))
                break
    except WebSocketDisconnect:
        game = games.get(game_id)
        if game:
            other = next((p for p in game.players if p != user_id), None)
            if other and other in connections:
                await connections[other].send_json({"type": "opponent_left"})
        games.pop(game_id, None)
        for p in (game.players if game else []):
            connections.pop(p, None)
        global queue
        queue = [(uid, w) for uid, w in queue if uid != user_id]

# ------------------- Удаление игры через 60 секунд -------------------
async def cleanup_game(game_id):
    await asyncio.sleep(60)
    game = games.pop(game_id, None)
    if game:
        for p in game.players:
            connections.pop(p, None)