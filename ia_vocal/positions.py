"""Endroits retenus à l'écran : « retiens cet endroit comme Google », puis « déplace la souris sur Google ».

Les positions sont enregistrées dans un fichier, pour survivre au redémarrage.
"""

from __future__ import annotations

import json
from pathlib import Path

from .commands import command

FICHIER = Path.home() / "IA-VOCAL-positions.json"


def _lire() -> dict:
    if not FICHIER.exists():
        return {}
    return json.loads(FICHIER.read_text(encoding="utf-8"))


def _ecrire(donnees: dict) -> None:
    FICHIER.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")


def _pyautogui():
    import pyautogui

    return pyautogui


@command(r"^(retiens|enregistre|mémorise|memorise) (cet endroit|cette position|la position|ici|l'endroit)"
         r"( comme| sous le nom| sous)? (?P<nom>.+)$",
         "retiens cet endroit comme <nom>")
def retiens(nom: str) -> str:
    x, y = _pyautogui().position()
    donnees = _lire()
    donnees[nom.strip().lower()] = [x, y]
    _ecrire(donnees)
    return f"J'ai retenu cet endroit comme « {nom.strip()} »."


@command(r"^(déplace|deplace|mets|bouge) (la )?souris (sur|sur la|sur le|vers) (?P<nom>.+)$",
         "déplace la souris sur <nom enregistré>")
def va_a_position(nom: str) -> str:
    cle = nom.strip().lower()
    donnees = _lire()
    if cle not in donnees:
        return (f"Je n'ai pas d'endroit « {nom.strip()} ». Mets la souris dessus et dis "
                f"« retiens cet endroit comme {nom.strip()} ».")
    x, y = donnees[cle]
    _pyautogui().moveTo(x, y, duration=0.3)
    return f"Souris sur {nom.strip()}."
