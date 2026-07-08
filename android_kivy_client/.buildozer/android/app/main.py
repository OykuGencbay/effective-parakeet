from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, Ellipse, Line
from kivy.clock import Clock
from kivy.core.window import Window
import json
import threading
import time
import websocket
from kivy.logger import Logger
SERVER_URL = "wss://effective-parakeet-dgzj.onrender.com/ws"
class ArenaWidget(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player_x = 400
        self.player_y = 240
        self.speed = 260
        self.move_left = False
        self.move_right = False
        self.move_up = False
        self.move_down = False
        self.in_tank = False
        self.bullets = []
        self.active_touches = {}
        Clock.schedule_interval(self.update, 1 / 60)
    def get_buttons(self):
        size = 70
        gap = 10
        base_x = 45
        base_y = 55
        return {
            "A": (base_x, base_y + size + gap, size, size),
            "D": (base_x + (size + gap) * 2, base_y + size + gap, size, size),
            "W": (base_x + size + gap, base_y + (size + gap) * 2, size, size),
            "S": (base_x + size + gap, base_y, size, size),

            "SHOOT": (self.width - 170, 55, 120, 80),
            "MOUNT": (self.width - 170, 155, 120, 80),
        }
    def point_inside_rect(self, x, y, rect):
        rx, ry, rw, rh = rect
        return rx <= x <= rx + rw and ry <= y <= ry + rh
    def press_button(self, button_name):
        if button_name == "W":
            self.move_up = True
        elif button_name == "A":
            self.move_left = True
        elif button_name == "S":
            self.move_down = True
        elif button_name == "D":
            self.move_right = True
        elif button_name == "SHOOT":
            self.shoot()
        elif button_name == "MOUNT":
            self.in_tank = not self.in_tank
    def release_button(self, button_name):
        if button_name == "W":
            self.move_up = False
        elif button_name == "A":
            self.move_left = False
        elif button_name == "S":
            self.move_down = False
        elif button_name == "D":
            self.move_right = False
    def on_touch_down(self, touch):
        x, y = touch.pos
        buttons = self.get_buttons()
        for name, rect in buttons.items():
            if self.point_inside_rect(x, y, rect):
                self.active_touches[touch.uid] = name
                self.press_button(name)
                return True
        return False
    def on_touch_up(self, touch):
        button_name = self.active_touches.get(touch.uid)
        if button_name:
            self.release_button(button_name)
            del self.active_touches[touch.uid]
            return True
        return False
    def shoot(self):
        bullet = {
            "x": self.player_x,
            "y": self.player_y,
            "vx": 500,
            "vy": 0,
        }
        self.bullets.append(bullet)
    def update(self, dt):
        if self.move_left:
            self.player_x -= self.speed * dt
        if self.move_right:
            self.player_x += self.speed * dt
        if self.move_up:
            self.player_y += self.speed * dt
        if self.move_down:
            self.player_y -= self.speed * dt
        self.player_x = max(40, min(self.width - 40, self.player_x))
        self.player_y = max(50, min(self.height - 50, self.player_y))
        for bullet in self.bullets:
            bullet["x"] += bullet["vx"] * dt
            bullet["y"] += bullet["vy"] * dt
        self.bullets = [
            bullet for bullet in self.bullets
            if -50 < bullet["x"] < self.width + 50
            and -50 < bullet["y"] < self.height + 50
        ]
        self.draw()
    def draw_poe(self, x, y):
        with self.canvas:
            if self.in_tank:
                Color(0.10, 0.25, 0.18, 1)
                Rectangle(pos=(x - 35, y - 25), size=(70, 45))
                Color(0.15, 0.38, 0.24, 1)
                Rectangle(pos=(x - 18, y - 5), size=(36, 28))
                Color(0.25, 0.55, 0.35, 1)
                Rectangle(pos=(x + 15, y + 4), size=(42, 8))
            else:
                Color(0.18, 0.35, 0.18, 1)
                Rectangle(pos=(x - 13, y - 28), size=(26, 40))
                Color(0.95, 0.78, 0.62, 1)
                Ellipse(pos=(x - 13, y + 8), size=(26, 26))
                Color(0.20, 0.10, 0.04, 1)
                Rectangle(pos=(x - 13, y + 25), size=(26, 8))
                Color(0.10, 0.22, 0.10, 1)
                Rectangle(pos=(x - 12, y - 48), size=(9, 20))
                Rectangle(pos=(x + 3, y - 48), size=(9, 20))
    def draw_button(self, name, rect):
        x, y, w, h = rect
        is_pressed = name in self.active_touches.values()
        with self.canvas:
            if is_pressed:
                Color(0.20, 0.65, 0.95, 0.75)
            else:
                Color(0.08, 0.25, 0.40, 0.55)
            Rectangle(pos=(x, y), size=(w, h))
            Color(0.3, 0.8, 1, 1)
            Line(rectangle=(x, y, w, h), width=2)
    def draw_controls(self):
        buttons = self.get_buttons()
        for name, rect in buttons.items():
            self.draw_button(name, rect)
    def draw_bullets(self):
        with self.canvas:
            Color(0.4, 0.9, 1, 1)
            for bullet in self.bullets:
                Ellipse(pos=(bullet["x"] - 5, bullet["y"] - 5), size=(10, 10))
    def draw(self):
        self.canvas.clear()
        with self.canvas:
            Color(0.01, 0.03, 0.09, 1)
            Rectangle(pos=self.pos, size=self.size)
            Color(0.05, 0.18, 0.30, 1)
            grid = 60
            for x in range(0, int(self.width), grid):
                Line(points=[x, 0, x, self.height], width=1)
            for y in range(0, int(self.height), grid):
                Line(points=[0, y, self.width, y], width=1)
            Color(0.2, 0.7, 1, 1)
            Line(rectangle=(20, 20, self.width - 40, self.height - 40), width=2)
        self.draw_bullets()
        self.draw_poe(self.player_x, self.player_y)
        self.draw_controls()
class BlueNightRoot(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ws = None
        self.start_network_thread()
        self.arena = ArenaWidget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.add_widget(self.arena)
        self.messages = [
            "System: Welcome to Blue Night Arena Mobile.",
            "System: Chat is local-only for now.",
        ]
        self.chat_log = Label(
            text="\n".join(self.messages),
            size_hint=(0.42, 0.28),
            pos_hint={"x": 0.02, "top": 0.97},
            color=(0.65, 0.9, 1, 1),
            font_size="13sp",
            halign="left",
            valign="top",
        )
        self.chat_log.bind(size=self.update_chat_text_size)
        with self.chat_log.canvas.before:
            Color(0.0, 0.02, 0.05, 0.65)
            self.chat_bg = Rectangle(pos=self.chat_log.pos, size=self.chat_log.size)
        self.chat_log.bind(pos=self.update_chat_bg, size=self.update_chat_bg)
        self.add_widget(self.chat_log)
        self.chat_bar = BoxLayout(
            orientation="horizontal",
            spacing=6,
            size_hint=(0.55, 0.10),
            pos_hint={"center_x": 0.5, "y": 0.02},
        )
        self.chat_input = TextInput(
            hint_text="Type chat...",
            multiline=False,
            font_size="15sp",
            background_color=(0.02, 0.07, 0.12, 0.95),
            foreground_color=(0.75, 0.95, 1, 1),
            cursor_color=(0.4, 0.9, 1, 1),
            hint_text_color=(0.4, 0.6, 0.7, 1),
        )
        self.chat_input.bind(on_text_validate=self.send_chat)
        self.send_button = Button(
            text="SEND",
            font_size="14sp",
            background_color=(0.05, 0.25, 0.40, 1),
            color=(0.75, 0.95, 1, 1),
            size_hint=(0.28, 1),
        )
        self.send_button.bind(on_press=self.send_chat)
        self.chat_bar.add_widget(self.chat_input)
        self.chat_bar.add_widget(self.send_button)
        self.add_widget(self.chat_bar)
        self.connection_status = Label(
            text="Offline",
            size_hint=(0.22, 0.06),
            pos_hint={"right": 0.98, "top": 0.98},
            color=(1, 0.55, 0.55, 1),
            font_size="14sp",
        )
        self.add_widget(self.connection_status)
        self.ws = None
        self.start_network_thread()
        def add_chat_message(self, message):
            def update_ui(dt):
                self.messages.append(message)
                self.messages = self.messages[-8:]
                self.chat_log.text = "\n".join(self.messages)
            Clock.schedule_once(update_ui, 0)
    def update_chat_text_size(self, instance, value):
        instance.text_size = (instance.width - 10, None)
    def update_chat_bg(self, instance, value):
        self.chat_bg.pos = instance.pos
        self.chat_bg.size = instance.size
    def send_chat(self, *args):
        message = self.chat_input.text.strip()
        if not message:
            return
        self.add_chat_message("You: " + message)
        try:
            if self.ws:
                self.ws.send(json.dumps({
                    "type": "chat",
                    "message": message,
                }))
            else:
                self.add_chat_message("System: not connected yet.")
        except Exception as error:
            Logger.error("BlueNight: Send chat error: " + str(error))
            self.add_chat_message("System: failed to send chat.")
        self.chat_input.text = ""
    def set_status(self, text, color):
        def update_ui(dt):
            self.connection_status.text = text
            self.connection_status.color = color
        Clock.schedule_once(update_ui, 0)
    def start_network_thread(self):
        Logger.info("BlueNight: start_network_thread was called")
        self.set_status("Starting net...", (1, 0.85, 0.3, 1))
        if not hasattr(self, "network_loop"):
            Logger.error("BlueNight: network_loop is missing from BlueNightRoot")
            self.set_status("Offline", (1, 0.4, 0.4, 1))
            self.add_chat_message("System: network_loop missing. App opened offline.")
            return
        thread = threading.Thread(target=self.network_loop, daemon=True)
        thread.start()
def network_loop(self):
    retry_delay = 3
    while True:
        try:
            Logger.info("BlueNight: network_loop trying connection")
            Logger.info("BlueNight: SERVER_URL is " + SERVER_URL)
            self.set_status("Waking server...", (1, 0.85, 0.3, 1))
            self.add_chat_message("System: trying to connect...")
            self.ws = websocket.create_connection(SERVER_URL, timeout=20)
            Logger.info("BlueNight: CONNECTED TO SERVER")
            self.set_status("Online", (0.4, 1, 0.6, 1))
            self.add_chat_message("System: connected to arena.")
            retry_delay = 3
            while True:
                message = self.ws.recv()
                Logger.info("BlueNight: SERVER MESSAGE " + str(message))
                try:
                    data = json.loads(message)
                except Exception:
                    continue
                if data.get("type") == "chat":
                    sender = data.get("name", "Player")
                    chat_message = data.get("message", "")
                    self.add_chat_message(sender + ": " + chat_message)
                elif data.get("type") == "system":
                    self.add_chat_message("System: " + data.get("message", ""))
                elif data.get("type") == "init":
                    self.add_chat_message("System: joined arena.")
        except Exception as error:
            Logger.error("BlueNight: Network error: " + str(error))
            self.ws = None
            self.set_status("Reconnecting...", (1, 0.55, 0.3, 1))
            self.add_chat_message("System: server asleep/offline. Retrying...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay + 3, 30)
class BlueNightArenaApp(App):
    def build(self):
        Window.clearcolor = (0.01, 0.03, 0.09, 1)
        return BlueNightRoot()
if __name__ == "__main__":
    BlueNightArenaApp().run()