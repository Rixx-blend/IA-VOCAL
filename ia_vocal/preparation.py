"""Préparation automatique de l'assistant local : Ollama puis le modèle de vision.

Étapes : installer Ollama si absent (l'installeur s'ouvre), démarrer le service,
télécharger le modèle si absent. L'avancement est envoyé à l'overlay.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable

from .agent import MODELE
from .commands import command

URL_INSTALLEUR = "https://ollama.com/download/OllamaSetup.exe"
API = "http://localhost:11434"
CREATE_NO_WINDOW = 0x08000000  # pas de fenêtre console sous Windows

_sortie: Callable[[str], None] = print


def definir_sortie(fonction: Callable[[str], None]) -> None:
    """Indique où envoyer les messages d'avancement (l'overlay)."""
    global _sortie
    _sortie = fonction


def _ollama_exe() -> str | None:
    trouve = shutil.which("ollama")
    if trouve:
        return trouve
    candidat = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return str(candidat) if candidat.exists() else None


def _api_repond() -> bool:
    try:
        with urllib.request.urlopen(API + "/api/tags", timeout=3):
            return True
    except Exception:
        return False


def _demarrer_serveur() -> None:
    exe = _ollama_exe()
    if exe is None:
        raise RuntimeError("Ollama n'est pas installé")
    options = {"creationflags": CREATE_NO_WINDOW} if os.name == "nt" else {}
    subprocess.Popen([exe, "serve"], **options)
    for _ in range(30):
        if _api_repond():
            return
        time.sleep(1)
    raise RuntimeError("le service Ollama ne démarre pas")


def _modele_installe() -> bool:
    with urllib.request.urlopen(API + "/api/tags", timeout=5) as rep:
        modeles = json.loads(rep.read().decode("utf-8")).get("models", [])
    return any(m.get("name", "") == MODELE for m in modeles)


def _telecharger_modele(progres: Callable[[str], None]) -> None:
    corps = json.dumps({"model": MODELE, "stream": True}).encode("utf-8")
    requete = urllib.request.Request(
        API + "/api/pull", data=corps, method="POST",
        headers={"content-type": "application/json"},
    )
    dernier = -20
    with urllib.request.urlopen(requete) as rep:
        for ligne in rep:
            if not ligne.strip():
                continue
            etat = json.loads(ligne.decode("utf-8"))
            if "error" in etat:
                raise RuntimeError(etat["error"])
            total, fait = etat.get("total"), etat.get("completed")
            if total and fait is not None:
                pourcentage = int(fait * 100 / total)
                if pourcentage >= dernier + 20:
                    dernier = pourcentage
                    progres(f"Téléchargement du modèle : {pourcentage} %")


def _telecharger_installeur(progres: Callable[[str], None]) -> Path:
    destination = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
    progres("Téléchargement d'Ollama…")
    urllib.request.urlretrieve(URL_INSTALLEUR, destination)
    return destination


def preparer(progres: Callable[[str], None]) -> str:
    """Prépare tout ce qui manque et retourne un message final."""
    try:
        if _ollama_exe() is None:
            installeur = _telecharger_installeur(progres)
            os.startfile(installeur)  # type: ignore[attr-defined]
            return ("Installe Ollama dans la fenêtre qui vient de s'ouvrir, "
                    "puis dis « prépare l'assistant local ».")
        if not _api_repond():
            progres("Démarrage d'Ollama…")
            _demarrer_serveur()
        if not _modele_installe():
            _telecharger_modele(progres)
        return "L'assistant local est prêt."
    except Exception as exc:
        return f"Préparation de l'assistant impossible : {exc}"


def lancer_en_arriere_plan() -> None:
    def tache() -> None:
        _sortie(preparer(_sortie))

    threading.Thread(target=tache, daemon=True).start()


@command(r"^(prépare|prepare|installe) (l')?assistant local$", "prépare l'assistant local")
def prepare_assistant() -> str:
    lancer_en_arriere_plan()
    return "Je prépare l'assistant local, je te tiens au courant."
