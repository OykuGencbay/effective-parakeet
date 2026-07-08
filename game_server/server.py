import base64
import hashlib
import hmac
import json
import math
import os
import random
import socket
import threading
import time
import uuid
HOST = "0.0.0.0"
PORT = 5000
MAP_WIDTH = 1600
MAP_HEIGHT = 1000
PLAYER_SPEED = 260
TANK_SPEED = 190
BULLET_SPEED = 700
TICK_RATE = 30
TANK_ENTER_DISTANCE = 70
TANK_EXIT_DISTANCE = 55
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
VALID_CHARACTERS = {"poe"}
ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "accounts.json")
players = {}
player_inputs = {}
clients = {}
bullets = []
target = {
    "x": random.randint(100, MAP_WIDTH - 100),
    "y": random.randint(100, MAP_HEIGHT - 100),
}
lock = threading.Lock()
account_lock = threading.Lock()
def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return {}
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
accounts = load_accounts()
def save_accounts():
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as file:
        json.dump(accounts, file, indent=2)
def hash_password(password):
    salt = os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120_000,
    )
    salt_text = base64.b64encode(salt).decode("utf-8")
    hash_text = base64.b64encode(password_hash).decode("utf-8")
    return f"{salt_text}${hash_text}"
def check_password(password, stored_hash):
    try:
        salt_text, hash_text = stored_hash.split("$", 1)
        salt = base64.b64decode(salt_text.encode("utf-8"))
        expected_hash = base64.b64decode(hash_text.encode("utf-8"))
    except ValueError:
        return False
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120_000,
    )
    return hmac.compare_digest(password_hash, expected_hash)
def validate_username(username):
    username = str(username).strip()
    if not 3 <= len(username) <= 18:
        return None, "Username must be 3-18 characters."
    if not all(character.isalnum() or character == "_" for character in username):
        return None, "Use only letters, numbers, and underscores."
    return username, ""
def register_account(username, password):
    username, error = validate_username(username)
    if error:
        return False, error, None
    password = str(password)
    if len(password) < 4:
        return False, "Password must be at least 4 characters.", None
    username_key = username.lower()
    with account_lock:
        if username_key in accounts:
            return False, "That username is already taken.", None
        accounts[username_key] = {
            "username": username,
            "password_hash": hash_password(password),
        }
        save_accounts()
    return True, "Registered successfully.", username
def login_account(username, password):
    username = str(username).strip()
    username_key = username.lower()
    with account_lock:
        account = accounts.get(username_key)
    if not account:
        return False, "Account not found.", None
    if not check_password(str(password), account["password_hash"]):
        return False, "Wrong password.", None
    return True, "Logged in successfully.", account["username"]
def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))
def distance(x1, y1, x2, y2):
    return math.hypot(x1 - x2, y1 - y2)
def point_inside_rect(x, y, rect):
    return (
        rect["x"] <= x <= rect["x"] + rect["w"]
        and rect["y"] <= y <= rect["y"] + rect["h"]
    )
def circle_rect_collision(cx, cy, radius, rect):
    closest_x = clamp(cx, rect["x"], rect["x"] + rect["w"])
    closest_y = clamp(cy, rect["y"], rect["y"] + rect["h"])
    return distance(cx, cy, closest_x, closest_y) <= radius
def get_blocking_rects():
    blocking = list(MAP_OBJECTS["walls"])
    for gate in MAP_OBJECTS["gates"]:
        if not gate["open"]:
            blocking.append(gate)
    return blocking
def is_position_blocked(x, y, radius):
    for rect in get_blocking_rects():
        if circle_rect_collision(x, y, radius, rect):
            return True
    return False
def is_on_speed_pad(x, y):
    for pad in MAP_OBJECTS["speed_pads"]:
        if point_inside_rect(x, y, pad):
            return True
    return False
def find_teleporter(teleporter_id):
    for teleporter in MAP_OBJECTS["teleporters"]:
        if teleporter["id"] == teleporter_id:
            return teleporter
    return None
def try_teleport_player(player):
    now = time.time()
    if now < player.get("teleport_cooldown_until", 0):
        return
    for teleporter in MAP_OBJECTS["teleporters"]:
        if distance(player["x"], player["y"], teleporter["x"], teleporter["y"]) <= teleporter["r"]:
            target = find_teleporter(teleporter["target"])
            if target:
                new_x = clamp(target["x"] + 65, 20, MAP_WIDTH - 20)
                new_y = clamp(target["y"], 20, MAP_HEIGHT - 20)
                player["x"] = new_x
                player["y"] = new_y
                if player["in_tank"]:
                    player["tank_x"] = new_x
                    player["tank_y"] = new_y
                player["teleport_cooldown_until"] = now + 1.0
            break
def move_player_with_collision(player, dx, dy, speed, dt, radius):
    old_x = player["x"]
    old_y = player["y"]
    new_x = clamp(old_x + dx * speed * dt, radius, MAP_WIDTH - radius)
    if not is_position_blocked(new_x, old_y, radius):
        player["x"] = new_x
    new_y = clamp(old_y + dy * speed * dt, radius, MAP_HEIGHT - radius)
    if not is_position_blocked(player["x"], new_y, radius):
        player["y"] = new_y
def move_target():
    target["x"] = random.randint(100, MAP_WIDTH - 100)
    target["y"] = random.randint(100, MAP_HEIGHT - 100)
def send_json(connection, data):
    message = json.dumps(data) + "\n"
    connection.sendall(message.encode("utf-8"))
def broadcast(data):
    disconnected = []
    with lock:
        current_clients = [
            connection
            for connection, player_id in clients.items()
            if player_id is not None
        ]
    for connection in current_clients:
        try:
            send_json(connection, data)
        except OSError:
            disconnected.append(connection)

    for connection in disconnected:
        remove_client(connection)
def get_public_state():
    public_players = {}
    for player_id, player in players.items():
        public_players[player_id] = {
            "id": player_id,
            "name": player["name"],
            "character": player.get("character", "poe"),
            "x": player["x"],
            "y": player["y"],
            "tank_x": player["tank_x"],
            "tank_y": player["tank_y"],
            "in_tank": player["in_tank"],
            "score": player["score"],
            "invulnerable": time.time() < player.get("invulnerable_until", 0),
        }
    return {
        "map": {
            "width": MAP_WIDTH,
            "height": MAP_HEIGHT,
        },
        "players": public_players,
        "bullets": bullets,
        "target": target,
        "objects": MAP_OBJECTS,
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
def create_player(player_id, username):
    spawn_x = random.randint(100, MAP_WIDTH - 100)
    spawn_y = random.randint(100, MAP_HEIGHT - 100)
    players[player_id] = {
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
def remove_client(connection):
    should_announce = False
    name = "A player"
    with lock:
        player_id = clients.pop(connection, None)
        if player_id:
            name = players.get(player_id, {}).get("name", "A player")
            players.pop(player_id, None)
            player_inputs.pop(player_id, None)
            should_announce = True
    try:
        connection.close()
    except OSError:
        pass
    if should_announce:
        broadcast({
            "type": "chat",
            "name": "System",
            "message": f"{name} left the map.",
        })
def authenticate_player(connection, player_id, data):
    message_type = data.get("type")
    username = data.get("username", "")
    password = data.get("password", "")
    if message_type == "register":
        success, message, clean_username = register_account(username, password)
    elif message_type == "login":
        success, message, clean_username = login_account(username, password)
    else:
        send_json(connection, {
            "type": "auth_error",
            "message": "Please log in or register first.",
        })
        return False
    if not success:
        send_json(connection, {
            "type": "auth_error",
            "message": message,
        })
        return False
    with lock:
        clients[connection] = player_id
        create_player(player_id, clean_username)
    send_json(connection, {
        "type": "init",
        "player_id": player_id,
    })
    broadcast({
        "type": "chat",
        "name": "System",
        "message": f"{clean_username} joined the map.",
    })
    return True
def handle_client(connection, address):
    player_id = str(uuid.uuid4())[:8]
    authenticated = False
    with lock:
        clients[connection] = None
    send_json(connection, {
        "type": "auth_required",
        "message": "Please log in or register.",
    })
    file = connection.makefile("r", encoding="utf-8")
    try:
        for line in file:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not authenticated:
                authenticated = authenticate_player(connection, player_id, data)
                continue
            message_type = data.get("type")
            chat_message = None
            with lock:
                if player_id not in players:
                    break
                player = players[player_id]
                if message_type == "select_character":
                    character = str(data.get("character", "poe")).lower()
                    if character in VALID_CHARACTERS:
                        player["character"] = character
                if message_type == "interact":
                    for terminal in MAP_OBJECTS["terminals"]:
                        near_terminal = (
                                distance(
                                    player["x"],
                                    player["y"],
                                    terminal["x"],
                                    terminal["y"],
                                )
                                <= 75
                        )
                        if near_terminal:
                            for gate in MAP_OBJECTS["gates"]:
                                if gate["id"] == terminal["gate_id"]:
                                    gate["open"] = not gate["open"]
                                    status = "opened" if gate["open"] else "closed"
                                    chat_message = {
                                        "type": "chat",
                                        "name": "System",
                                        "message": f"{player['name']} {status} the central gate.",
                                    }
                                    break
                elif message_type == "input":
                    player_inputs[player_id] = {
                        "up": bool(data.get("up")),
                        "down": bool(data.get("down")),
                        "left": bool(data.get("left")),
                        "right": bool(data.get("right")),
                    }
                elif message_type == "toggle_tank":
                    if player["in_tank"]:
                        player["in_tank"] = False
                        player["x"] = clamp(
                            player["tank_x"] + TANK_EXIT_DISTANCE,
                            20,
                            MAP_WIDTH - 20,
                        )
                        player["y"] = clamp(
                            player["tank_y"] + TANK_EXIT_DISTANCE,
                            20,
                            MAP_HEIGHT - 20,
                        )
                    else:
                        close_to_tank = (
                            distance(
                                player["x"],
                                player["y"],
                                player["tank_x"],
                                player["tank_y"],
                            )
                            <= TANK_ENTER_DISTANCE
                        )
                        if close_to_tank:
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
                elif message_type == "chat":
                    message = str(data.get("message", "")).strip()[:140]
                    if message:
                        chat_message = {
                            "type": "chat",
                            "name": player["name"],
                            "message": message,
                        }
            if chat_message:
                broadcast(chat_message)
    except OSError:
        pass
    except Exception as error:
        print(f"Client handler error: {error}")
    finally:
        remove_client(connection)
def update_game():
    dt = 1 / TICK_RATE
    hit_messages = []
    with lock:
        # Move players
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
            speed_boost = 1.5 if is_on_speed_pad(player["x"], player["y"]) else 1.0
            if player["in_tank"]:
                player["x"] = player["tank_x"]
                player["y"] = player["tank_y"]
                move_player_with_collision(
                    player,
                    dx,
                    dy,
                    TANK_SPEED * speed_boost,
                    dt,
                    TANK_HIT_RADIUS,
                )
                player["tank_x"] = player["x"]
                player["tank_y"] = player["y"]
            else:
                move_player_with_collision(
                    player,
                    dx,
                    dy,
                    PLAYER_SPEED * speed_boost,
                    dt,
                    PLAYER_HIT_RADIUS,
                )
            try_teleport_player(player)
        for bullet in bullets:
            bullet["x"] += bullet["vx"] * dt
            bullet["y"] += bullet["vy"] * dt
            bullet["age"] += dt
            for rect in get_blocking_rects():
                if point_inside_rect(bullet["x"], bullet["y"], rect):
                    bullet["dead"] = True
                    break
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
        state = get_public_state()
    for message in hit_messages:
        broadcast(message)
    broadcast({
        "type": "state",
        "state": state,
    })
def game_loop():
    while True:
        start = time.time()
        try:
            update_game()
        except Exception as error:
            print(f"Game loop error: {error}")
        elapsed = time.time() - start
        time.sleep(max(0, 1 / TICK_RATE - elapsed))
def main():
    threading.Thread(target=game_loop, daemon=True).start()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"Server running on {HOST}:{PORT}")
    print("Run client with:")
    print("python pygame_client/client.py 127.0.0.1")
    try:
        while True:
            connection, address = server_socket.accept()

            threading.Thread(
                target=handle_client,
                args=(connection, address),
                daemon=True,
            ).start()
    finally:
        server_socket.close()
if __name__ == "__main__":
    main()