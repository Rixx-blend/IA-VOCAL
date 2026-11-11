"""Assistant : comprend une phrase libre et choisit une action à exécuter.

Le modèle ne fait qu'indiquer une action parmi une liste fixe. C'est ce
programme qui exécute l'action, et seules les actions ci-dessous existent.
Nécessite la variable d'environnement ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from . import actions
from .apps import lancer_application

MODELE = "claude-haiku-5-5"
URL_API = "https://api.anthropic.com/v1/messages"

INSTRUCTIONS = """Tu es le moteur de IA VOCAL, un assistant qui parle français.
Tu reçois une demande de l'utilisateur et tu réponds UNIQUEMENT avec un objet JSON,
sans texte autour, de la forme {"action": "<nom>", "args": {...}}.

Actions possibles :
- "ouvre" : args {"cible": "<site web ou nom d'application>"}
- "lance" : args {"nom": "<nom d'application>"}
- "minuteur" : args {"secondes": <entier>}
- "musique" : args {}
- "heure" : args {}
- "reponse" : args {"texte": "<réponse courte en français>"}, pour répondre
  à une question ou discuter
- "inconnu" : args {"texte": "<explication courte>"}, si la demande ne peut
  pas être faite avec les actions ci-dessus

N'invente aucune autre action."""


class AssistantIndisponible(Exception):
    pass


def disponible() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _interroger_modele(phrase: str) -> dict:
    cle = os.environ["ANTHROPIC_API_KEY"]
    corps = json.dumps({
        "model": MODELE,
        "max_tokens": 300,
        "system": INSTRUCTIONS,
        "messages": [{"role": "user", "content": phrase}],
    }).encode("utf-8")
    requete = urllib.request.Request(
        URL_API,
        data=corps,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": cle,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(requete, timeout=20) as rep:
            donnees = json.loads(rep.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise AssistantIndisponible(f"pas de connexion ({exc.reason})") from exc

    texte = "".join(
        bloc.get("text", "") for bloc in donnees.get("content", [])
        if bloc.get("type") == "text"
    )
    debut, fin = texte.find("{"), texte.rfind("}")
    return json.loads(texte[debut:fin + 1])


def _executer(decision: dict) -> str:
    action = decision.get("action")
    args = decision.get("args") or {}

    if action == "ouvre":
        return actions.ouvre(cible=str(args["cible"]))
    if action == "lance":
        return lancer_application(str(args["nom"]))
    if action == "minuteur":
        return actions.minuteur(duree=str(int(args["secondes"])), unite="secondes")
    if action == "musique":
        return actions.lance_musique()
    if action == "heure":
        return actions.heure()
    if action in ("reponse", "inconnu"):
        return str(args.get("texte", "")) or "Je n'ai rien à répondre."
    return "Je ne sais pas faire ça."


def repondre(phrase: str) -> str:
    """Comprend la phrase, exécute l'action choisie et retourne le message à afficher."""
    if not disponible():
        return (
            "Je ne comprends que les commandes connues. Pour comprendre tout ce que "
            "tu dis, ajoute la variable ANTHROPIC_API_KEY."
        )
    try:
        return _executer(_interroger_modele(phrase))
    except AssistantIndisponible as exc:
        return f"Assistant indisponible : {exc}."
    except (KeyError, TypeError, ValueError):
        return "Je n'ai pas compris la demande."
    except Exception as exc:  # on ne plante pas l'overlay
        return f"Erreur : {exc}"
