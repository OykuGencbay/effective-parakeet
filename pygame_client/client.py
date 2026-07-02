import copy
import json
import socket
import sys
import threading
import time
import pygame
import websocket
SERVER_URL = "ws://127.0.0.1:10000"
PORT = 5000
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 680
SIDEBAR_WIDTH = 300
GAME_WIDTH = WINDOW_WIDTH - SIDEBAR_WIDTH
FPS = 60
BLACK = (2, 7, 18)
DARK_BLUE = (6, 20, 38)
GRID_BLUE = (13, 85, 160)
NEON_BLUE = (20, 150, 255)
LIGHT_BLUE = (110, 210, 255)
WHITE = (235, 248, 255)
GREY_BLUE = (130, 175, 210)
TANK_BODY = (5, 45, 95)
TANK_DARK = (3, 25, 55)
TANK_TRACK = (8, 75, 140)
HUMAN_BODY = (40, 170, 255)
HUMAN_HEAD = (230, 240, 255)
ERROR_RED = (255, 110, 130)
SUCCESS_GREEN = (120, 255, 190)
POE_UNIFORM = (62, 85, 45)
POE_UNIFORM_DARK = (35, 55, 28)
POE_HAIR = (85, 50, 30)
POE_SKIN = (220, 190, 165)
POE_BOOTS = (62, 85, 45)
state = None
my_id = None
chat_messages = []
running = True
auth_success = False
auth_message = "Choose Login or Register."
auth_mode = "login"
CHARACTERS = {
    "poe": {
        "name": "Poe",
        "age": "19",
        "profession": "Army Cadet",
        "likes": "Instant Noodles, Onesies",
        "dislikes": "Situations That Are Not Under Control",
        "backstory": "In this world, everyone's direction of lives are being shaped by the household they were born in. Poe was not very fortunate about that. His mother died following the birth of his now-deceased little brother, Rick. As a result of that, he was forced to live with his gaming-addicted father. Due to his father's neglect, he was forced to devour the only person he has left and as a result of this crime, he was placed in the system. His childish heart was filled with hatred and violence, and he became fascinated with millitary paraphelenia. Now, he's seeking comfort on the frontlines of Blue Night Arena when he's off-duty.",
    }
}
state_lock = threading.Lock()
send_lock = threading.Lock()
def send_json(ws, data):
    with send_lock:
        try:
            ws.send(json.dumps(data))
        except Exception:
            pass
def network_reader(ws):
    global state, my_id, running, auth_success, auth_message
    try:
        while running:
            message = ws.recv()
            data = json.loads(message)
            with state_lock:
                if data.get("type") == "auth_required":
                    auth_message = data.get("message", "Please log in or register.")
                elif data.get("type") == "auth_error":
                    auth_message = data.get("message", "Login failed.")
                elif data.get("type") == "init":
                    my_id = data["player_id"]
                    auth_success = True
                    auth_message = "Success!"
                elif data.get("type") == "state":
                    state = data["state"]
                elif data.get("type") == "chat":
                    name = data.get("name", "Unknown")
                    message = data.get("message", "")
                    chat_messages.append((name, message))
                    del chat_messages[:-12]
    except Exception as error:
        print("Disconnected from server:", error)
        running = False
def draw_text(surface, font, text, x, y, color=WHITE, center=False):
    image = font.render(text, True, color)
    rect = image.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    surface.blit(image, rect)
def draw_auth_box(screen, font, small_font, mode, active_field, username, password, message):
    screen.fill(BLACK)
    panel = pygame.Rect(315, 120, 470, 430)
    pygame.draw.rect(screen, DARK_BLUE, panel, border_radius=12)
    pygame.draw.rect(screen, NEON_BLUE, panel, 2, border_radius=12)
    title = "Create Account" if mode == "register" else "Login"
    draw_text(screen, font, "Blue Night Arena", WINDOW_WIDTH // 2, 155, LIGHT_BLUE, center=True)
    draw_text(screen, font, title, WINDOW_WIDTH // 2, 195, WHITE, center=True)
    username_rect = pygame.Rect(380, 260, 340, 38)
    password_rect = pygame.Rect(380, 335, 340, 38)
    draw_text(screen, small_font, "Username", username_rect.x, username_rect.y - 24, GREY_BLUE)
    draw_text(screen, small_font, "Password", password_rect.x, password_rect.y - 24, GREY_BLUE)
    username_border = NEON_BLUE if active_field == "username" else GRID_BLUE
    password_border = NEON_BLUE if active_field == "password" else GRID_BLUE
    pygame.draw.rect(screen, BLACK, username_rect, border_radius=6)
    pygame.draw.rect(screen, username_border, username_rect, 2, border_radius=6)
    pygame.draw.rect(screen, BLACK, password_rect, border_radius=6)
    pygame.draw.rect(screen, password_border, password_rect, 2, border_radius=6)
    draw_text(screen, small_font, username, username_rect.x + 10, username_rect.y + 10, WHITE)
    masked_password = "*" * len(password)
    draw_text(screen, small_font, masked_password, password_rect.x + 10, password_rect.y + 10, WHITE)
    message_color = SUCCESS_GREEN if message == "Success!" else ERROR_RED
    draw_text(screen, small_font, message, WINDOW_WIDTH // 2, 410, message_color, center=True)
    draw_text(screen, small_font, "Enter: submit    Tab: switch field    L: login    R: register", WINDOW_WIDTH // 2, 465, GREY_BLUE, center=True)
def auth_screen(screen, clock, font, small_font, sock, starting_username=""):
    global auth_mode, running
    username = starting_username
    password = ""
    active_field = "username"
    while running:
        clock.tick(FPS)
        with state_lock:
            success = auth_success
            message = auth_message
        if success:
            return True
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    return False
                elif event.key == pygame.K_TAB:
                    active_field = "password" if active_field == "username" else "username"
                elif event.key == pygame.K_l:
                    auth_mode = "login"
                elif event.key == pygame.K_r:
                    auth_mode = "register"
                elif event.key == pygame.K_RETURN:
                    if username.strip() and password:
                        send_json(sock, {
                            "type": auth_mode,
                            "username": username.strip(),
                            "password": password,
                        })
                elif event.key == pygame.K_BACKSPACE:
                    if active_field == "username":
                        username = username[:-1]
                    else:
                        password = password[:-1]
                elif event.unicode:
                    if active_field == "username":
                        if len(username) < 18 and (event.unicode.isalnum() or event.unicode == "_"):
                            username += event.unicode
                    else:
                        if len(password) < 32 and event.unicode not in "\r\n\t":
                            password += event.unicode
        draw_auth_box(
            screen,
            font,
            small_font,
            auth_mode,
            active_field,
            username,
            password,
            message,
        )
        pygame.display.flip()
    return False
def get_camera(current_state):
    if not current_state:
        return {"x": 0, "y": 0}
    if not my_id:
        return {"x": 0, "y": 0}
    if my_id not in current_state["players"]:
        return {"x": 0, "y": 0}
    me = current_state["players"][my_id]
    return {
        "x": me["x"] - GAME_WIDTH / 2,
        "y": me["y"] - WINDOW_HEIGHT / 2,
    }
def draw_grid(screen, camera):
    grid_size = 80
    for x in range(int(-camera["x"] % grid_size), GAME_WIDTH, grid_size):
        pygame.draw.line(screen, GRID_BLUE, (x, 0), (x, WINDOW_HEIGHT), 1)
    for y in range(int(-camera["y"] % grid_size), WINDOW_HEIGHT, grid_size):
        pygame.draw.line(screen, GRID_BLUE, (0, y), (GAME_WIDTH, y), 1)
def draw_tank(screen, x, y, occupied=False, is_me=False):
    body_color = LIGHT_BLUE if is_me else TANK_BODY
    pygame.draw.rect(screen, TANK_TRACK, (x - 38, y - 25, 76, 14), border_radius=4)
    pygame.draw.rect(screen, TANK_TRACK, (x - 38, y + 11, 76, 14), border_radius=4)
    pygame.draw.rect(screen, body_color, (x - 32, y - 20, 64, 40), border_radius=6)
    pygame.draw.rect(screen, WHITE, (x - 32, y - 20, 64, 40), 2, border_radius=6)
    pygame.draw.circle(screen, TANK_DARK, (x, y), 16)
    pygame.draw.circle(screen, WHITE, (x, y), 16, 2)
    pygame.draw.rect(screen, LIGHT_BLUE, (x + 12, y - 5, 38, 10), border_radius=4)
    if occupied:
        pygame.draw.rect(screen, POE_UNIFORM, (x - 7, y - 22, 14, 15))
        pygame.draw.rect(screen, POE_HAIR, (x - 8, y - 36, 16, 18))
        pygame.draw.rect(screen, POE_SKIN, (x - 6, y - 34, 12, 12))
        pygame.draw.rect(screen, WHITE, (x - 6, y - 34, 12, 12), 1)
        pygame.draw.rect(screen, POE_HAIR, (x - 6, y - 36, 12, 4))
def draw_character_select_screen(screen, font, small_font):
    screen.fill(BLACK)
    panel = pygame.Rect(250, 80, 600, 520)
    pygame.draw.rect(screen, DARK_BLUE, panel, border_radius=14)
    pygame.draw.rect(screen, NEON_BLUE, panel, 2, border_radius=14)
    draw_text(
        screen,
        font,
        "Choose Your Character",
        WINDOW_WIDTH // 2,
        120,
        LIGHT_BLUE,
        center=True,
    )
    card = pygame.Rect(400, 200, 405, 350)
    pygame.draw.rect(screen, BLACK, card, border_radius=12)
    pygame.draw.rect(screen, LIGHT_BLUE, card, 3, border_radius=12)
    draw_text(screen, font, "Poe", WINDOW_WIDTH // 2, 205, WHITE, center=True)
    draw_text(screen, small_font, "Army Cadet", WINDOW_WIDTH // 2, 238, GREY_BLUE, center=True)
    preview_x = WINDOW_WIDTH // 2
    preview_y = 330
    draw_poe(screen, preview_x, preview_y, is_me=True)
    button = pygame.Rect(450, 505, 200, 42)
    pygame.draw.rect(screen, NEON_BLUE, button, border_radius=8)
    draw_text(screen, small_font, "ENTER: Select Poe", WINDOW_WIDTH // 2, 518, WHITE, center=True)
    draw_text(
        screen,
        small_font,
        "Esc: quit",
        WINDOW_WIDTH // 2,
        565,
        GREY_BLUE,
        center=True,
    )
def draw_poe(screen, x, y, is_me=False):
    outline = WHITE if is_me else GREY_BLUE
    pygame.draw.rect(screen, POE_BOOTS, (x - 8, y + 8, 6, 13))
    pygame.draw.rect(screen, POE_BOOTS, (x + 2, y + 8, 6, 13))
    pygame.draw.rect(screen, POE_UNIFORM, (x - 11, y - 10, 22, 21))
    pygame.draw.rect(screen, POE_UNIFORM_DARK, (x - 17, y - 8, 6, 16))
    pygame.draw.rect(screen, POE_UNIFORM_DARK, (x + 11, y - 8, 6, 16))
    pygame.draw.rect(screen, POE_SKIN, (x - 4, y - 15, 8, 6))
    pygame.draw.rect(screen, POE_HAIR, (x - 9, y - 31, 18, 9))
    pygame.draw.rect(screen, POE_SKIN, (x - 8, y - 27, 16, 15))
    pygame.draw.rect(screen, POE_HAIR, (x - 8, y - 29, 16, 5))
    pygame.draw.rect(screen, POE_HAIR, (x - 8, y - 25, 5, 4))
    pygame.draw.rect(screen, POE_HAIR, (x + 3, y - 25, 5, 3))
    pygame.draw.rect(screen, BLACK, (x - 5, y - 22, 2, 2))
    pygame.draw.rect(screen, BLACK, (x + 3, y - 22, 2, 2))
    pygame.draw.rect(screen, TANK_DARK, (x - 11, y + 3, 22, 3))
    pygame.draw.rect(screen, BLACK, (x - 9, y + 20, 8, 3))
    pygame.draw.rect(screen, BLACK, (x + 1, y + 20, 8, 3))
def draw_scaled_poe(screen, x, y, scale=2.0):
    base_width = 80
    base_height = 100
    poe_surface = pygame.Surface((base_width, base_height), pygame.SRCALPHA)
    draw_poe(poe_surface, base_width // 2, 65, is_me=True)
    scaled_width = int(base_width * scale)
    scaled_height = int(base_height * scale)
    scaled_surface = pygame.transform.scale(
        poe_surface,
        (scaled_width, scaled_height)
    )
    rect = scaled_surface.get_rect(center=(x, y))
    screen.blit(scaled_surface, rect)
def draw_wrapped_text(surface, font, text, x, y, max_width, color=WHITE, line_gap=4, max_lines=None):
    words = text.split(" ")
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + word + " "
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line.strip())
            current_line = word + " "
    if current_line:
        lines.append(current_line.strip())
    if max_lines:
        lines = lines[:max_lines]
    for line in lines:
        draw_text(surface, font, line, x, y, color)
        y += font.get_height() + line_gap
    return y
def draw_character_select_screen(screen, font, small_font):
    info_font = pygame.font.SysFont("arial", 13)
    screen.fill(BLACK)
    poe = CHARACTERS["poe"]
    panel = pygame.Rect(200, 40, 700, 600)
    pygame.draw.rect(screen, DARK_BLUE, panel, border_radius=14)
    pygame.draw.rect(screen, NEON_BLUE, panel, 2, border_radius=14)
    draw_text(
        screen,
        font,
        "Choose Your Character",
        WINDOW_WIDTH // 2,
        75,
        LIGHT_BLUE,
        center=True,
    )
    card = pygame.Rect(290, 120, 520, 455)
    pygame.draw.rect(screen, BLACK, card, border_radius=12)
    pygame.draw.rect(screen, LIGHT_BLUE, card, 3, border_radius=12)
    draw_text(screen, font, poe["name"], WINDOW_WIDTH // 2, 145, WHITE, center=True)
    preview_x = WINDOW_WIDTH // 2
    preview_y = 230
    draw_scaled_poe(screen, preview_x, preview_y + 5, scale=2.0)
    info_x = card.x + 28
    info_y = 315
    max_width = card.width - 56
    draw_text(screen, info_font, f"Age: {poe['age']}", info_x, info_y, GREY_BLUE)
    info_y += 19
    draw_text(screen, info_font, f"Profession: {poe['profession']}", info_x, info_y, GREY_BLUE)
    info_y += 19
    draw_text(screen, info_font, f"Likes: {poe['likes']}", info_x, info_y, GREY_BLUE)
    info_y += 19
    info_y = draw_wrapped_text(
        screen,
        info_font,
        f"Dislikes: {poe['dislikes']}",
        info_x,
        info_y,
        max_width,
        GREY_BLUE,
        line_gap=1,
        max_lines=2,
    )
    info_y += 10
    draw_text(screen, info_font, "Backstory:", info_x, info_y, LIGHT_BLUE)
    info_y += 19
    draw_wrapped_text(
        screen,
        info_font,
        poe["backstory"],
        info_x,
        info_y,
        max_width,
        WHITE,
        line_gap=1,
        max_lines=10,
    )
    button = pygame.Rect(450, 590, 200, 38)
    pygame.draw.rect(screen, NEON_BLUE, button, border_radius=8)
    draw_text(
        screen,
        small_font,
        "ENTER: Select Poe",
        WINDOW_WIDTH // 2,
        601,
        WHITE,
        center=True,
    )
def draw_players(screen, current_state, camera, small_font):
    for player in current_state["players"].values():
        is_me = player["id"] == my_id
        player_x = int(player["x"] - camera["x"])
        player_y = int(player["y"] - camera["y"])
        tank_x = int(player["tank_x"] - camera["x"])
        tank_y = int(player["tank_y"] - camera["y"])
        if player["in_tank"]:
            draw_tank(screen, tank_x, tank_y, occupied=True, is_me=is_me)
            if player.get("invulnerable"):
                pygame.draw.circle(screen, LIGHT_BLUE, (tank_x, tank_y), 48, 2)
            draw_text(
                screen,
                small_font,
                player["name"],
                tank_x,
                tank_y - 58,
                WHITE,
                center=True,
            )
            draw_text(
                screen,
                small_font,
                f"Score: {player['score']}",
                tank_x,
                tank_y + 42,
                GREY_BLUE,
                center=True,
            )
        else:
            draw_tank(screen, tank_x, tank_y, occupied=False, is_me=is_me)
            draw_poe(screen, player_x, player_y, is_me=is_me)
            if player.get("invulnerable"):
                pygame.draw.circle(screen, LIGHT_BLUE, (player_x, player_y - 5), 32, 2)
            draw_text(
                screen,
                small_font,
                player["name"],
                player_x,
                player_y - 52,
                WHITE,
                center=True,
            )
            draw_text(
                screen,
                small_font,
                f"Score: {player['score']}",
                player_x,
                player_y + 34,
                GREY_BLUE,
                center=True,
            )
def draw_bullets(screen, current_state, camera):
    for bullet in current_state["bullets"]:
        x = int(bullet["x"] - camera["x"])
        y = int(bullet["y"] - camera["y"])
        pygame.draw.circle(screen, WHITE, (x, y), 5)
        pygame.draw.circle(screen, LIGHT_BLUE, (x, y), 9, 1)
def draw_map_border(screen, current_state, camera):
    rect = pygame.Rect(
        int(-camera["x"]),
        int(-camera["y"]),
        current_state["map"]["width"],
        current_state["map"]["height"],
    )
    pygame.draw.rect(screen, NEON_BLUE, rect, 3)
def draw_sidebar(screen, current_state, font, small_font, chat_active, chat_text):
    sidebar_x = GAME_WIDTH
    pygame.draw.rect(screen, DARK_BLUE, (sidebar_x, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT))
    pygame.draw.line(screen, NEON_BLUE, (sidebar_x, 0), (sidebar_x, WINDOW_HEIGHT), 2)
    draw_text(screen, font, "Blue Night Arena", sidebar_x + 18, 18, LIGHT_BLUE)
    draw_text(screen, small_font, "WASD / Arrows: move", sidebar_x + 18, 58, GREY_BLUE)
    draw_text(screen, small_font, "Click / Space: shoot", sidebar_x + 18, 78, GREY_BLUE)
    draw_text(screen, small_font, "E: get on/off tank", sidebar_x + 18, 98, GREY_BLUE)
    draw_text(screen, small_font, "T: chat", sidebar_x + 18, 118, GREY_BLUE)
    draw_text(screen, small_font, "F: use terminal", sidebar_x + 18, 138, GREY_BLUE)
    draw_text(screen, font, "Leaderboard", sidebar_x + 18, 154, LIGHT_BLUE)
    players = []
    if current_state:
        players = sorted(
            current_state["players"].values(),
            key=lambda player: player["score"],
            reverse=True,
        )[:8]
    y = 190
    for index, player in enumerate(players, start=1):
        draw_text(
            screen,
            small_font,
            f"{index}. {player['name']} - {player['score']}",
            sidebar_x + 18,
            y,
            WHITE,
        )
        y += 24
    draw_text(screen, font, "Chat", sidebar_x + 18, 380, LIGHT_BLUE)
    y = 416
    for name, message in list(chat_messages[-8:]):
        shown_message = message[:32]
        draw_text(
            screen,
            small_font,
            f"{name}: {shown_message}",
            sidebar_x + 18,
            y,
            WHITE,
        )
        y += 24
    input_y = WINDOW_HEIGHT - 44
    pygame.draw.rect(
        screen,
        BLACK,
        (sidebar_x + 14, input_y, SIDEBAR_WIDTH - 28, 30),
    )
    if chat_active:
        border_color = NEON_BLUE
        prompt = "> " + chat_text
    else:
        border_color = GRID_BLUE
        prompt = "Press T to chat"
    pygame.draw.rect(
        screen,
        border_color,
        (sidebar_x + 14, input_y, SIDEBAR_WIDTH - 28, 30),
        1,
    )
    draw_text(screen, small_font, prompt, sidebar_x + 22, input_y + 7, WHITE)
def world_mouse_position(mouse_pos, camera):
    mouse_x, mouse_y = mouse_pos
    return {
        "x": mouse_x + camera["x"],
        "y": mouse_y + camera["y"],
    }
def character_select_screen(screen, clock, font, small_font, sock):
    global selected_character, running
    selected_character = "poe"
    while running:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    return False
                elif event.key == pygame.K_RETURN:
                    selected_character = "poe"
                    send_json(sock, {
                        "type": "select_character",
                        "character": selected_character,
                    })
                    return True
        draw_character_select_screen(screen, font, small_font)
        pygame.display.flip()
    return False
def draw_map_objects(screen, current_state, camera, small_font):
    objects = current_state.get("objects", {})
    for pad in objects.get("speed_pads", []):
        rect = pygame.Rect(
            int(pad["x"] - camera["x"]),
            int(pad["y"] - camera["y"]),
            pad["w"],
            pad["h"],
        )
        pygame.draw.rect(screen, (5, 55, 90), rect, border_radius=8)
        pygame.draw.rect(screen, LIGHT_BLUE, rect, 2, border_radius=8)
        draw_text(screen, small_font, "BOOST", rect.centerx, rect.centery - 8, WHITE, center=True)
    for teleporter in objects.get("teleporters", []):
        x = int(teleporter["x"] - camera["x"])
        y = int(teleporter["y"] - camera["y"])
        pygame.draw.circle(screen, (10, 20, 80), (x, y), teleporter["r"])
        pygame.draw.circle(screen, NEON_BLUE, (x, y), teleporter["r"], 3)
        pygame.draw.circle(screen, LIGHT_BLUE, (x, y), 12)
        draw_text(screen, small_font, "TP", x, y - 7, WHITE, center=True)
    for wall in objects.get("walls", []):
        rect = pygame.Rect(
            int(wall["x"] - camera["x"]),
            int(wall["y"] - camera["y"]),
            wall["w"],
            wall["h"],
        )
        pygame.draw.rect(screen, (3, 18, 38), rect, border_radius=4)
        pygame.draw.rect(screen, NEON_BLUE, rect, 2, border_radius=4)
    for gate in objects.get("gates", []):
        rect = pygame.Rect(
            int(gate["x"] - camera["x"]),
            int(gate["y"] - camera["y"]),
            gate["w"],
            gate["h"],
        )
        if gate["open"]:
            pygame.draw.rect(screen, (3, 40, 50), rect, 1, border_radius=4)
            draw_text(screen, small_font, "OPEN", rect.centerx, rect.centery - 8, LIGHT_BLUE, center=True)
        else:
            pygame.draw.rect(screen, (10, 45, 90), rect, border_radius=4)
            pygame.draw.rect(screen, WHITE, rect, 2, border_radius=4)
            draw_text(screen, small_font, "GATE", rect.centerx, rect.centery - 8, WHITE, center=True)
    for terminal in objects.get("terminals", []):
        x = int(terminal["x"] - camera["x"])
        y = int(terminal["y"] - camera["y"])
        pygame.draw.rect(screen, (5, 35, 70), (x - 22, y - 22, 44, 44), border_radius=6)
        pygame.draw.rect(screen, LIGHT_BLUE, (x - 22, y - 22, 44, 44), 2, border_radius=6)
        draw_text(screen, small_font, "F", x, y - 8, WHITE, center=True)
def main():
    global running
    selected_character = "poe"
    host = "127.0.0.1"
    starting_username = ""
    print("Connecting to local server at 127.0.0.1:5000...")
    try:
        ws = websocket.create_connection(SERVER_URL, timeout=10)
        print("Connected to online server!")
    except Exception as error:
        print("Could not connect to the online server.")
        print("Error:", error)
        return
    threading.Thread(target=network_reader, args=(ws,), daemon=True).start()
    threading.Thread(target=network_reader, args=(ws,), daemon=True).start()
    pygame.init()
    pygame.display.set_caption("Blue Night Arena")
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 24, bold=True)
    small_font = pygame.font.SysFont("arial", 16)
    if not auth_screen(screen, clock, font, small_font, ws, starting_username):
        try:
            ws.close()
        except OSError:
            pass
    if not character_select_screen(screen, clock, font, small_font, ws):
        try:
            ws.close()
        except OSError:
            pass
        pygame.quit()
        return
    keys = {
        "up": False,
        "down": False,
        "left": False,
        "right": False,
    }
    chat_active = False
    chat_text = ""
    last_input_send = 0
    while running:
        clock.tick(FPS)
        with state_lock:
            current_state = copy.deepcopy(state) if state else None
            current_my_id = my_id
        camera = get_camera(current_state)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if chat_active:
                    if event.key == pygame.K_RETURN:
                        if chat_text.strip():
                            send_json(ws, {
                                "type": "chat",
                                "message": chat_text.strip(),
                            })
                        chat_text = ""
                        chat_active = False
                    elif event.key == pygame.K_ESCAPE:
                        chat_text = ""
                        chat_active = False
                    elif event.key == pygame.K_BACKSPACE:
                        chat_text = chat_text[:-1]
                    elif event.unicode and len(chat_text) < 100:
                        chat_text += event.unicode
                else:
                    if event.key == pygame.K_t:
                        chat_active = True
                    elif event.key == pygame.K_e:
                        send_json(ws, {
                            "type": "toggle_tank",
                        })
                    elif event.key == pygame.K_f:
                        send_json(ws, {
                            "type": "interact",
                        })
                    elif event.key == pygame.K_SPACE:
                        if current_state and current_my_id in current_state["players"]:
                            me = current_state["players"][current_my_id]
                            mouse_world = world_mouse_position(pygame.mouse.get_pos(), camera)
                            send_json(ws, {
                                "type": "shoot",
                                "dx": mouse_world["x"] - me["x"],
                                "dy": mouse_world["y"] - me["y"],
                            })
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and event.pos[0] < GAME_WIDTH:
                    if current_state and current_my_id in current_state["players"]:
                        me = current_state["players"][current_my_id]
                        mouse_world = world_mouse_position(event.pos, camera)
                        send_json(ws, {
                            "type": "shoot",
                            "dx": mouse_world["x"] - me["x"],
                            "dy": mouse_world["y"] - me["y"],
                        })
        pressed = pygame.key.get_pressed()
        if not chat_active:
            keys["up"] = pressed[pygame.K_w] or pressed[pygame.K_UP]
            keys["down"] = pressed[pygame.K_s] or pressed[pygame.K_DOWN]
            keys["left"] = pressed[pygame.K_a] or pressed[pygame.K_LEFT]
            keys["right"] = pressed[pygame.K_d] or pressed[pygame.K_RIGHT]
        else:
            keys["up"] = False
            keys["down"] = False
            keys["left"] = False
            keys["right"] = False
        now = time.time()
        if now - last_input_send > 0.05:
            send_json(ws, {
                "type": "input",
                **keys,
            })
            last_input_send = now
        screen.fill(BLACK)
        draw_grid(screen, camera)
        if current_state:
            draw_map_border(screen, current_state, camera)
            draw_map_objects(screen, current_state, camera, small_font)
            draw_bullets(screen, current_state, camera)
            draw_players(screen, current_state, camera, small_font)
        else:
            draw_text(
                screen,
                font,
                "Loading map...",
                GAME_WIDTH // 2,
                WINDOW_HEIGHT // 2,
                WHITE,
                center=True,
            )
        draw_sidebar(
            screen,
            current_state,
            font,
            small_font,
            chat_active,
            chat_text,
        )
        pygame.display.flip()
    try:
        ws.close()
    except OSError:
        pass
    pygame.quit()
if __name__ == "__main__":
    main()