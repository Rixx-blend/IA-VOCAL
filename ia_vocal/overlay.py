"""Fenêtre overlay : petit panneau sans bordure, toujours au premier plan."""

from __future__ import annotations

import queue
import tkinter as tk

from .commands import dispatch

# Import des actions : leur simple présence enregistre les commandes.
from . import actions  # noqa: F401
from .tray import IconeZone
from .voice import Ecoute


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

        self.ecoute = Ecoute()
        self.commandes: queue.Queue[str] = queue.Queue()
        self._place_top_right()
        self._build()
        self.root.bind("<Escape>", lambda _e: self.masquer())
        self.root.bind("<F2>", lambda _e: self.toggle())
        self.root.bind("<F3>", lambda _e: self.parler())

        # Démarrage discret : la fenêtre est cachée, seule l'icône reste visible
        self._visible = False
        self.root.withdraw()

        self.icone = IconeZone(self.commandes)
        self.icone.demarrer()
        self.root.after(100, self._verifier_ecoute)

    def _place_top_right(self) -> None:
        sw = self.root.winfo_screenwidth()
        x = sw - self.WIDTH - 24
        self.root.geometry(f"{self.WIDTH}x150+{x}+24")

    def _build(self) -> None:
        self.root.configure(bg="#1e1e24")

        header = tk.Label(
            self.root, text="IA VOCAL", fg="#9ecbff", bg="#1e1e24",
            font=("Segoe UI", 10, "bold"), anchor="w",
        )
        header.pack(fill="x", padx=12, pady=(10, 0))

        self.log = tk.Label(
            self.root,
            text="Dis-moi ce que tu veux (ex. « heure », « minuteur 10 minutes »)",
            fg="#d6d6df", bg="#1e1e24", font=("Segoe UI", 10),
            anchor="w", justify="left", wraplength=self.WIDTH - 24,
        )
        self.log.pack(fill="x", padx=12, pady=(6, 6))

        ligne = tk.Frame(self.root, bg="#1e1e24")
        ligne.pack(fill="x", padx=12, pady=(0, 12))

        self.bouton = tk.Button(
            ligne, text="Parler", command=self.parler,
            bg="#3a3a46", fg="#ffffff", activebackground="#4a4a58",
            activeforeground="#ffffff", relief="flat", padx=10,
            font=("Segoe UI", 10),
        )
        self.bouton.pack(side="right", padx=(8, 0), ipady=4)

        self.entry = tk.Entry(
            ligne, bg="#2a2a33", fg="#ffffff", insertbackground="#ffffff",
            relief="flat", font=("Segoe UI", 11),
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", self._on_submit)
        self.entry.focus_set()

    def _on_submit(self, _event: tk.Event) -> None:
        text = self.entry.get()
        self.entry.delete(0, tk.END)
        if not text.strip():
            return
        self.log.config(text=dispatch(text))

    def parler(self) -> None:
        """Lance une écoute du micro (bouton Parler ou F3)."""
        if self.ecoute.demarrer():
            self.log.config(text="Je t'écoute…")
            self.bouton.config(state="disabled")

    def _verifier_ecoute(self) -> None:
        """Lit les résultats de la voix et les commandes de l'icône, sans bloquer."""
        try:
            while True:
                commande = self.commandes.get_nowait()
                if commande == "quitter":
                    self.quitter()
                    return
                if commande == "basculer":
                    self.toggle()
        except queue.Empty:
            pass

        try:
            while True:
                genre, texte = self.ecoute.resultats.get_nowait()
                self.bouton.config(state="normal")
                if genre == "phrase":
                    # On écrit ce qui a été compris, puis on exécute la commande
                    self.entry.delete(0, tk.END)
                    self.entry.insert(0, texte)
                    self.log.config(text=dispatch(texte))
                    self.entry.delete(0, tk.END)
                else:
                    self.log.config(text=texte)
        except queue.Empty:
            pass
        self.root.after(100, self._verifier_ecoute)

    def afficher(self) -> None:
        if not self._visible:
            self.root.deiconify()
            self.entry.focus_set()
            self._visible = True

    def masquer(self) -> None:
        if self._visible:
            self.root.withdraw()
            self._visible = False

    def toggle(self) -> None:
        if self._visible:
            self.masquer()
        else:
            self.afficher()

    def quitter(self) -> None:
        self.icone.arreter()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
