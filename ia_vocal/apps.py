"""Lancement d'applications installées sur l'ordinateur, par leur nom."""

from __future__ import annotations

import difflib
import glob
import os
import platform
import shutil
import subprocess
import unicodedata
from pathlib import Path

# Noms dits à l'oral -> nom canonique ou commande Windows
ALIAS = {
    "bloc-notes": "notepad",
    "bloc notes": "notepad",
    "calculatrice": "calc",
    "explorateur": "explorer",
    "gestionnaire des taches": "taskmgr",
    "terminal": "wt",
    "after effect": "after effects",
    "adobe after effect": "after effects",
    "adobe after effects": "after effects",
    "aftereffects": "after effects",
    "ae": "after effects",
}

# Emplacements d'installation courants sous Windows (motif glob)
CHEMINS_WINDOWS = {
    "blender": [r"C:\Program Files\Blender Foundation\Blender *\blender.exe"],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "spotify": [os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")],
    "discord": [os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe")],
    "after effects": [
        r"C:\Program Files\Adobe\Adobe After Effects *\Support Files\AfterFX.exe",
        r"C:\Program Files\Adobe\After Effects *\Support Files\AfterFX.exe",
        r"C:\Program Files (x86)\Adobe\Adobe After Effects *\Support Files\AfterFX.exe",
    ],
}


def _normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return "".join(c.lower() if c.isalnum() else " " for c in texte).strip()


def _correspond_aux_mots(demande: str, libelle: str) -> bool:
    """Accepte les noms enrichis (Adobe/année) et les pluriels simples."""
    mots_demandes = _normaliser(demande).split()
    mots_libelle = _normaliser(libelle).split()
    if not mots_demandes:
        return False
    return all(
        any(mot_libelle == mot or mot_libelle.startswith(mot) for mot_libelle in mots_libelle)
        for mot in mots_demandes
    )


def _trouver_raccourci_windows(nom: str) -> str | None:
    """Cherche le raccourci correspondant dans les menus Démarrer."""
    dossiers = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    cible = _normaliser(nom)
    raccourcis: list[tuple[str, str]] = []
    for dossier in dossiers:
        if not dossier.is_dir():
            continue
        try:
            for chemin in dossier.rglob("*.lnk"):
                raccourcis.append((_normaliser(chemin.stem), str(chemin)))
        except OSError:
            continue

    # Priorité au nom exact, puis aux mots demandés présents dans le nom complet.
    for libelle, chemin in raccourcis:
        if libelle == cible:
            return chemin

    candidats = [
        (libelle, chemin)
        for libelle, chemin in raccourcis
        if _correspond_aux_mots(cible, libelle)
    ]
    if candidats:
        # Le raccourci le plus court évite de choisir une documentation ou un désinstalleur.
        candidats.sort(key=lambda element: len(element[0]))
        return candidats[0][1]

    # Tolérance aux petites erreurs de dictée uniquement pour les noms assez longs.
    if len(cible.replace(" ", "")) >= 5:
        noms = [libelle for libelle, _ in raccourcis if len(libelle.replace(" ", "")) >= 5]
        proche = difflib.get_close_matches(cible, noms, n=1, cutoff=0.90)
        if proche:
            return next(chemin for libelle, chemin in raccourcis if libelle == proche[0])
    return None


def _trouver_windows(nom: str) -> str | None:
    for motif in CHEMINS_WINDOWS.get(nom, []):
        trouves = sorted(glob.glob(motif), reverse=True)
        if trouves:
            if nom == "discord" and Path(trouves[0]).name.lower() == "update.exe":
                break
            return trouves[0]

    raccourci = _trouver_raccourci_windows(nom)
    if raccourci:
        return raccourci
    return shutil.which(nom)


def lancer_application(nom: str) -> str:
    """Lance une application par son nom et retourne un message à l'utilisateur."""
    nom = nom.strip()
    cle = _normaliser(nom)
    nom = ALIAS.get(cle, nom)
    cle = _normaliser(nom)
    systeme = platform.system()

    if systeme == "Windows":
        exe = _trouver_windows(cle)
        if exe is None:
            return f"Je ne trouve pas « {nom} » dans les applications installées ni dans le menu Démarrer."
        try:
            if exe.lower().endswith(".lnk"):
                os.startfile(exe)  # type: ignore[attr-defined]
            else:
                subprocess.Popen([exe], shell=False)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1223:
                return f"Windows a annulé l'ouverture de « {nom} ». Vérifie qu'aucune demande d'autorisation n'a été refusée."
            return f"Impossible de lancer « {nom} » : {exc}"
    elif systeme == "Darwin":
        try:
            subprocess.Popen(["open", "-a", nom])
        except OSError as exc:
            return f"Impossible de lancer « {nom} » : {exc}"
    else:
        exe = shutil.which(nom)
        if exe is None:
            return f"Je ne trouve pas « {nom} » sur cet ordinateur."
        try:
            subprocess.Popen([exe])
        except OSError as exc:
            return f"Impossible de lancer « {nom} » : {exc}"

    return f"J'ouvre {nom}."
