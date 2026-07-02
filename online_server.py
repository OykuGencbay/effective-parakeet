import asyncio
import json
import os
import random
import time
import math
import websockets

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 10000))

MAP_WIDTH = 1600
MAP_HEIGHT = 1000

PLAYER_SPEED = 260
TANK_SPEED = 190
BULLET_SPEED = 700
TICK_RATE = 30

PLAYER_HIT_RADIUS = 18
TANK_HIT_RADIUS = 34
SPAWN_INVULNERABILITY_SECONDS = 1.5
MAP_OBJECTS = {
    "walls": [
        {"x": 220, "y": 150, "w": 360, "h": 35},
        {"x": 1020, "y": 150, "w": 360, "h": 35},

        {"x": 220, "y": 815, "w": 360, "h": 35},
        {"x": 1020, "y": 815, "w": 360, "h": 35},

        {"x": 380, "y": 340, "w": 35, "h": 260},
        {"x": 1185, "y": 340, "w": 35, "h": 260},

        {"x": 620, "y": 480, "w": 130, "h": 35},
        {"x": 850, "y": 480, "w": 130, "h": 35},
    ],

    "gates": [
        {
            "id": "center_gate",
            "x": 780,
            "y": 405,
            "w": 40,
            "h": 190,
            "open": False,
        }
    ],

    "speed_pads": [
        {"x": 95, "y": 790, "w": 150, "h": 90},
        {"x": 1355, "y": 120, "w": 150, "h": 90},
    ],

    "teleporters": [
        {"id": "tp_a", "x": 135, "y": 135, "r": 38, "target": "tp_b"},
        {"id": "tp_b", "x": 1465, "y": 865, "r": 38, "target": "tp_a"},
    ],

    "terminals": [
        {
            "id": "gate_terminal",
            "x": 800,
            "y": 355,
            "r": 35,
            "gate_id": "center_gate",
        }
    ],
}

players = {}
player_inputs = {}
clients = {}
bullets = []

state_lock = asyncio.Lock()


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def distance(x1, y1, x2, y2):
    return math.hypot(x1 - x2, y1 - y2)


def make_player(player_id, username):
    spawn_x = random.randint(100, MAP_WIDTH - 100)
    spawn_y = random.randint(100, MAP_HEIGHT - 100)

    players[player_id] = {
        "id": player_id,
        "name": username,
        "character": "poe",
        "x": spawn_x,
        "y": spawn_y,
        "tank_x": clamp(spawn_x + 80, 20, MAP_WIDTH - 20),
        "tank_y": spawn_y,
        "in_tank": False,
        "score": 0,
        "last_shot": 0,
        "invulnerable_until": time.time() + SPAWN_INVULNERABILITY_SECONDS,
    }

    player_inputs[player_id] = {
        "up": False,
        "down": False,
        "left": False,
        "right": False,
    }


def respawn_player(player):
    spawn_x = random.randint(100, MAP_WIDTH - 100)
    spawn_y = random.randint(100, MAP_HEIGHT - 100)

    player["x"] = spawn_x
    player["y"] = spawn_y
    player["tank_x"] = clamp(spawn_x + 80, 20, MAP_WIDTH - 20)
    player["tank_y"] = spawn_y
    player["in_tank"] = False
    player["invulnerable_until"] = time.time() + SPAWN_INVULNERABILITY_SECONDS


def public_state():
    now = time.time()

    return {
        "map": {
            "width": MAP_WIDTH,
            "height": MAP_HEIGHT,
        },
        "players": {
            player_id: {
                "id": player_id,
                "name": player["name"],
                "character": player.get("character", "poe"),
                "x": player["x"],
                "y": player["y"],
                "tank_x": player["tank_x"],
                "tank_y": player["tank_y"],
                "in_tank": player["in_tank"],
                "score": player["score"],
                "invulnerable": now < player.get("invulnerable_until", 0),
            }
            for player_id, player in players.items()
        },
        "bullets": [bullet.copy() for bullet in bullets],
        "objects": MAP_OBJECTS,
    }


async def send_json(websocket, data):
    await websocket.send(json.dumps(data))


async def broadcast(data):
    dead = []

    for websocket in list(clients.keys()):
        try:
            await send_json(websocket, data)
        except Exception:
            dead.append(websocket)

    for websocket in dead:
        await remove_client(websocket)


async def remove_client(websocket):
    async with state_lock:
        player_id = clients.pop(websocket, None)

        if player_id:
            player = players.pop(player_id, None)
            player_inputs.pop(player_id, None)
            name = player["name"] if player else "A player"
        else:
            name = "A player"

    await broadcast({
        "type": "chat",
        "name": "System",
        "message": f"{name} left the arena.",
    })


async def handle_message(player_id, data):
    message_type = data.get("type")

    async with state_lock:
        if player_id not in players:
            return

        player = players[player_id]

        if message_type == "input":
            player_inputs[player_id] = {
                "up": bool(data.get("up")),
                "down": bool(data.get("down")),
                "left": bool(data.get("left")),
                "right": bool(data.get("right")),
            }

        elif message_type == "toggle_tank":
            if player["in_tank"]:
                player["in_tank"] = False
                player["x"] = clamp(player["tank_x"] + 55, 20, MAP_WIDTH - 20)
                player["y"] = clamp(player["tank_y"] + 55, 20, MAP_HEIGHT - 20)
            else:
                close_enough = distance(
                    player["x"],
                    player["y"],
                    player["tank_x"],
                    player["tank_y"],
                ) <= 70

                if close_enough:
                    player["in_tank"] = True
                    player["x"] = player["tank_x"]
                    player["y"] = player["tank_y"]

        elif message_type == "shoot":
            now = time.time()

            if now - player["last_shot"] >= 0.25:
                player["last_shot"] = now

                dx = float(data.get("dx", 0))
                dy = float(data.get("dy", -1))
                length = math.hypot(dx, dy)

                if length > 0:
                    dx /= length
                    dy /= length

                    bullets.append({
                        "x": player["x"],
                        "y": player["y"],
                        "vx": dx * BULLET_SPEED,
                        "vy": dy * BULLET_SPEED,
                        "owner": player_id,
                        "age": 0,
                    })

        elif message_type == "select_character":
            player["character"] = "poe"

        elif message_type == "chat":
            message = str(data.get("message", "")).strip()[:140]

            if message:
                await broadcast({
                    "type": "chat",
                    "name": player["name"],
                    "message": message,
                })


async def websocket_handler(websocket):
    player_id = str(random.randint(100000, 999999))
    username = f"Player-{player_id}"

    try:
        first_message = await websocket.recv()
        data = json.loads(first_message)

        if data.get("type") in ["login", "register"]:
            username = str(data.get("username", username)).strip()[:18] or username

        async with state_lock:
            clients[websocket] = player_id
            make_player(player_id, username)

        await send_json(websocket, {
            "type": "init",
            "player_id": player_id,
        })

        await broadcast({
            "type": "chat",
            "name": "System",
            "message": f"{username} joined the arena.",
        })

        async for message in websocket:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue

            await handle_message(player_id, data)

    except Exception as error:
        print("Client error:", error)

    finally:
        await remove_client(websocket)


async def game_loop():
    while True:
        dt = 1 / TICK_RATE
        hit_messages = []

        async with state_lock:
            for player_id, player in players.items():
                keys = player_inputs.get(player_id, {})

                dx = 0
                dy = 0

                if keys.get("up"):
                    dy -= 1
                if keys.get("down"):
                    dy += 1
                if keys.get("left"):
                    dx -= 1
                if keys.get("right"):
                    dx += 1

                length = math.hypot(dx, dy)

                if length > 0:
                    dx /= length
                    dy /= length

                speed = TANK_SPEED if player["in_tank"] else PLAYER_SPEED

                player["x"] = clamp(player["x"] + dx * speed * dt, 20, MAP_WIDTH - 20)
                player["y"] = clamp(player["y"] + dy * speed * dt, 20, MAP_HEIGHT - 20)

                if player["in_tank"]:
                    player["tank_x"] = player["x"]
                    player["tank_y"] = player["y"]

            for bullet in bullets:
                bullet["x"] += bullet["vx"] * dt
                bullet["y"] += bullet["vy"] * dt
                bullet["age"] += dt

            now = time.time()

            for bullet in bullets:
                if bullet.get("dead"):
                    continue

                shooter_id = bullet.get("owner")

                if shooter_id not in players:
                    bullet["dead"] = True
                    continue

                shooter = players[shooter_id]

                for victim_id, victim in players.items():
                    if victim_id == shooter_id:
                        continue

                    if now < victim.get("invulnerable_until", 0):
                        continue

                    hit_radius = TANK_HIT_RADIUS if victim["in_tank"] else PLAYER_HIT_RADIUS

                    if distance(bullet["x"], bullet["y"], victim["x"], victim["y"]) <= hit_radius:
                        shooter["score"] += 1
                        bullet["dead"] = True

                        hit_messages.append({
                            "type": "chat",
                            "name": "System",
                            "message": f"{shooter['name']} hit {victim['name']}! +1 point",
                        })

                        respawn_player(victim)
                        break

            bullets[:] = [
                bullet for bullet in bullets
                if not bullet.get("dead")
                and bullet["age"] < 2
                and 0 <= bullet["x"] <= MAP_WIDTH
                and 0 <= bullet["y"] <= MAP_HEIGHT
            ]

            state = public_state()

        for message in hit_messages:
            await broadcast(message)

        await broadcast({
            "type": "state",
            "state": state,
        })

        await asyncio.sleep(1 / TICK_RATE)


async def main():
    print(f"Starting WebSocket server on {HOST}:{PORT}")

    async with websockets.serve(websocket_handler, HOST, PORT):
        await game_loop()


if __name__ == "__main__":
    asyncio.run(main())