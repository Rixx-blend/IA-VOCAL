"""Lancement d'applications avec tolérance aux erreurs de dictée et de frappe."""

from __future__ import annotations

import difflib
import glob
import os
import platform
import shutil
import subprocess
import unicodedata
from pathlib import Path

from .commands import Pas_trouve

# Synonymes fréquents et noms alternatifs. La recherche floue générale
# prend ensuite le relais pour les autres applications.
ALIAS = {
    "bloc-notes": "notepad",
    "bloc notes": "notepad",
    "notepad": "notepad",
    "calculatrice": "calc",
    "explorateur": "explorer",
    "gestionnaire des taches": "taskmgr",
    "terminal": "wt",
    "after effect": "after effects",
    "adobe after effect": "after effects",
    "adobe after effects": "after effects",
    "aftereffects": "after effects",
    "photoshop": "photoshop",
    "premier pro": "premiere pro",
}

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
    return " ".join("".join(c.lower() if c.isalnum() else " " for c in texte).split())


def _score_nom(demande: str, libelle: str) -> float:
    """Score de similarité tolérant aux fautes, mots manquants et suffixes."""
    demande = _normaliser(demande)
    libelle = _normaliser(libelle)
    if not demande or not libelle:
        return 0.0
    if demande == libelle:
        return 1.0
    if demande in libelle:
        return 0.97

    mots_demande = demande.split()
    mots_libelle = libelle.split()
    scores = []
    for mot in mots_demande:
        meilleur = max(
            (difflib.SequenceMatcher(None, mot, candidat).ratio()
             for candidat in mots_libelle),
            default=0.0,
        )
        # Une petite faute de reconnaissance vocale ne doit pas éliminer le mot.
        scores.append(meilleur)
    couverture = sum(scores) / len(scores)
    ordre = difflib.SequenceMatcher(None, demande, libelle).ratio()
    # La couverture des mots est prioritaire : « photoshop » doit trouver
    # « Adobe Photoshop 2025 », sans confondre avec une autre application.
    return 0.82 * couverture + 0.18 * ordre


def _raccourcis_windows() -> list[tuple[str, str]]:
    dossiers = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    resultats: list[tuple[str, str]] = []
    vus: set[str] = set()
    for dossier in dossiers:
        if not dossier.is_dir():
            continue
        try:
            for chemin in dossier.rglob("*.lnk"):
                cle = str(chemin).casefold()
                if cle not in vus:
                    vus.add(cle)
                    resultats.append((chemin.stem, str(chemin)))
        except OSError:
            continue
    return resultats


def _trouver_raccourci_windows(nom: str) -> str | None:
    raccourcis = _raccourcis_windows()
    if not raccourcis:
        return None

    cible = _normaliser(nom)
    # Toujours privilégier une correspondance exacte.
    for libelle, chemin in raccourcis:
        if _normaliser(libelle) == cible:
            return chemin

    classes = sorted(
        ((_score_nom(cible, libelle), len(_normaliser(libelle)), libelle, chemin)
         for libelle, chemin in raccourcis),
        key=lambda element: (element[0], -element[1]),
        reverse=True,
    )
    meilleur = classes[0]
    second_score = classes[1][0] if len(classes) > 1 else 0.0

    # Seuil conservateur : ne pas ouvrir une application sans rapport.
    # En cas de deux candidats proches, on demande une précision au lieu de deviner.
    if meilleur[0] < 0.76:
        return None
    if second_score >= meilleur[0] - 0.045:
        return None
    return meilleur[3]


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
    """Lance l'application la plus probable sans exiger son nom exact."""
    nom = nom.strip()
    cle = _normaliser(nom)
    nom_recherche = ALIAS.get(cle, cle)
    systeme = platform.system()

    if systeme == "Windows":
        exe = _trouver_windows(nom_recherche)
        if exe is None:
            # Pas de correspondance fiable : l'assistant local prend le relais
            raise Pas_trouve(nom)
        try:
            if exe.lower().endswith(".lnk"):
                os.startfile(exe)  # type: ignore[attr-defined]
            else:
                subprocess.Popen([exe], shell=False)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1223:
                return f"Windows a annulé l'ouverture de « {nom} ». Vérifie l'autorisation demandée."
            return f"Impossible de lancer « {nom} » : {exc}"
    elif systeme == "Darwin":
        try:
            subprocess.Popen(["open", "-a", nom])
        except OSError as exc:
            return f"Impossible de lancer « {nom} » : {exc}"
    else:
        exe = shutil.which(nom_recherche)
        if exe is None:
            raise Pas_trouve(nom)
        try:
            subprocess.Popen([exe])
        except OSError as exc:
            return f"Impossible de lancer « {nom} » : {exc}"

    return f"J'ouvre {nom}."
