"""Commandes du PC et de Google : onglets, recherche, dossiers, son, système, calcul, notes.

Les raccourcis clavier (onglets, volume) ne fonctionnent que sous Windows.
Ce module est importé avant actions.py, pour que ses motifs passent
avant la commande générique « ouvre … ».
"""

from __future__ import annotations

import ast
import datetime as _dt
import operator
import os
import platform
import subprocess
import urllib.parse
import webbrowser
from pathlib import Path

from .commands import command

SYSTEME = platform.system()

SITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "drive": "https://drive.google.com",
    "maps": "https://maps.google.com",
    "agenda": "https://calendar.google.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "twitch": "https://www.twitch.tv",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://fr.wikipedia.org",
    "amazon": "https://www.amazon.fr",
}

DOSSIERS = {
    "documents": "Documents",
    "téléchargements": "Downloads",
    "telechargements": "Downloads",
    "bureau": "Desktop",
    "images": "Pictures",
    "photos": "Pictures",
    "vidéos": "Videos",
    "videos": "Videos",
    "musique": "Music",
}

# Codes de touches virtuelles Windows
VK_CTRL, VK_SHIFT, VK_ALT = 0x11, 0x10, 0x12
VK_TAB, VK_T, VK_W = 0x09, 0x54, 0x57
VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF


def _raccourci(*touches: int) -> str | None:
    """Appuie sur une combinaison de touches (Windows seulement)."""
    if SYSTEME != "Windows":
        return "Ce raccourci n'est disponible que sous Windows."
    import ctypes

    clavier = ctypes.windll.user32.keybd_event
    for touche in touches:
        clavier(touche, 0, 0, 0)
    for touche in reversed(touches):
        clavier(touche, 0, 2, 0)  # 2 = relâcher la touche
    return None


def _url(cible: str) -> str:
    """Transforme une cible dite à l'oral en adresse web (site connu, adresse ou recherche)."""
    cible = cible.strip()
    cle = cible.lower()
    if cle in SITES:
        return SITES[cle]
    if cible.startswith(("http://", "https://")):
        return cible
    if "." in cible and " " not in cible:
        return f"https://{cible}"
    return _recherche(cible)


def _recherche(requete: str) -> str:
    return "https://www.google.com/search?q=" + urllib.parse.quote(requete)


def _ouvrir_chemin(chemin: Path) -> None:
    if SYSTEME == "Windows":
        os.startfile(chemin)  # type: ignore[attr-defined]
    elif SYSTEME == "Darwin":
        subprocess.Popen(["open", str(chemin)])
    else:
        subprocess.Popen(["xdg-open", str(chemin)])


# ---------- Onglets du navigateur ----------

@command(r"^(ouvre|crée|cree|ajoute)( un| un nouvel| nouvel)? onglet$",
         "ouvre un onglet")
def nouvel_onglet() -> str:
    return _raccourci(VK_CTRL, VK_T) or "J'ouvre un nouvel onglet."


@command(r"^(ouvre|lance|crée|cree) (un |un nouvel )?onglet (sur |vers |pour |avec )?(?P<cible>.+)$",
         "ouvre un onglet sur <site ou recherche>")
def onglet_sur(cible: str) -> str:
    url = _url(cible)
    webbrowser.open_new_tab(url)
    return f"J'ouvre un onglet sur {cible}."


@command(r"^ferme (cet |ce |l'|le |l )?onglet$", "ferme l'onglet")
def ferme_onglet() -> str:
    return _raccourci(VK_CTRL, VK_W) or "J'ai fermé l'onglet."


@command(r"^(rouvre|réouvre|reouvre)( le dernier| l')? onglet$", "rouvre l'onglet")
def rouvre_onglet() -> str:
    return _raccourci(VK_CTRL, VK_SHIFT, VK_T) or "J'ai rouvert l'onglet."


@command(r"^(onglet suivant|prochain onglet|change d'onglet)$", "onglet suivant")
def onglet_suivant() -> str:
    return _raccourci(VK_CTRL, VK_TAB) or "Onglet suivant."


@command(r"^(onglet précédent|onglet precedent|onglet d'avant)$", "onglet précédent")
def onglet_precedent() -> str:
    return _raccourci(VK_CTRL, VK_SHIFT, VK_TAB) or "Onglet précédent."


# ---------- Google et web ----------

@command(r"^(cherche|recherche|google|cherche sur google|recherche sur google) (?P<requete>.+)$",
         "cherche <texte> sur Google")
def cherche(requete: str) -> str:
    webbrowser.open(_recherche(requete))
    return f"Je cherche « {requete} » sur Google."


@command(r"^(va sur|va à|va a|va vers|aller sur|ouvre le site) (?P<cible>.+)$",
         "va sur <site>")
def va_sur(cible: str) -> str:
    webbrowser.open(_url(cible))
    return f"J'ouvre {cible}."


# ---------- Dossiers ----------

@command(r"^ouvre (mes |le |les |le dossier )?(?P<dossier>documents|téléchargements|telechargements|"
         r"bureau|images|photos|vidéos|videos|musique)$",
         "ouvre <documents, bureau, téléchargements…>")
def ouvre_dossier(dossier: str) -> str:
    nom = DOSSIERS[dossier.lower()]
    chemin = Path.home() / nom
    if not chemin.exists():
        return f"Je ne trouve pas le dossier {dossier}."
    _ouvrir_chemin(chemin)
    return f"J'ouvre {dossier}."


# ---------- Son et écran ----------

@command(r"^(augmente|monte|plus fort)( le)? ?(volume|son)?$", "augmente le volume")
def volume_plus() -> str:
    return _raccourci(VK_VOLUME_UP) or "Volume augmenté."


@command(r"^(baisse|diminue|moins fort)( le)? ?(volume|son)?$", "baisse le volume")
def volume_moins() -> str:
    return _raccourci(VK_VOLUME_DOWN) or "Volume baissé."


@command(r"^(coupe|mets en sourdine|muet|active le son|réactive le son)( le)? ?(son|volume)?$",
         "coupe ou rétablit le son")
def son_muet() -> str:
    return _raccourci(VK_VOLUME_MUTE) or "Son coupé ou rétabli."


@command(r"^(capture|capture d'écran|fais une capture|fais une capture d'écran|screenshot)$",
         "capture d'écran")
def capture_ecran() -> str:
    from PIL import ImageGrab

    dossier = Path.home() / "Pictures"
    dossier.mkdir(exist_ok=True)
    fichier = dossier / f"capture-{_dt.datetime.now():%Y%m%d-%H%M%S}.png"
    ImageGrab.grab().save(fichier)
    return f"Capture enregistrée dans {fichier.name}."


# ---------- Système ----------

@command(r"^(verrouille|verrouiller)( l'écran| l'ordinateur| le pc| le ordinateur)?$",
         "verrouille l'ordinateur")
def verrouille() -> str:
    if SYSTEME == "Windows":
        import ctypes

        ctypes.windll.user32.LockWorkStation()
        return "Ordinateur verrouillé."
    return "Ce verrouillage n'est disponible que sous Windows."


@command(r"^(éteins|eteins|arrête|arrete)( l')?ordinateur( dans (?P<minutes>\d+) minutes?)?$",
         "éteins l'ordinateur (dans N minutes)")
def eteins(minutes: str | None = None) -> str:
    if SYSTEME != "Windows":
        return "Cette commande n'est disponible que sous Windows."
    secondes = int(minutes) * 60 if minutes else 60  # une minute de marge par défaut
    subprocess.Popen(["shutdown", "/s", "/t", str(secondes)])
    return f"Extinction dans {secondes // 60 or 1} minute(s). Dis « annule l'extinction » pour arrêter."


@command(r"^annule (l')?(extinction|arrêt|arret)$", "annule l'extinction")
def annule_extinction() -> str:
    if SYSTEME != "Windows":
        return "Cette commande n'est disponible que sous Windows."
    subprocess.Popen(["shutdown", "/a"])
    return "Extinction annulée."


@command(r"^(quel jour (on est|sommes-nous)|quelle date|date)\??$", "quelle date")
def date_du_jour() -> str:
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]
    now = _dt.datetime.now()
    return f"On est {jours[now.weekday()]} {now.day} {mois[now.month - 1]} {now.year}."


# ---------- Calcul ----------

_OPERATIONS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _evaluer(noeud: ast.AST) -> float:
    if isinstance(noeud, ast.Expression):
        return _evaluer(noeud.body)
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)):
        return noeud.value
    if isinstance(noeud, ast.BinOp) and type(noeud.op) in _OPERATIONS:
        return _OPERATIONS[type(noeud.op)](_evaluer(noeud.left), _evaluer(noeud.right))
    if isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, ast.USub):
        return -_evaluer(noeud.operand)
    raise ValueError("calcul non pris en charge")


def _calculer(texte: str) -> str:
    expression = texte.lower().replace(",", ".")
    for mot, symbole in [(" divisé par ", "/"), (" divise par ", "/"), (" fois ", "*"),
                         (" plus ", "+"), (" moins ", "-"), (" x ", "*")]:
        expression = expression.replace(mot, symbole)
    expression = expression.replace(" ", "")
    try:
        resultat = _evaluer(ast.parse(expression, mode="eval"))
    except ZeroDivisionError:
        return "Division par zéro impossible."
    except (SyntaxError, ValueError):
        return "Je ne sais pas calculer ça."
    if float(resultat).is_integer():
        resultat = int(resultat)
    return f"{texte.strip()} = {resultat}"


@command(r"^(combien (font|fait|fait-il|ça fait|ca fait|c'est)|calcule) (?P<calcul>.*\d.*)$",
         "combien font <calcul>")
def calcule(calcul: str) -> str:
    return _calculer(calcul)


# ---------- Notes ----------

FICHIER_NOTES = Path.home() / "IA-VOCAL-notes.txt"


@command(r"^(note|prends note|noter)( que)? (?P<texte>.+)$", "note <texte>")
def note(texte: str) -> str:
    horodatage = _dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    with FICHIER_NOTES.open("a", encoding="utf-8") as fichier:
        fichier.write(f"[{horodatage}] {texte.strip()}\n")
    return "Note enregistrée."


@command(r"^(ouvre|lis) (mes )?notes$", "ouvre mes notes")
def ouvre_notes() -> str:
    if not FICHIER_NOTES.exists():
        return "Tu n'as encore aucune note."
    _ouvrir_chemin(FICHIER_NOTES)
    return "J'ouvre tes notes."
