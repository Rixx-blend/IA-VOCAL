"""Icône dans la zone de notification Windows (à côté de l'horloge).

Les clics du menu ne touchent pas directement la fenêtre : ils déposent
une commande dans une file, lue par l'overlay dans la boucle Tkinter.
"""

from __future__ import annotations

import queue
import threading

import pystray
from PIL import Image, ImageDraw

BLEU = (158, 203, 255, 255)
FOND = (30, 30, 36, 255)


def _image_icone() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    dessin = ImageDraw.Draw(img)
    dessin.ellipse((4, 4, 60, 60), fill=FOND, outline=BLEU, width=4)
    dessin.ellipse((24, 24, 40, 40), fill=BLEU)  # point central
    return img


class IconeZone:
    def __init__(self, commandes: queue.Queue) -> None:
        menu = pystray.Menu(
            pystray.MenuItem(
                "Afficher / masquer",
                lambda _icon, _item: commandes.put("basculer"),
                default=True,  # clic gauche
            ),
            pystray.MenuItem(
                "Quitter",
                lambda _icon, _item: commandes.put("quitter"),
            ),
        )
        self._icon = pystray.Icon("IA VOCAL", _image_icone(), "IA VOCAL", menu)

    def demarrer(self) -> None:
        threading.Thread(target=self._icon.run, daemon=True).start()

    def arreter(self) -> None:
        self._icon.stop()
