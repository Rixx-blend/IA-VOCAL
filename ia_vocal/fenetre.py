"""Fenêtre de l'application : overlay arrondi avec orbe animé."""

from __future__ import annotations

import base64
import ctypes
import io
import json
import os
import threading
import time
from pathlib import Path

# Configure la transparence WebView2 avant la création du runtime.
os.environ["WEBVIEW2_DEFAULT_BACKGROUND_COLOR"] = "00000000"

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
        self._traitement = threading.Lock()
        self._interface_prete = False
        self._messages_en_attente: list[tuple[str, str]] = []

    def interface_prete(self) -> None:
        """Signale que le pont JavaScript est disponible et vide les messages différés."""
        self._interface_prete = True
        en_attente, self._messages_en_attente = self._messages_en_attente, []
        for fonction, texte in en_attente:
            self._appeler(fonction, texte)

    def capturer_fond(self) -> str | None:
        """Capture la zone du bureau derrière l'overlay pour la réfraction WebGL."""
        if not hasattr(ctypes, "windll") or self.fenetre is None:
            return None
        try:
            from PIL import ImageGrab
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, TITRE)
            if not hwnd:
                return None

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            rect = RECT()
            if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
                return None
            origin = POINT(0, 0)
            if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
                return None
            width, height = rect.right - rect.left, rect.bottom - rect.top
            if width <= 0 or height <= 0:
                return None
            try:
                dpi = user32.GetDpiForWindow(hwnd) or 96
            except Exception:
                dpi = 96
            marge = round(16 * dpi / 96)  # marge transparente CSS autour de la vitre
            # WDA_EXCLUDEFROMCAPTURE retire cette fenêtre de la capture.
            # L'affinité est restaurée immédiatement après chaque image.
            WDA_NONE = 0x00000000
            WDA_EXCLUDEFROMCAPTURE = 0x00000011
            affinite_active = bool(
                user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            )
            if not affinite_active:
                return None
            try:
                shot = ImageGrab.grab(
                    bbox=(
                        origin.x + marge, origin.y + marge,
                        origin.x + width - marge, origin.y + height - marge,
                    ),
                    all_screens=True,
                )
            finally:
                user32.SetWindowDisplayAffinity(hwnd, WDA_NONE)

            # Aligne la texture sur les dimensions CSS attendues par le shader.
            echelle = max(1.0, dpi / 96.0)
            taille = (
                max(1, round((width - 2 * marge) / echelle)),
                max(1, round((height - 2 * marge) / echelle)),
            )
            if shot.size != taille:
                shot = shot.resize(taille, Image.Resampling.BILINEAR)
            buffer = io.BytesIO()
            shot.convert("RGB").save(buffer, format="JPEG", quality=78, optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            return "data:image/jpeg;base64," + encoded
        except Exception:
            return None

    def envoyer(self, texte: str) -> bool:
        phrase = (texte or "").strip()
        if not phrase:
            return False
        threading.Thread(target=self._traiter, args=(phrase,), daemon=True).start()
        return True

    def ecouter(self) -> bool:
        if self.ecoute.active:
            self.ecoute.arreter()
            self._etat("repos")
            self._message("Écoute désactivée.")
            return False
        if not self.ecoute.demarrer():
            self._message("Impossible de démarrer le micro.")
            return False
        self._etat("ecoute")
        self._message("Je t'écoute. Tu peux parler, je reste en écoute jusqu'à désactivation.")
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
        self.ecoute.arreter()
        if self.fenetre:
            self.fenetre.destroy()

    def _traiter(self, texte: str) -> None:
        with self._traitement:
            self._etat("reflechit")
            try:
                resultat = executer(texte)
                if resultat is None:
                    resultat = repondre(texte)
                    if resultat.startswith("__COMMANDE__:"):
                        commande_locale = resultat.split(":", 1)[1].strip()
                        resultat = executer(commande_locale)
                        if resultat is None or resultat.startswith("Je ne trouve pas «"):
                            self._etat("agit")
                            self._message("Je réalise cette action sur ton ordinateur…")
                            resultat = executer_tache(commande_locale, self._message)
                elif resultat.startswith("Je ne trouve pas «"):
                    self._etat("agit")
                    self._message("Je cherche cette application avec l'agent local…")
                    resultat = executer_tache(texte, self._message)
            except ai.AssistantLocalIndisponible as exc:
                resultat = str(exc)
            except Exception as exc:
                resultat = f"Erreur : {exc}"
            self._repondre(resultat or "C'est fait.")

    def _attendre_voix(self) -> None:
        while self.ecoute.active:
            try:
                genre, texte = self.ecoute.resultats.get(timeout=0.35)
            except Exception:
                continue
            if genre == "phrase":
                self._appeler("setTexte", texte)
                self.envoyer(texte)
            else:
                self._message(texte)
                self._etat("repos")
                return

    def _repondre(self, texte: str) -> None:
        self._message(texte)
        self._etat("parle")
        self.ecoute.suspendre_sortie_vocale(True)
        try:
            _parler(texte)
        finally:
            self.ecoute.suspendre_sortie_vocale(False)
        self._etat("ecoute" if self.ecoute.active else "repos")

    def _etat(self, etat: str) -> None:
        self._appeler("setEtat", etat)

    def _message(self, texte: str) -> None:
        self._appeler("setMessage", texte)

    def _appeler(self, fonction: str, *arguments: str) -> None:
        if self.fenetre is None:
            return
        if not self._interface_prete:
            if arguments:
                self._messages_en_attente.append((fonction, arguments[0]))
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
        moteur.stop()
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
    GWL_STYLE = -16
    GWL_EXSTYLE = -20
    WS_BORDER = 0x00800000
    WS_DLGFRAME = 0x00400000
    WS_THICKFRAME = 0x00040000
    WS_CAPTION = 0x00C00000
    WS_EX_APPWINDOW = 0x00040000
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_LAYERED = 0x00080000
    LWA_COLORKEY = 0x00000001
    COULEUR_CLE_MAGENTA = 0x00FF00FF
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_FRAMECHANGED = 0x0020

    hwnd = user32.FindWindowW(None, TITRE)
    if not hwnd:
        return

    # Supprime aussi le cadre natif Windows, qui peut rester visible
    # même lorsque la fenêtre WebView est frameless et transparente.
    style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    style &= ~(WS_BORDER | WS_DLGFRAME | WS_THICKFRAME | WS_CAPTION)
    user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)

    exstyle = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    # Le fond magenta du host devient transparent au niveau du compositeur Windows.
    exstyle = (exstyle & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW | WS_EX_LAYERED
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, exstyle)
    user32.SetLayeredWindowAttributes(hwnd, COULEUR_CLE_MAGENTA, 255, LWA_COLORKEY)

    # Windows 11 : demande à DWM de ne dessiner aucune bordure.
    try:
        dwmapi = ctypes.windll.dwmapi
        couleur_sans_bordure = ctypes.c_int(0xFFFFFFFE)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 34, ctypes.byref(couleur_sans_bordure),
            ctypes.sizeof(couleur_sans_bordure),
        )
    except Exception:
        pass

    user32.SetWindowPos(
        hwnd, 0, 0, 0, 0, 0,
        SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED,
    )


class _AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_uint), ("AccentFlags", ctypes.c_uint),
        ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_uint),
    ]


class _CompAttrData(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p), ("SizeOfData", ctypes.c_size_t)]


class _Rect(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def _effet_verre() -> None:
    """Active le matériau Acrylic Windows et découpe la fenêtre en coins arrondis."""
    if not hasattr(ctypes, "windll"):
        return
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, TITRE)
    if not hwnd:
        return

    # L'overlay reste inclus dans les captures et le partage d'écran.
    try:
        user32.SetWindowDisplayAffinity(hwnd, 0)  # WDA_NONE
    except Exception:
        pass

    # Acrylic natif : flou réel du bureau derrière la fenêtre (Windows 10/11).
    # La teinte est volontairement sombre pour conserver le contraste du texte.
    try:
        ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
        ACCENT_FLAGS = 2
        ACRYLIC_TINT_ABGR = 0xCC281E19  # alpha CC, RGB approx. 25/30/40
        politique = _AccentPolicy(
            ACCENT_ENABLE_ACRYLICBLURBEHIND,
            ACCENT_FLAGS,
            ACRYLIC_TINT_ABGR,
            0,
        )
        donnees = _CompAttrData(
            19,
            ctypes.cast(ctypes.pointer(politique), ctypes.c_void_p),
            ctypes.sizeof(politique),
        )
        user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(donnees))
    except Exception:
        # Le dégradé CSS opaque sert de repli si Acrylic est indisponible.
        pass

    # Découpe native de toute la fenêtre : aucun panneau Acrylic rectangulaire
    # ne doit dépasser des coins arrondis du composant HTML.
    try:
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long),
            ]

        rect = RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            largeur = max(1, rect.right - rect.left)
            hauteur = max(1, rect.bottom - rect.top)
            try:
                dpi = user32.GetDpiForWindow(hwnd) or 96
            except Exception:
                dpi = 96
            rayon = max(1, round(38 * dpi / 96))
            gdi32 = ctypes.windll.gdi32
            gdi32.CreateRoundRectRgn.argtypes = [
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int,
            ]
            gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
            user32.SetWindowRgn.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool,
            ]
            user32.SetWindowRgn.restype = ctypes.c_int
            region = gdi32.CreateRoundRectRgn(
                0, 0, largeur + 1, hauteur + 1, rayon * 2, rayon * 2
            )
            if region:
                if not user32.SetWindowRgn(ctypes.c_void_p(hwnd), region, True):
                    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
                    gdi32.DeleteObject(region)
    except Exception:
        pass

    # Conserve l'absence de cadre natif Windows.
    try:
        dwmapi = ctypes.windll.dwmapi
        couleur_sans_bordure = ctypes.c_int(0xFFFFFFFE)  # DWMWA_COLOR_NONE
        dwmapi.DwmSetWindowAttribute(
            hwnd, 34, ctypes.byref(couleur_sans_bordure),
            ctypes.sizeof(couleur_sans_bordure),
        )
        corner_round = ctypes.c_int(2)  # DWMWCP_ROUND
        dwmapi.DwmSetWindowAttribute(
            hwnd, 33, ctypes.byref(corner_round), ctypes.sizeof(corner_round),
        )
    except Exception:
        pass

    try:
        SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER = 0x0001, 0x0002, 0x0004
        SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x0010, 0x0020
        user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER |
            SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
    except Exception:
        pass


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
        frameless=True, transparent=True, background_color="#FF00FF",
        shadow=False, on_top=False,
    )
    api.fenetre = fenetre
    preparation.definir_sortie(api._message)
    preparation.lancer_en_arriere_plan()

    def apres_demarrage() -> None:
        time.sleep(0.8)
        _afficher_dans_barre_des_taches()
        _effet_verre()

    # Pywebview peut restaurer la fenêtre après une minimisation en réappliquant
    # son cadre natif. On retire donc le cadre à chaque restauration.
    def apres_restauration() -> None:
        time.sleep(0.18)
        _afficher_dans_barre_des_taches()
        _effet_verre()
        try:
            fenetre.evaluate_js(
                "document.documentElement.style.background='transparent';"
                "document.body.style.background='transparent';"
                "document.documentElement.style.outline='none';"
                "document.body.style.outline='none';"
            )
        except Exception:
            pass

    try:
        fenetre.events.restored += lambda: threading.Thread(
            target=apres_restauration, daemon=True
        ).start()
    except Exception:
        pass
    webview.start(apres_demarrage)
