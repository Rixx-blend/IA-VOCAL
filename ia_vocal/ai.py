"""Moteur de compréhension 100 % local via Ollama."""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.request

MODELE_LOCAL = "qwen2.5vl:3b"
URL_OLLAMA = "http://localhost:11434/api/chat"

INSTRUCTIONS = """Tu es IA VOCAL, un assistant personnel Windows qui parle français.
IDENTITÉ TECHNIQUE À RESPECTER :
- Le modèle qui génère tes réponses est Qwen 2.5 VL 3B.
- Ce modèle est développé par Alibaba Cloud et exécuté localement par Ollama.
- Tu n'es pas un modèle Microsoft, OpenAI, Google ou un autre fournisseur.
- Ollama est le moteur d'exécution local, pas le créateur du modèle.
- Ne prétends pas connaître une autre identité technique et n'invente jamais de version.
Tu fonctionnes localement. Analyse la demande et retourne UNIQUEMENT un JSON valide.
Deux formats possibles :
{"type":"reponse","texte":"réponse naturelle, adaptée à la complexité de la demande"}
{"type":"commande","commande":"une commande courte en français à exécuter"}

Si l'utilisateur demande quel modèle tu es, qui l'a développé, quel moteur tu utilises
ou si tu fonctionnes localement, réponds directement avec les informations exactes
ci-dessus, sans transformer cette question en commande.
Pour les réponses :
- Adapte la longueur à la demande : réponse brève pour une question simple, explication développée pour une question complexe.
- Ne raccourcis pas artificiellement tes réponses. Donne les informations nécessaires pour répondre complètement.
- Pour une explication ou un tutoriel, avance par étapes numérotées et explique les termes techniques simplement.
- Ajoute des exemples concrets lorsqu'ils améliorent réellement la compréhension.
- Pour une comparaison, présente les différences importantes et termine par une conclusion claire.
- Si tu ne connais pas une information ou si tu n'es pas certain, dis-le clairement au lieu d'inventer.
- Évite les répétitions, les introductions inutiles et les conclusions creuses.
Si l'utilisateur pose une autre question, discute ou demande une explication, utilise reponse.
Si l'utilisateur demande une action sur le PC, une application, un site, un fichier ou un réglage,
formule une commande simple et précise à transmettre au moteur local.
N'invente jamais qu'une action a été faite ni qu'une application a été trouvée.
Si une précision indispensable manque, demande-la dans une réponse.
N'utilise jamais de service distant ni de clé API."""


def _normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in texte if not unicodedata.combining(c))


def _question_identite(phrase: str) -> str | None:
    """Répond de façon déterministe aux questions sur l'identité du modèle."""
    texte = _normaliser(phrase)
    mots_cles = (
        "quel modele", "quelle ia", "quelle intelligence artificielle",
        "qui t a developpe", "qui a developpe", "qui t a cree",
        "qui a cree", "tu es base sur", "tu utilises quel",
        "quel moteur", "tu fonctionnes localement", "tu es local",
        "tu viens de microsoft", "tu es microsoft",
    )
    if not any(mot in texte for mot in mots_cles):
        return None

    if "local" in texte or "localement" in texte or "moteur" in texte:
        return (
            "Je suis IA VOCAL. Mon modèle est Qwen 2.5 VL 3B, développé par "
            "Alibaba Cloud. Il fonctionne localement sur ton ordinateur grâce à Ollama."
        )
    if "qui t a developpe" in texte or "qui a developpe" in texte or "qui t a cree" in texte or "qui a cree" in texte:
        return "Le modèle que j'utilise, Qwen 2.5 VL 3B, est développé par Alibaba Cloud. IA VOCAL est l'application qui l'utilise."
    return "Je suis IA VOCAL, propulsé par Qwen 2.5 VL 3B, un modèle développé par Alibaba Cloud et exécuté localement avec Ollama."


class AssistantLocalIndisponible(Exception):
    pass


def disponible() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2):
            return True
    except Exception:
        return False


def repondre(phrase: str) -> str:
    identite = _question_identite(phrase)
    if identite:
        return json.dumps({"type": "reponse", "texte": identite}, ensure_ascii=False)

    corps = {
        "model": MODELE_LOCAL,
        "stream": False,
        "format": "json",
        "keep_alive": -1,
        "options": {"temperature": 0.1, "num_predict": 600, "num_ctx": 4096},
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
