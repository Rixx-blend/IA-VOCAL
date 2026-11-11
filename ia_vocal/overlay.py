"""Fenêtre overlay : petit panneau sans bordure, toujours au premier plan."""

from __future__ import annotations

import tkinter as tk

from .commands import dispatch

# Import des actions : leur simple présence enregistre les commandes.
from . import actions  # noqa: F401


class Overlay:
    WIDTH = 460

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("IA VOCAL")
        self.root.overrideredirect(True)          # pas de barre de titre
        self.root.attributes("-topmost", True)    # toujours au premier plan
        try:
            self.root.attributes("-alpha", 0.92)  # légère transparence
        except tk.TclError:
            pass

        self._place_top_right()
        self._build()
        self.root.bind("<Escape>", lambda _e: self.root.destroy())
        self.root.bind("<F2>", lambda _e: self.toggle())
        self._visible = True

    def _place_top_right(self) -> None:
        sw = self.root.winfo_screenwidth()
        x = sw - self.WIDTH - 24
        self.root.geometry(f"{self.WIDTH}x120+{x}+24")

    def _build(self) -> None:
        self.root.configure(bg="#1e1e24")

        header = tk.Label(
            self.root, text="IA VOCAL", fg="#9ecbff", bg="#1e1e24",
            font=("Segoe UI", 10, "bold"), anchor="w",
        )
        header.pack(fill="x", padx=12, pady=(10, 0))

        self.log = tk.Label(
            self.root, text="Dis-moi ce que tu veux (ex. « heure », « minuteur 10 minutes »)",
            fg="#d6d6df", bg="#1e1e24", font=("Segoe UI", 10),
            anchor="w", justify="left", wraplength=self.WIDTH - 24,
        )
        self.log.pack(fill="x", padx=12, pady=(6, 6))

        self.entry = tk.Entry(
            self.root, bg="#2a2a33", fg="#ffffff", insertbackground="#ffffff",
            relief="flat", font=("Segoe UI", 11),
        )
        self.entry.pack(fill="x", padx=12, pady=(0, 12), ipady=6)
        self.entry.bind("<Return>", self._on_submit)
        self.entry.focus_set()

    def _on_submit(self, _event: tk.Event) -> None:
        text = self.entry.get()
        self.entry.delete(0, tk.END)
        if not text.strip():
            return
        self.log.config(text=dispatch(text))

    def toggle(self) -> None:
        if self._visible:
            self.root.withdraw()
        else:
            self.root.deiconify()
            self.entry.focus_set()
        self._visible = not self._visible

    def run(self) -> None:
        self.root.mainloop()
