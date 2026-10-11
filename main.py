"""Hum-to-Band: hum 4 bars, get a full band.   Run:  python main.py"""
import os

from kivy.app import App
from kivy.core.window import Window
from kivy.lang import Builder

from ui.screens import MainScreen

HERE = os.path.dirname(os.path.abspath(__file__))


class HumToBandApp(App):
    title = "Hum-to-Band"

    def build(self):
        Window.size = (1100, 780)
        Builder.load_file(os.path.join(HERE, "ui", "hum.kv"))
        self.screen = MainScreen()
        return self.screen

    def on_stop(self):
        if getattr(self.screen, "controller", None):
            self.screen.controller.shutdown()


if __name__ == "__main__":
    HumToBandApp().run()
