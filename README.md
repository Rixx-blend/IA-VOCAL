# IA VOCAL

Un petit overlay toujours au-dessus de l'écran qui reçoit des ordres (texte ou voix) et exécute des tâches.

Exemples de commandes :
- `ouvre https://example.com`
- `lance une musique`
- `minuteur 10 minutes`
- `heure`

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python -m ia_vocal
```

Tkinter est fourni avec Python sur Windows et macOS. Sur Linux : `sudo apt install python3-tk`.

## Structure

- `ia_vocal/overlay.py` : fenêtre overlay (Tkinter)
- `ia_vocal/commands.py` : moteur de commandes (chaque commande est une fonction enregistrée)
- `ia_vocal/actions.py` : les actions concrètes (ouvrir, musique, minuteur, ...)
- `ia_vocal/__main__.py` : point d'entrée

## Ajouter une commande

Dans `actions.py`, décorer une fonction avec `@command(motif)` :

```python
@command(r"^ouvre (?P<url>\S+)$")
def ouvre(url: str) -> str:
    webbrowser.open(url)
    return f"J'ouvre {url}"
```

## Prochaines étapes

- Reconnaissance vocale (micro -> texte)
- Synthèse vocale pour les réponses
- Raccourci global pour afficher / masquer l'overlay
