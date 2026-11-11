"""Contrôle de la souris et du clavier : déplacer, cliquer, défiler, écrire.

Les bibliothèques sont importées au moment de l'usage, pour que l'application
démarre même si l'une d'elles manque.

Sécurité : pyautogui arrête tout si la souris touche un coin de l'écran
(« failsafe »). C'est un bon moyen d'interrompre une action en cours.
"""

from __future__ import annotations

from .commands import command

PAS_PAR_DEFAUT = 100  # pixels, pour « déplace la souris vers la gauche »

TOUCHES = {
    "entrée": "enter", "entrer": "enter",
    "échap": "esc", "echap": "esc",
    "tab": "tab", "tabulation": "tab",
    "espace": "space",
    "suppr": "delete", "supprimer": "delete",
    "retour arrière": "backspace", "retour arriere": "backspace",
    "windows": "win",
    "flèche haut": "up", "flèche bas": "down",
    "flèche gauche": "left", "flèche droite": "right",
}

RACCOURCIS = {
    "ctrl c": ("ctrl", "c"), "ctrl v": ("ctrl", "v"), "ctrl x": ("ctrl", "x"),
    "ctrl z": ("ctrl", "z"), "ctrl a": ("ctrl", "a"), "ctrl s": ("ctrl", "s"),
    "ctrl w": ("ctrl", "w"), "ctrl t": ("ctrl", "t"),
}


def _pyautogui():
    import pyautogui

    return pyautogui


@command(r"^(clique|clic|click|clique ici)$", "clique")
def clique() -> str:
    _pyautogui().click()
    return "Clic."


@command(r"^(double clic|double-clic|double clique|double-clique)$", "double clic")
def double_clic() -> str:
    _pyautogui().doubleClick()
    return "Double clic."


@command(r"^(clic droit|clique droit|clic-droit|clique à droite)$", "clic droit")
def clic_droit() -> str:
    _pyautogui().rightClick()
    return "Clic droit."


@command(r"^(défile|defile|fais défiler|scroll) (vers le |en )?(?P<sens>haut|bas)$",
         "défile vers le haut ou le bas")
def defile(sens: str) -> str:
    cran = 500 if sens.lower() == "haut" else -500
    _pyautogui().scroll(cran)
    return f"Je défile vers le {sens}."


@command(r"^(déplace|deplace|bouge|mets) (la )?souris (en |au |à )?"
         r"(?P<place>haut à gauche|haut à droite|bas à gauche|bas à droite|"
         r"en haut|en bas|à gauche|à droite|au centre|au milieu)$",
         "déplace la souris (haut à gauche, au centre…)")
def place_souris(place: str) -> str:
    pg = _pyautogui()
    largeur, hauteur = pg.size()
    marge = 20
    x = {"gauche": marge, "droite": largeur - marge}
    y = {"haut": marge, "bas": hauteur - marge}
    place = place.lower()
    if place in ("au centre", "au milieu"):
        pos = (largeur // 2, hauteur // 2)
    else:
        horizontal = "gauche" if "gauche" in place else "droite" if "droite" in place else None
        vertical = "haut" if "haut" in place else "bas" if "bas" in place else None
        pos = (x.get(horizontal, pg.position().x), y.get(vertical, pg.position().y))
    pg.moveTo(*pos, duration=0.3)
    return "Souris déplacée."


@command(r"^(déplace|deplace|bouge|mets) (la )?souris (vers le |vers la |à |a )?"
         r"(?P<sens>haut|bas|gauche|droite)( de (?P<pixels>\d+)( pixels?)?)?$",
         "déplace la souris vers le haut, le bas, la gauche ou la droite")
def bouge_souris(sens: str, pixels: str | None = None) -> str:
    pg = _pyautogui()
    pas = int(pixels) if pixels else PAS_PAR_DEFAUT
    dx = dy = 0
    if sens == "haut":
        dy = -pas
    elif sens == "bas":
        dy = pas
    elif sens == "gauche":
        dx = -pas
    else:
        dx = pas
    pg.moveRel(dx, dy, duration=0.2)
    return "Souris déplacée."


@command(r"^(déplace|deplace|mets) (la )?souris (à|a|en) (?P<x>\d+)[ ,x]+(?P<y>\d+)$",
         "déplace la souris à <x> <y>")
def souris_en_position(x: str, y: str) -> str:
    _pyautogui().moveTo(int(x), int(y), duration=0.3)
    return f"Souris en position {x}, {y}."


@command(r"^(écris|ecris|écrit|tape|saisis) (?P<texte>.+)$", "écris <texte>")
def ecris(texte: str) -> str:
    # Le presse-papiers gère les accents et les caractères spéciaux
    import pyperclip

    pg = _pyautogui()
    pyperclip.copy(texte)
    pg.hotkey("ctrl", "v")
    return "Texte écrit."


@command(r"^appuie sur (?P<touche>.+)$", "appuie sur <touche ou raccourci>")
def appuie(touche: str) -> str:
    cle = touche.strip().lower()
    pg = _pyautogui()
    if cle in RACCOURCIS:
        pg.hotkey(*RACCOURCIS[cle])
    elif cle in TOUCHES:
        pg.press(TOUCHES[cle])
    else:
        return f"Je ne connais pas la touche « {touche} »."
    return f"J'ai appuyé sur {touche}."
