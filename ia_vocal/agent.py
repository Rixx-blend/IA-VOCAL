"""Agent local : voit l'écran, choisit une action, l'exécute, puis recommence.

Utilise un petit modèle de vision lancé avec Ollama (gratuit, sans internet pour le modèle).
Variables d'environnement facultatives :
- IA_VOCAL_MODELE : nom du modèle Ollama (défaut : qwen2.5vl:3b)
- IA_VOCAL_OLLAMA_URL : adresse de l'API Ollama (défaut : http://localhost:11434/api/chat)
"""

from __future__ import annotations

import base64
import io
import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Callable

from .commands import command

MODELE = os.environ.get("IA_VOCAL_MODELE", "qwen2.5vl:3b")
URL_OLLAMA = os.environ.get("IA_VOCAL_OLLAMA_URL", "http://localhost:11434/api/chat")
MAX_ETAPES = 12                   # limite de sécurité par tâche
MAX_DEFILAGES_IDENTIQUES = 2       # évite les défilements répétés si le modèle boucle
PAUSE_ENTRE_ETAPES = 0.2           # délai court entre les actions

_arret = threading.Event()

INSTRUCTIONS = """Tu contrôles un ordinateur Windows. Tu vois une capture d'écran.
Objectif de l'utilisateur : OBJECTIF

Réponds UNIQUEMENT avec un objet JSON, une seule action à la fois. Formats possibles :
{"action": "clic", "x": 500, "y": 300}
{"action": "double_clic", "x": 500, "y": 300}
{"action": "ecrire", "texte": "du texte à taper"}
{"action": "touche", "touche": "enter"}   (aussi : esc, tab, ctrl+t, ctrl+l, ctrl+w)
{"action": "defiler", "sens": "bas"}      (ou "haut")
{"action": "fini", "message": "ce que tu as fait, en français"}

Les coordonnées x et y vont de 0 à 1000 : 0 = bord gauche ou haut, 1000 = bord droit ou bas.
Quand l'objectif est atteint, réponds avec l'action "fini".
Si l'utilisateur ne précise pas quelle application il veut lancer, ne choisis pas au hasard :
réponds avec l'action "fini" et demande le nom de l'application.
Si l'application demandée n'apparaît pas à l'écran, utilise le menu Démarrer et sa recherche.
Ne dis pas qu'une application est introuvable sans avoir vérifié le menu Démarrer."""


class AgentIndisponible(Exception):
    pass


def _capturer() -> str:
    """Capture l'écran et retourne l'image en base64 (JPEG, réduite pour aller vite)."""
    from PIL import ImageGrab

    image = ImageGrab.grab().convert("RGB")
    image.thumbnail((1024, 1024))
    tampon = io.BytesIO()
    image.save(tampon, format="JPEG", quality=68)
    return base64.b64encode(tampon.getvalue()).decode("ascii")


def _demander(image_b64: str, objectif: str, historique: list[str]) -> dict:
    consigne = INSTRUCTIONS.replace("OBJECTIF", objectif)
    if historique:
        consigne += "\n\nActions déjà faites : " + " ; ".join(historique)

    corps = {
        "model": MODELE,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 96, "num_ctx": 2048},
        "keep_alive": "10m",
        "messages": [{"role": "user", "content": consigne, "images": [image_b64]}],
    }
    requete = urllib.request.Request(
        URL_OLLAMA,
        data=json.dumps(corps).encode("utf-8"),
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=180) as rep:
            donnees = json.loads(rep.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise AgentIndisponible(
            "Ollama ne répond pas. Vérifie qu'il est lancé, puis que le modèle "
            f"« {MODELE} » est installé (commande : ollama pull {MODELE})."
        ) from exc
    return json.loads(donnees["message"]["content"])


def _ecrire(texte: str) -> None:
    import pyautogui
    import pyperclip

    pyperclip.copy(texte)
    pyautogui.hotkey("ctrl", "v")


def _executer(action: dict) -> None:
    import pyautogui

    type_action = action.get("action")

    if type_action in ("clic", "double_clic"):
        largeur, hauteur = pyautogui.size()
        x = int(float(action["x"]) / 1000 * largeur)
        y = int(float(action["y"]) / 1000 * hauteur)
        pyautogui.moveTo(x, y, duration=0.08)
        if type_action == "clic":
            pyautogui.click()
        else:
            pyautogui.doubleClick()
    elif type_action == "ecrire":
        _ecrire(str(action.get("texte", "")))
    elif type_action == "touche":
        touche = str(action.get("touche", "")).lower()
        if "+" in touche:
            pyautogui.hotkey(*touche.split("+"))
        else:
            pyautogui.press(touche)
    elif type_action == "defiler":
        pyautogui.scroll(-250 if action.get("sens") == "bas" else 250)


def _action_rapide_blender(objectif: str) -> str | None:
    """Raccourci déterministe pour retirer le cube initial de Blender."""
    import re
    import pyautogui

    demande = objectif.lower()
    mots = ("supprime", "supprimer", "efface", "effacer", "enleve", "enlève", "retire", "retirer")
    if not any(mot in demande for mot in mots) or not re.search(r"\bcube\b", demande):
        return None

    try:
        titre = (pyautogui.getActiveWindowTitle() or "").lower()
        if "blender" not in titre:
            return None
        import pyperclip

        largeur, hauteur = pyautogui.size()
        pyautogui.moveTo(largeur // 2, hauteur // 2)
        pyautogui.hotkey("shift", "f4")  # console Python de Blender
        pyperclip.copy('obj = bpy.data.objects.get("Cube"); bpy.data.objects.remove(obj, do_unlink=True) if obj else None')
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        time.sleep(0.15)
        pyautogui.hotkey("shift", "f5")  # retour à la vue 3D
        return "Le cube de base a été supprimé."
    except Exception:
        return None


def executer_tache(objectif: str, progres: Callable[[str], None]) -> str:
    """Exécute une tâche étape par étape. Retourne le message final."""
    import pyautogui

    _arret.clear()
    resultat_rapide = _action_rapide_blender(objectif)
    if resultat_rapide:
        return resultat_rapide
    historique: list[str] = []
    dernier_defilement = None
    repetitions_defilement = 0

    for etape in range(1, MAX_ETAPES + 1):
        if _arret.is_set():
            return "Tâche arrêtée."
        try:
            action = _demander(_capturer(), objectif, historique)
        except AgentIndisponible as exc:
            return str(exc)
        except (KeyError, ValueError, TypeError):
            return "Le modèle n'a pas donné une action exploitable."
        except Exception as exc:  # on ne plante pas l'overlay
            return f"Erreur : {exc}"

        if action.get("action") == "fini":
            return str(action.get("message", "C'est fait."))

        # Le modèle peut parfois redemander le même défilement alors que la page bouge.
        # On limite ces répétitions pour éviter que la page ne parte en boucle.
        if action.get("action") == "defiler":
            sens = action.get("sens", "bas")
            if sens == dernier_defilement:
                repetitions_defilement += 1
            else:
                dernier_defilement = sens
                repetitions_defilement = 1
            if repetitions_defilement > MAX_DEFILAGES_IDENTIQUES:
                return "J'ai interrompu le défilement répétitif pour éviter de faire défiler la page en boucle."
        else:
            dernier_defilement = None
            repetitions_defilement = 0

        # Les détails techniques des étapes ne sont pas affichés dans le chat.
        try:
            _executer(action)
        except pyautogui.FailSafeException:
            return "Arrêt de sécurité : la souris était dans un coin de l'écran."
        except Exception as exc:
            return f"Erreur pendant l'action : {exc}"

        historique.append(json.dumps(action, ensure_ascii=False))
        time.sleep(PAUSE_ENTRE_ETAPES)

    return "Je n'ai pas fini dans le nombre d'étapes prévu. Précise la demande ou découpe-la."


@command(r"^(arrête|arrete|stop|arrête la tâche|annule la tâche)$", "arrête la tâche en cours")
def arreter_tache() -> str:
    _arret.set()
    return "J'arrête la tâche en cours."
