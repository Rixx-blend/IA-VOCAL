"""Reconnaissance vocale : micro -> texte (français).

L'écoute tourne dans un thread séparé pour ne pas bloquer la fenêtre.
Le résultat est déposé dans une file, que l'overlay lit régulièrement.
"""

from __future__ import annotations

import queue
import threading

import speech_recognition as sr

LANGUE = "fr-FR"


class Ecoute:
    def __init__(self) -> None:
        # Chaque élément : (genre, texte) où genre vaut "phrase" ou "info"
        self.resultats: queue.Queue[tuple[str, str]] = queue.Queue()
        self._verrou = threading.Lock()

    def demarrer(self) -> bool:
        """Lance une écoute. Retourne False si une écoute est déjà en cours."""
        if not self._verrou.acquire(blocking=False):
            return False
        threading.Thread(target=self._ecouter, daemon=True).start()
        return True

    def _ecouter(self) -> None:
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            texte = recognizer.recognize_google(audio, language=LANGUE)
            self.resultats.put(("phrase", texte))
        except sr.WaitTimeoutError:
            self.resultats.put(("info", "Je n'ai rien entendu."))
        except sr.UnknownValueError:
            self.resultats.put(("info", "Je n'ai pas compris."))
        except sr.RequestError:
            self.resultats.put(
                ("info", "Reconnaissance indisponible : vérifie ta connexion internet.")
            )
        except Exception as exc:  # micro absent, PyAudio manquant, etc.
            self.resultats.put(("info", f"Micro indisponible : {exc}"))
        finally:
            self._verrou.release()
