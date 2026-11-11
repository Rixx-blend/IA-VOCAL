"""Prépare Ollama et les modèles locaux nécessaires à IA VOCAL."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from .agent import MODELE as MODELE_VISION
from .ai import MODELE_LOCAL
from .commands import command

URL_INSTALLEUR = "https://ollama.com/download/OllamaSetup.exe"
URL_VOSK = "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip"
API = "http://localhost:11434"
DOSSIER_MODELES = Path.home() / "AppData" / "Local" / "IA-VOCAL"
DOSSIER_VOSK = DOSSIER_MODELES / "vosk-model-small-fr-0.22"
CREATE_NO_WINDOW = 0x08000000
_sortie: Callable[[str], None] = print


def definir_sortie(fonction: Callable[[str], None]) -> None:
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
    for _ in range(45):
        if _api_repond():
            return
        time.sleep(1)
    raise RuntimeError("le service Ollama ne démarre pas")


def _modeles_installes() -> set[str]:
    with urllib.request.urlopen(API + "/api/tags", timeout=8) as rep:
        import json
        modeles = json.loads(rep.read().decode("utf-8")).get("models", [])
    return {m.get("name", "") for m in modeles}


def _telecharger_modele(nom: str, progres: Callable[[str], None]) -> None:
    import json
    progres(f"Téléchargement du modèle local {nom}…")
    corps = json.dumps({"model": nom, "stream": True}).encode("utf-8")
    requete = urllib.request.Request(
        API + "/api/pull", data=corps, method="POST",
        headers={"content-type": "application/json"},
    )
    dernier = -20
    with urllib.request.urlopen(requete, timeout=3600) as rep:
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
                    progres(f"Téléchargement du modèle local : {pourcentage} %")


def _installer_vosk(progres: Callable[[str], None]) -> None:
    if DOSSIER_VOSK.exists():
        return
    DOSSIER_MODELES.mkdir(parents=True, exist_ok=True)
    archive = Path(tempfile.gettempdir()) / "vosk-model-small-fr-0.22.zip"
    progres("Téléchargement du modèle vocal français local…")
    urllib.request.urlretrieve(URL_VOSK, archive)
    progres("Installation du modèle vocal local…")
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(DOSSIER_MODELES)
    archive.unlink(missing_ok=True)


def _precharger_modele(progres: Callable[[str], None]) -> None:
    """Charge le modèle en mémoire au démarrage pour éviter l'attente au premier message."""
    import json

    progres("Démarrage du cerveau local…")
    corps = json.dumps({
        "model": MODELE_LOCAL,
        "prompt": "Réponds simplement OK.",
        "stream": False,
        "keep_alive": -1,
        "options": {"num_predict": 1, "num_ctx": 2048},
    }).encode("utf-8")
    requete = urllib.request.Request(
        API + "/api/generate",
        data=corps,
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(requete, timeout=180) as rep:
        resultat = json.loads(rep.read().decode("utf-8"))
    if resultat.get("error"):
        raise RuntimeError(resultat["error"])


def _telecharger_installeur(progres: Callable[[str], None]) -> Path:
    destination = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
    progres("Téléchargement d'Ollama…")
    urllib.request.urlretrieve(URL_INSTALLEUR, destination)
    return destination


def preparer(progres: Callable[[str], None]) -> str:
    try:
        if _ollama_exe() is None:
            installeur = _telecharger_installeur(progres)
            os.startfile(installeur)  # type: ignore[attr-defined]
            return "Installe Ollama, puis relance IA VOCAL pour terminer la préparation locale."
        if not _api_repond():
            progres("Démarrage du moteur local Ollama…")
            _demarrer_serveur()
        modeles = _modeles_installes()
        for nom in sorted({MODELE_LOCAL, MODELE_VISION}):
            if nom not in modeles and f"{nom}:latest" not in modeles:
                _telecharger_modele(nom, progres)
        _installer_vosk(progres)
        _precharger_modele(progres)
        return "IA VOCAL est prête : le moteur local est chargé et l'écoute continue est disponible."
    except Exception as exc:
        return f"Préparation locale impossible : {exc}"


def lancer_en_arriere_plan() -> None:
    def tache() -> None:
        _sortie(preparer(_sortie))
    threading.Thread(target=tache, daemon=True).start()


@command(r"^(prépare|prepare|installe) (l')?assistant local$", "prépare l'assistant local")
def prepare_assistant() -> str:
    lancer_en_arriere_plan()
    return "Je prépare les modèles locaux. Le premier téléchargement peut prendre du temps."
