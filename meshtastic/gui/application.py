import tkinter as tk
from tkinter import ttk


class MeshtasticApplication(tk.Frame):
    """Meshtastic main application window."""

    def __init__(self):
        super().__init__(None)
        self.master.title("Meshtastic")
        self.pack(expand=1)

        self.hello = ttk.Label(self, text="Hello, Meshtastic :)")
        self.hello.pack(fill="both", padx=10, pady=10)

    def connect_serial(self):
        "Helper method to connect to "


