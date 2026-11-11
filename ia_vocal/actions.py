"""Actions concrètes exposées à l'utilisateur.

Pour ajouter une commande, écrire une fonction décorée par @command.
Les groupes nommés de la regex deviennent des arguments de la fonction.
"""

from __future__ import annotations

import datetime as _dt
import platform
import subprocess
import threading
import webbrowser

from .apps import lancer_application
from .commands import command


def _est_un_site(cible: str) -> bool:
    return cible.startswith(("http://", "https://", "www.")) or (
        "." in cible and " " not in cible
    )


@command(r"^ouvre (?P<cible>.+)$", "ouvre <site ou application>")
def ouvre(cible: str) -> str:
    cible = cible.strip()
    if _est_un_site(cible):
        url = cible if cible.startswith(("http://", "https://")) else f"https://{cible}"
        webbrowser.open(url)
        return f"J'ouvre {url}"
    return lancer_application(cible)


@command(r"^lance une musique$", "lance une musique")
def lance_musique() -> str:
    system = platform.system()
    if system == "Windows":
        # Ouvre le lecteur par défaut ; à adapter à votre service de streaming
        subprocess.Popen(["cmd", "/c", "start", "spotify:"], shell=False)
    elif system == "Darwin":
        subprocess.Popen(["open", "-a", "Music"])
    else:
        subprocess.Popen(["xdg-open", "https://open.spotify.com"])
    return "Je lance la musique."


@command(r"^lance (?P<cible>.+)$", "lance <application>")
def lance(cible: str) -> str:
    return lancer_application(cible)


@command(r"^minuteur (?P<duree>\d+)\s*(?P<unite>secondes?|minutes?|heures?)$",
         "minuteur <nombre> <secondes|minutes|heures>")
def minuteur(duree: str, unite: str) -> str:
    n = int(duree)
    unite = unite.lower()
    if unite.startswith("seconde"):
        secondes = n
    elif unite.startswith("minute"):
        secondes = n * 60
    else:
        secondes = n * 3600

    def alerte() -> None:
        print(f"[IA VOCAL] Minuteur de {duree} {unite} terminé.")

    timer = threading.Timer(secondes, alerte)
    timer.daemon = True  # ne bloque pas la fermeture de l'application
    timer.start()
    return f"Minuteur lancé pour {n} {unite}."


@command(r"^(quelle heure est-il|heure)\??$", "heure")
def heure() -> str:
    return f"Il est {_dt.datetime.now().strftime('%H:%M')}."


@command(r"^aide$", "aide")
def aide() -> str:
    from .commands import list_commands

    return "Commandes : " + " ; ".join(list_commands())
