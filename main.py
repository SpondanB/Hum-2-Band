"""Hum-to-Band: hum 4 bars, get a full band.   Run:  python main.py"""
import os

# Window limits must be set before the window exists. The minimum keeps the layout usable;
# below it the settings panel scrolls instead of the controls overlapping.
from kivy.config import Config

Config.set("graphics", "resizable", "1")
Config.set("graphics", "minimum_width", "400")
Config.set("graphics", "minimum_height", "480")

from kivy.app import App
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import NumericProperty

from ui.screens import MainScreen

HERE = os.path.dirname(os.path.abspath(__file__))


class HumToBandApp(App):
    title = "Hum2Band"
    s = NumericProperty(1.0)     # UI scale: every dp()/sp() size in hum.kv is multiplied by it

    def build(self):
        Window.size = (1000, 680)    # fits a 1366x768 laptop with its title bar and taskbar
        Builder.load_file(os.path.join(HERE, "ui", "hum.kv"))
        self.screen = MainScreen()
        return self.screen

    def on_stop(self):
        if getattr(self, "screen", None):
            self.screen.shutdown()


if __name__ == "__main__":
    HumToBandApp().run()
