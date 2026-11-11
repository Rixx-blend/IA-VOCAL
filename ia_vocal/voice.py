"""Reconnaissance vocale française entièrement locale avec Vosk."""

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
        self._verrou = threading.Lock()
        self._modele = None

    def demarrer(self) -> bool:
        if not self._verrou.acquire(blocking=False):
            return False
        threading.Thread(target=self._ecouter, daemon=True).start()
        return True

    def _charger_modele(self):
        if self._modele is not None:
            return self._modele
        if not MODELE_VOSK.exists():
            raise RuntimeError(
                "Le modèle vocal français local n'est pas installé. "
                "Laisse la préparation d'IA VOCAL se terminer puis relance l'écoute."
            )
        from vosk import Model
        self._modele = Model(str(MODELE_VOSK))
        return self._modele

    def _ecouter(self) -> None:
        try:
            from vosk import KaldiRecognizer

            modele = self._charger_modele()
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.4)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=12)
            donnees = audio.get_raw_data(convert_rate=16000, convert_width=2)
            moteur = KaldiRecognizer(modele, 16000)
            moteur.AcceptWaveform(donnees)
            resultat = json.loads(moteur.FinalResult())
            texte = resultat.get("text", "").strip()
            if texte:
                self.resultats.put(("phrase", texte))
            else:
                self.resultats.put(("info", "Je n'ai pas compris."))
        except sr.WaitTimeoutError:
            self.resultats.put(("info", "Je n'ai rien entendu."))
        except Exception as exc:
            self.resultats.put(("info", f"Micro ou reconnaissance locale indisponible : {exc}"))
        finally:
            self._verrou.release()
