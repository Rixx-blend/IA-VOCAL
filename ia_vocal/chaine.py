"""Enchaîne plusieurs ordres dans une seule phrase.

« va sur Google et ouvre un nouvel onglet » -> deux étapes, exécutées dans l'ordre.
Une courte pause sépare les étapes, pour laisser le temps au navigateur de charger.
"""

from __future__ import annotations

import re
import time

from . import positions  # noqa: F401  (enregistre les commandes d'endroits)
from .commands import command, dispatch, reconnait

SEPARATEURS = re.compile(
    r"\s*(?:,|\bet puis\b|\bpuis\b|\bensuite\b|\bhop\b|\bet\b|\baprès\b|\bapres\b|\bthen\b)\s*",
    re.IGNORECASE,
)
PAUSE_ENTRE_ETAPES = 1.5  # secondes


@command(r"^(t'es là|t'es la|tu es là|tu es la|es-tu là|tu m'entends|t'es là\?)\??$",
         "dis bonjour pour vérifier que l'assistant répond")
def presence() -> str:
    return "Oui, je suis là."


def decouper(texte: str) -> list[str]:
    return [etape.strip() for etape in SEPARATEURS.split(texte) if etape and etape.strip()]


def executer(texte: str) -> str | None:
    """Exécute la phrase, étape par étape si elle en contient plusieurs.

    Retourne None si la phrase n'est pas comprise, pour laisser la main à l'assistant.
    """
    etapes = decouper(texte)

    # On vérifie toutes les étapes avant d'en exécuter une seule
    if len(etapes) > 1 and all(reconnait(e) for e in etapes):
        resultats = []
        for i, etape in enumerate(etapes):
            resultats.append(dispatch(etape) or "")
            if i < len(etapes) - 1:
                time.sleep(PAUSE_ENTRE_ETAPES)
        return " ; ".join(r for r in resultats if r)

    # Une seule action (qui contient peut-être un « et » dans son texte)
    if reconnait(texte):
        return dispatch(texte)
    return None
