"""Reconnaissance vocale française locale et continue avec Vosk."""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path

import speech_recognition as sr

LANGUE = "fr-FR"
MODELE_VOSK = Path.home() / "AppData" / "Local" / "IA-VOCAL" / "vosk-model-small-fr-0.22"


class Ecoute:
    def __init__(self) -> None:
        self.resultats: queue.Queue[tuple[str, str]] = queue.Queue()
        self._actif = threading.Event()
        self._silencieux = threading.Event()
        self._modele = None
        self._thread = None

    @property
    def active(self) -> bool:
        return self._actif.is_set()

    def demarrer(self) -> bool:
        if self._actif.is_set():
            return True
        self._actif.set()
        self._thread = threading.Thread(target=self._ecouter, daemon=True)
        self._thread.start()
        return True

    def arreter(self) -> None:
        self._actif.clear()

    def suspendre_sortie_vocale(self, suspendre: bool) -> None:
        if suspendre:
            self._silencieux.set()
        else:
            self._silencieux.clear()

    def _charger_modele(self):
        if self._modele is not None:
            return self._modele
        if not MODELE_VOSK.exists():
            raise RuntimeError(
                "Le modèle vocal français local n'est pas installé. "
                "Attends la fin de la préparation puis relance l'écoute."
            )
        from vosk import Model
        self._modele = Model(str(MODELE_VOSK))
        return self._modele

    def _ecouter(self) -> None:
        try:
            from vosk import KaldiRecognizer

            modele = self._charger_modele()
            recognizer = sr.Recognizer()
            recognizer.dynamic_energy_threshold = True
            with sr.Microphone(sample_rate=16000) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.35)
                while self._actif.is_set():
                    try:
                        audio = recognizer.listen(source, timeout=1, phrase_time_limit=8)
                    except sr.WaitTimeoutError:
                        continue

                    if not self._actif.is_set() or self._silencieux.is_set():
                        continue

                    moteur = KaldiRecognizer(modele, 16000)
                    donnees = audio.get_raw_data(convert_rate=16000, convert_width=2)
                    moteur.AcceptWaveform(donnees)
                    texte = json.loads(moteur.FinalResult()).get("text", "").strip()
                    if texte and self._actif.is_set() and not self._silencieux.is_set():
                        self.resultats.put(("phrase", texte))
        except Exception as exc:
            if self._actif.is_set():
                self.resultats.put(("info", f"Micro ou reconnaissance locale indisponible : {exc}"))
        finally:
            self._actif.clear()
