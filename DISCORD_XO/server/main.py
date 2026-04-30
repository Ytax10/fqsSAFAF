import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from game import Game

app = FastAPI()

games = {}
queue = []
connections = {}
next_game_id = 1

# Монтируем папку static в корень
app.mount("/", StaticFiles(directory="../static", html=True), name="static")

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
        opp_id, opp_ws = queue.pop(0)
        game_id = next_game_id
        next_game_id += 1
        game = Game(opp_id, user_id, game_id)
        games[game_id] = game

        await opp_ws.send_json({
            "type": "start", "your_turn": True,
            "piece": game.piece_of[opp_id], "state": game.state_dict()
        })
        await websocket.send_json({
            "type": "start", "your_turn": False,
            "piece": game.piece_of[user_id], "state": game.state_dict()
        })

        asyncio.create_task(player_loop(opp_ws, opp_id, game_id))
        asyncio.create_task(player_loop(websocket, user_id, game_id))
    else:
        queue.append((user_id, websocket))
        await websocket.send_json({"type": "waiting"})

async def player_loop(ws, user_id, game_id):
    try:
        while True:
            msg = await ws.receive_json()
            coord = msg.get("coord")
            if not coord: continue
            game = games.get(game_id)
            if not game:
                await ws.send_json({"type": "error", "message": "Игра не найдена"})
                continue
            try:
                game.place(user_id, coord)
            except ValueError as e:
                await ws.send_json({"type": "error", "message": str(e)})
                continue

            state = game.state_dict()
            for pid in game.players:
                if pid in connections:
                    await connections[pid].send_json({"type": "update", "state": state})

            if game.winner:
                for pid in game.players:
                    if pid in connections:
                        await connections[pid].send_json({
                            "type": "gameover", "winner": game.winner, "state": state
                        })
                asyncio.create_task(cleanup(game_id))
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
        queue = [(u, w) for u, w in queue if u != user_id]

async def cleanup(gid):
    await asyncio.sleep(60)
    game = games.pop(gid, None)
    if game:
        for p in game.players:
            connections.pop(p, None)