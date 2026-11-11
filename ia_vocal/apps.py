"""Lancement d'applications installées sur l'ordinateur, par leur nom."""

from __future__ import annotations

import glob
import os
import platform
import shutil
import subprocess

# Noms dits à l'oral -> nom réel de l'application ou de la commande
ALIAS = {
    "bloc-notes": "notepad",
    "calculatrice": "calc",
    "explorateur": "explorer",
}

# Emplacements d'installation courants sous Windows (motif glob)
CHEMINS_WINDOWS = {
    "blender": [r"C:\Program Files\Blender Foundation\Blender *\blender.exe"],
    "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
    "spotify": [os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")],
}


def _trouver_windows(nom: str) -> str | None:
    for motif in CHEMINS_WINDOWS.get(nom, []):
        trouves = sorted(glob.glob(motif), reverse=True)  # version la plus récente
        if trouves:
            return trouves[0]
    return shutil.which(nom)


def lancer_application(nom: str) -> str:
    """Lance une application par son nom et retourne un message pour l'utilisateur."""
    nom = nom.strip().lower()
    nom = ALIAS.get(nom, nom)
    systeme = platform.system()

    if systeme == "Windows":
        exe = _trouver_windows(nom)
        if exe is None:
            return f"Je ne trouve pas « {nom} » sur cet ordinateur."
        subprocess.Popen([exe])
    elif systeme == "Darwin":
        subprocess.Popen(["open", "-a", nom.title()])
    else:
        exe = shutil.which(nom)
        if exe is None:
            return f"Je ne trouve pas « {nom} » sur cet ordinateur."
        subprocess.Popen([exe])

    return f"J'ouvre {nom}."
