"""Fenêtre de l'application : overlay arrondi avec orbe animé."""

from __future__ import annotations

import ctypes
import json
import threading
import time
from pathlib import Path

import webview

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
    def __init__(self) -> None:
        self.fenetre = None
        self.ecoute = Ecoute()
        self._glisse_en_cours = False

    def envoyer(self, texte: str) -> bool:
        threading.Thread(target=self._traiter, args=(texte,), daemon=True).start()
        return True

    def ecouter(self) -> bool:
        if not self.ecoute.demarrer():
            return False
        self._etat("ecoute")
        threading.Thread(target=self._attendre_voix, daemon=True).start()
        return True

    def debut_glisser(self) -> None:
        if self._glisse_en_cours:
            return
        self._glisse_en_cours = True
        threading.Thread(target=self._suivre_souris, daemon=True).start()

    def _suivre_souris(self) -> None:
        user32 = ctypes.windll.user32
        VK_LBUTTON = 0x01

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        curseur = POINT()
        user32.GetCursorPos(ctypes.byref(curseur))
        depart_souris = (curseur.x, curseur.y)
        depart_fenetre = (self.fenetre.x, self.fenetre.y)
        try:
            while user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000:
                user32.GetCursorPos(ctypes.byref(curseur))
                self.fenetre.move(
                    depart_fenetre[0] + curseur.x - depart_souris[0],
                    depart_fenetre[1] + curseur.y - depart_souris[1],
                )
                time.sleep(0.01)
        finally:
            self._glisse_en_cours = False

    def minimiser(self) -> None:
        if self.fenetre:
            self.fenetre.minimize()

    def quitter(self) -> None:
        if self.fenetre:
            self.fenetre.destroy()

    def _traiter(self, texte: str) -> None:
        self._etat("reflechit")
        try:
            resultat = executer(texte)
            if resultat is None:
                resultat = repondre(texte)
                if resultat.startswith("__COMMANDE__:"):
                    commande_locale = resultat.split(":", 1)[1].strip()
                    resultat = executer(commande_locale)
                    if resultat is None:
                        self._etat("agit")
                        self._message("Je réalise cette action sur ton ordinateur…")
                        resultat = executer_tache(commande_locale, self._message)
        except ai.AssistantLocalIndisponible as exc:
            resultat = str(exc)
        except Exception as exc:
            resultat = f"Erreur : {exc}"
        self._repondre(resultat or "C'est fait.")

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
            pass


def _parler(texte: str) -> None:
    try:
        import pyttsx3
        moteur = pyttsx3.init()
        moteur.say(texte)
        moteur.runAndWait()
    except Exception:
        time.sleep(min(4.0, len(texte) / 20))


def _position() -> tuple[int, int]:
    try:
        ecran = webview.screens[0]
        largeur_ecran, hauteur_ecran = ecran.width, ecran.height
    except Exception:
        largeur_ecran, hauteur_ecran = 1920, 1080
    return (largeur_ecran - LARGEUR) // 2, hauteur_ecran - HAUTEUR - 48


def _afficher_dans_barre_des_taches() -> None:
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
    user32.ShowWindow(hwnd, 0)
    user32.ShowWindow(hwnd, 5)


def _coordonnees_coherentes() -> None:
    if hasattr(ctypes, "windll"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def lancer() -> None:
    _coordonnees_coherentes()
    api = Api()
    x, y = _position()
    fenetre = webview.create_window(
        TITRE, html=PAGE.read_text(encoding="utf-8"), js_api=api,
        width=LARGEUR, height=HAUTEUR, x=x, y=y,
        frameless=True, transparent=True, shadow=False, on_top=False,
    )
    api.fenetre = fenetre
    preparation.definir_sortie(api._message)
    preparation.lancer_en_arriere_plan()

    def apres_demarrage() -> None:
        time.sleep(0.8)
        _afficher_dans_barre_des_taches()

    webview.start(apres_demarrage)
