"""Fenêtre de l'application : overlay arrondi avec orbe animé, dans la barre des tâches.

L'interface est une page HTML (ui/index.html). Python expose l'objet Api à la page ;
Python met la page à jour avec evaluate_js.
"""

from __future__ import annotations

import ctypes
import json
import threading
import time
from pathlib import Path

import webview

# Enregistre les commandes (l'ordre compte : pc et souris avant « ouvre … »)
from . import actions  # noqa: F401
from . import agent, ai, preparation  # noqa: F401
from .agent import executer_tache
from .ai import repondre
from .chaine import executer
from .voice import Ecoute

TITRE = "IA VOCAL"
LARGEUR, HAUTEUR = 680, 250
PAGE = Path(__file__).parent / "ui" / "index.html"


class Api:
    """Méthodes appelées depuis la page (pywebview.api.<nom>)."""

    def __init__(self) -> None:
        self.fenetre = None
        self.ecoute = Ecoute()

    # ----- appelées par la page -----

    def envoyer(self, texte: str) -> bool:
        threading.Thread(target=self._traiter, args=(texte,), daemon=True).start()
        return True

    def ecouter(self) -> bool:
        if not self.ecoute.demarrer():
            return False
        self._etat("ecoute")
        threading.Thread(target=self._attendre_voix, daemon=True).start()
        return True

    def minimiser(self) -> None:
        if self.fenetre:
            self.fenetre.minimize()

    def quitter(self) -> None:
        if self.fenetre:
            self.fenetre.destroy()

    # ----- traitement -----

    def _traiter(self, texte: str) -> None:
        self._etat("reflechit")
        resultat = executer(texte)
        if resultat is None:
            if ai.disponible():
                resultat = repondre(texte)
            else:
                self._etat("agit")
                resultat = executer_tache(texte, self._message)
        self._repondre(resultat)

    def _attendre_voix(self) -> None:
        genre, texte = self.ecoute.resultats.get()
        if genre == "phrase":
            self._appeler("setTexte", texte)
            self.envoyer(texte)
        else:
            self._repondre(texte)

    def _repondre(self, texte: str) -> None:
        self._message(texte)
        self._etat("parle")
        _parler(texte)
        self._etat("repos")

    # ----- mise à jour de la page -----

    def _etat(self, etat: str) -> None:
        self._appeler("setEtat", etat)

    def _message(self, texte: str) -> None:
        self._appeler("setMessage", texte)

    def _appeler(self, fonction: str, *arguments: str) -> None:
        if self.fenetre is None:
            return
        args = ",".join(json.dumps(a, ensure_ascii=False) for a in arguments)
        try:
            self.fenetre.evaluate_js(f"{fonction}({args})")
        except Exception:
            pass  # la page n'est pas encore prête ou a été fermée


def _parler(texte: str) -> None:
    """Lit la réponse à voix haute si pyttsx3 est installé, sinon attend un peu."""
    try:
        import pyttsx3
    except ImportError:
        time.sleep(min(4.0, len(texte) / 20))
        return
    moteur = pyttsx3.init()
    moteur.say(texte)
    moteur.runAndWait()


def _position() -> tuple[int, int]:
    """Centré en bas de l'écran principal."""
    try:
        ecran = webview.screens[0]
        largeur_ecran, hauteur_ecran = ecran.width, ecran.height
    except Exception:
        largeur_ecran, hauteur_ecran = 1920, 1080
    return (largeur_ecran - LARGEUR) // 2, hauteur_ecran - HAUTEUR - 48


def _afficher_dans_barre_des_taches() -> None:
    """Une fenêtre sans bordure n'apparaît pas dans la barre des tâches : on force le style."""
    if not hasattr(ctypes, "windll"):
        return
    user32 = ctypes.windll.user32
    GWL_EXSTYLE = -20
    WS_EX_APPWINDOW = 0x00040000
    WS_EX_TOOLWINDOW = 0x00000080
    hwnd = user32.FindWindowW(None, TITRE)
    if not hwnd:
        return
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)
    user32.ShowWindow(hwnd, 0)  # masque
    user32.ShowWindow(hwnd, 5)  # réaffiche : la barre des tâches se met à jour


def lancer() -> None:
    api = Api()
    x, y = _position()
    fenetre = webview.create_window(
        TITRE,
        html=PAGE.read_text(encoding="utf-8"),
        js_api=api,
        width=LARGEUR,
        height=HAUTEUR,
        x=x,
        y=y,
        frameless=True,
        transparent=True,
        on_top=False,
        background_color="#000000",
    )
    api.fenetre = fenetre

    preparation.definir_sortie(api._message)
    if not ai.disponible():
        preparation.lancer_en_arriere_plan()

    def apres_demarrage() -> None:
        time.sleep(0.8)  # le temps que la fenêtre existe
        _afficher_dans_barre_des_taches()

    webview.start(apres_demarrage)
