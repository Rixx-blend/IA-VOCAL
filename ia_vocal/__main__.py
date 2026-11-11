"""Point d'entrée : python -m ia_vocal"""

from .overlay import Overlay


def main() -> None:
    Overlay().run()


if __name__ == "__main__":
    main()
