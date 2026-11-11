"""Moteur de compréhension 100 % local via Ollama."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

MODELE_LOCAL = "qwen2.5vl:3b"
URL_OLLAMA = "http://localhost:11434/api/chat"

INSTRUCTIONS = """Tu es IA VOCAL, un assistant personnel Windows qui parle français.
Tu fonctionnes localement. Analyse la demande et retourne UNIQUEMENT un JSON valide.
Deux formats possibles :
{"type":"reponse","texte":"réponse naturelle et concise"}
{"type":"commande","commande":"une commande courte en français à exécuter"}

Si l'utilisateur pose une question, discute ou demande une explication, utilise reponse.
Si l'utilisateur demande une action sur le PC, une application, un site, un fichier ou un réglage,
formule une commande simple et précise à transmettre au moteur local.
N'invente jamais qu'une action a été faite ni qu'une application a été trouvée.
Si une précision indispensable manque, demande-la dans une réponse.
N'utilise jamais de service distant ni de clé API."""


class AssistantLocalIndisponible(Exception):
    pass


def disponible() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2):
            return True
    except Exception:
        return False


def repondre(phrase: str) -> str:
    corps = {
        "model": MODELE_LOCAL,
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {"temperature": 0.1, "num_predict": 160, "num_ctx": 4096},
        "messages": [
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "user", "content": phrase},
        ],
    }
    requete = urllib.request.Request(
        URL_OLLAMA,
        data=json.dumps(corps, ensure_ascii=False).encode("utf-8"),
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=120) as rep:
            donnees = json.loads(rep.read().decode("utf-8"))
        decision = json.loads(donnees["message"]["content"])
    except urllib.error.URLError as exc:
        raise AssistantLocalIndisponible(
            "Le moteur local Ollama ne répond pas. Vérifie qu'il est démarré "
            "et que le modèle qwen2.5vl:3b est installé."
        ) from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise AssistantLocalIndisponible(
            "Le modèle local a renvoyé une réponse illisible. Réessaie."
        ) from exc

    if decision.get("type") == "reponse":
        return str(decision.get("texte", "Je n'ai pas de réponse."))
    if decision.get("type") == "commande":
        commande = str(decision.get("commande", "")).strip()
        return "__COMMANDE__:" + (commande or phrase)
    return "Je n'ai pas compris la demande."
