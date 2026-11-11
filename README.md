# IA VOCAL

Assistant vocal Windows avec compréhension, vision et reconnaissance vocale locales.

## Fonctionnement local

- Ollama exécute le modèle `qwen2.5vl:3b) sur le PC.
- Vosk convertit la voix en texte localement (français).
- Les actions sur l'écran sont pilotées par l'agent local.
- Aucune clé API Claude/Anthropic ou service Google de reconnaissance vocale n'est utilisée.

## Première préparation

Au premier lancement, IA VOCAL installe Ollama si nécessaire, puis télécharge le modèle IA et le modèle vocal français. Ces téléchargements initiaux nécessitent Internet. Une fois les fichiers installés, l'inférence et la reconnaissance vocale se font localement.

## Installation développeur

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Le modèle local demande plusieurs Go d'espace disque et de mémoire. Les performances dépendent du matériel.
