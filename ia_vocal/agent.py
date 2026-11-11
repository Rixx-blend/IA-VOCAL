"""Agent local : observe l'écran et exécute des actions génériques."""

from __future__ import annotations

import base64
import io
import json
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from typing import Callable

from .commands import command

MODELE = os.environ.get("IA_VOCAL_MODELE", "qwen2.5vl:3b")
URL_OLLAMA = os.environ.get("IA_VOCAL_OLLAMA_URL", "http://localhost:11434/api/chat")
MAX_ETAPES = 12
PAUSE_ENTRE_ETAPES = 0.12

_arret = threading.Event()

INSTRUCTIONS = """Tu contrôles un ordinateur Windows. Tu vois une capture d'écran.
Objectif de l'utilisateur : OBJECTIF

Réponds UNIQUEMENT avec un objet JSON, une seule action à la fois. Formats possibles :
{"action": "clic", "x": 500, "y": 300}
{"action": "double_clic", "x": 500, "y": 300}
{"action": "ecrire", "texte": "du texte à taper"}
{"action": "touche", "touche": "enter"} (raccourcis possibles : alt+f4, esc, tab, ctrl+w, ctrl+l)
{"action": "defiler", "sens": "bas"} (ou "haut")
{"action": "fini", "message": "résultat bref en français"}

Les coordonnées vont de 0 à 1000. 0 = bord gauche/haut, 1000 = bord droit/bas.
Analyse précisément l'écran avant chaque action. Fais le minimum d'actions nécessaire.
Pour fermer une application ou une fenêtre, repère d'abord sa fenêtre et utilise le bouton de fermeture ou Alt+F4. Ne fais JAMAIS défiler l'écran pour fermer une application.
Ne fais défiler que si le contenu recherché est réellement plus bas ou plus haut dans la page.
Après chaque action, vérifie visuellement le résultat. Si l'écran n'a pas changé, choisis une autre méthode au lieu de répéter la même action.
Quand l'objectif est atteint, réponds "fini".
Si une information manque ou si l'action est impossible, explique-le au lieu d'inventer.
Pour lancer une application, vérifie le menu Démarrer et sa recherche avant de conclure qu'elle est absente."""


class AgentIndisponible(Exception):
    pass


def _normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in texte if not unicodedata.combining(c))


def _fermer_fenetre_cible(objectif: str) -> str | None:
    """Ferme proprement une fenêtre Windows correspondant à l'application demandée."""
    demande = _normaliser(objectif)
    if not re.search(r"\b(ferme|fermer|quitte|quitter|close|clos)\b", demande):
        return None

    mots = re.findall(r"[a-z0-9]+", demande)
    mots = [
        mot for mot in mots
        if mot not in {
            "ferme", "fermer", "quitte", "quitter", "close", "clos",
            "application", "app", "logiciel", "fenetre", "fenetre",
            "qui", "est", "ouvert", "ouverte", "lance", "arrete",
        }
    ]
    if not mots:
        return None

    try:
        import pyautogui
        fenetres = pyautogui.getAllWindows()
    except Exception:
        return None

    cible = None
    meilleur_score = 0
    for fenetre in fenetres:
        titre = _normaliser(str(getattr(fenetre, "title", "") or "")).strip()
        if not titre or "ia vocal" in titre:
            continue
        score = sum(1 for mot in mots if mot in titre.split() or mot in titre)
        if score > meilleur_score:
            meilleur_score = score
            cible = fenetre

    if cible is None or meilleur_score == 0:
        return None

    try:
        if getattr(cible, "isMinimized", False):
            cible.restore()
        cible.activate()
        time.sleep(0.25)
        import pyautogui
        pyautogui.hotkey("alt", "f4")
        time.sleep(0.35)
        return f"J'ai envoyé la commande de fermeture à la fenêtre « {cible.title} »."
    except Exception:
        return None


def _capturer() -> str:
    from PIL import ImageGrab

    image = ImageGrab.grab().convert("RGB")
    image.thumbnail((960, 960))
    tampon = io.BytesIO()
    image.save(tampon, format="JPEG", quality=65, optimize=True)
    return base64.b64encode(tampon.getvalue()).decode("ascii")


def _demander(image_b64: str, objectif: str, historique: list[str], defilement_interdit: bool = False) -> dict:
    consigne = INSTRUCTIONS.replace("OBJECTIF", objectif)
    if historique:
        consigne += "\nActions déjà réalisées : " + " ; ".join(historique[-5:])
    if defilement_interdit:
        consigne += "\nIMPORTANT : le défilement a déjà échoué. Le défilement est interdit pour cette tâche. Choisis une action différente adaptée à l'objectif."

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
        with urllib.request.urlopen(requete, timeout=90) as rep:
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
    fermeture = _fermer_fenetre_cible(objectif)
    if fermeture:
        return fermeture

    historique: list[str] = []
    dernier_defilement = None
    repetitions_defilement = 0
    defilement_interdit = bool(
        re.search(r"\b(ferme|fermer|quitte|quitter|close|clos)\b", _normaliser(objectif))
    )

    for _ in range(MAX_ETAPES):
        if _arret.is_set():
            return "Tâche arrêtée."
        try:
            capture = _capturer()
            action = _demander(capture, objectif, historique, defilement_interdit)
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
            if defilement_interdit or repetitions_defilement > 1:
                defilement_interdit = True
                historique.append("Défilement refusé : action inadaptée ou sans résultat. Choisir une autre action.")
                continue
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

    return "Je n'ai pas terminé. La tâche a atteint sa limite d'actions."


@command(r"^(arrête|arrete|stop|arrête la tâche|annule la tâche)$", "arrête la tâche en cours")
def arreter_tache() -> str:
    _arret.set()
    return "J'arrête la tâche en cours."
