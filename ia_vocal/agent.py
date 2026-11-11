"""Agent local : observe l'écran et exécute des actions génériques."""

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
MAX_ETAPES = 12
MAX_DEFILAGES_IDENTIQUES = 2
PAUSE_ENTRE_ETAPES = 0.15

_arret = threading.Event()

INSTRUCTIONS = """Tu contrôles un ordinateur Windows. Tu vois une capture d'écran.
Objectif de l'utilisateur : OBJECTIF

Réponds UNIQUEMENT avec un objet JSON, une seule action à la fois. Formats possibles :
{"action": "clic", "x": 500, "y": 300}
{"action": "double_clic", "x": 500, "y": 300}
{"action": "ecrire", "texte": "du texte à taper"}
{"action": "touche", "touche": "enter"} (aussi : esc, tab, ctrl+t, ctrl+l, ctrl+w)
{"action": "defiler", "sens": "bas"} (ou "haut")
{"action": "fini", "message": "résultat bref en français"}

Les coordonnées vont de 0 à 1000. 0 = bord gauche/haut, 1000 = bord droit/bas.
Analyse précisément l'écran avant chaque action. Fais le minimum d'actions nécessaire.
Ne répète jamais une action qui n'a pas produit le résultat attendu.
Quand l'objectif est atteint, réponds "fini".
Si une information manque ou si l'action est impossible, explique-le au lieu d'inventer.
Pour lancer une application, vérifie le menu Démarrer et sa recherche avant de conclure qu'elle est absente."""


class AgentIndisponible(Exception):
    pass


def _capturer() -> str:
    from PIL import ImageGrab

    image = ImageGrab.grab().convert("RGB")
    image.thumbnail((960, 960))
    tampon = io.BytesIO()
    image.save(tampon, format="JPEG", quality=65, optimize=True)
    return base64.b64encode(tampon.getvalue()).decode("ascii")


def _demander(image_b64: str, objectif: str, historique: list[str]) -> dict:
    consigne = INSTRUCTIONS.replace("OBJECTIF", objectif)
    if historique:
        consigne += "\nActions déjà réalisées : " + " ; ".join(historique[-5:])

    corps = {
        "model": MODELE,
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {"temperature": 0, "num_predict": 96, "num_ctx": 4096},
        "messages": [{"role": "user", "content": consigne, "images": [image_b64]}],
    }
    requete = urllib.request.Request(
        URL_OLLAMA,
        data=json.dumps(corps).encode("utf-8"),
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=120) as rep:
            donnees = json.loads(rep.read().decode("utf-8"))
        return json.loads(donnees["message"]["content"])
    except urllib.error.URLError as exc:
        raise AgentIndisponible(
            "Ollama ne répond pas. Vérifie que le moteur local est démarré "
            f"et que le modèle {MODELE} est installé."
        ) from exc


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
        x = max(0, min(largeur - 1, int(float(action["x"]) / 1000 * largeur)))
        y = max(0, min(hauteur - 1, int(float(action["y"]) / 1000 * hauteur)))
        pyautogui.click(x, y) if type_action == "clic" else pyautogui.doubleClick(x, y)
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
    else:
        raise ValueError(f"Action non prise en charge : {type_action}")


def executer_tache(objectif: str, progres: Callable[[str], None]) -> str:
    import pyautogui

    _arret.clear()
    historique: list[str] = []
    dernier_defilement = None
    repetitions_defilement = 0

    for _ in range(MAX_ETAPES):
        if _arret.is_set():
            return "Tâche arrêtée."
        try:
            action = _demander(_capturer(), objectif, historique)
        except AgentIndisponible as exc:
            return str(exc)
        except (KeyError, ValueError, TypeError):
            return "Le modèle n'a pas donné une action exploitable."
        except Exception as exc:
            return f"Erreur pendant l'analyse de l'écran : {exc}"

        type_action = action.get("action")
        if type_action == "fini":
            return str(action.get("message", "Tâche terminée."))
        if type_action == "defiler":
            sens = action.get("sens", "bas")
            repetitions_defilement = repetitions_defilement + 1 if sens == dernier_defilement else 1
            dernier_defilement = sens
            if repetitions_defilement > MAX_DEFILAGES_IDENTIQUES:
                return "J'ai arrêté car le défilement se répétait sans résultat."
        else:
            dernier_defilement = None
            repetitions_defilement = 0

        try:
            _executer(action)
        except pyautogui.FailSafeException:
            return "Action interrompue par la sécurité de la souris."
        except Exception as exc:
            return f"Impossible d'exécuter l'action : {exc}"

        historique.append(json.dumps(action, ensure_ascii=False))
        time.sleep(PAUSE_ENTRE_ETAPES)

    return "Je n'ai pas terminé. La tâche est trop longue ou nécessite une demande plus précise."


@command(r"^(arrête|arrete|stop|arrête la tâche|annule la tâche)$", "arrête la tâche en cours")
def arreter_tache() -> str:
    _arret.set()
    return "J'arrête la tâche en cours."
