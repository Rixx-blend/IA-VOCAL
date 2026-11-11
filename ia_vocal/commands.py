"""Moteur de commandes : associe un motif (regex) à une fonction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

Handler = Callable[..., Optional[str]]


@dataclass(frozen=True)
class Command:
    pattern: re.Pattern
    handler: Handler
    description: str


_REGISTRY: list[Command] = []


def command(pattern: str, description: str = "") -> Callable[[Handler], Handler]:
    """Décorateur qui enregistre une commande.

    Le motif est une regex insensible à la casse appliquée à la phrase entière.
    Les groupes nommés du motif sont passés en arguments à la fonction.
    """

    compiled = re.compile(pattern, re.IGNORECASE)

    def decorator(func: Handler) -> Handler:
        _REGISTRY.append(Command(compiled, func, description or func.__doc__ or ""))
        return func

    return decorator


def dispatch(text: str) -> Optional[str]:
    """Exécute la première commande qui correspond à la phrase.

    Retourne None si aucune commande ne correspond, pour laisser la main à l'assistant.
    """
    phrase = text.strip()
    if not phrase:
        return ""

    for cmd in _REGISTRY:
        match = cmd.pattern.match(phrase)
        if match:
            try:
                result = cmd.handler(**match.groupdict())
            except Exception as exc:  # on ne plante pas l'overlay
                return f"Erreur : {exc}"
            return result or "C'est fait."

    return None


def reconnait(text: str) -> bool:
    """Vrai si une commande connue correspond à la phrase (sans l'exécuter)."""
    phrase = text.strip()
    return any(cmd.pattern.match(phrase) for cmd in _REGISTRY)


def list_commands() -> list[str]:
    return [c.description for c in _REGISTRY if c.description]
