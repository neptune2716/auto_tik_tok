import os
import json
from typing import Set, Optional
from config import HISTORY_FILE

class StoryHistory:
    def __init__(self):
        self.used_titles: Set[str] = set()
        self.load_history()

    def load_history(self) -> None:
        """Charge l'historique depuis le fichier JSON."""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.used_titles = set(json.load(f))
            except json.JSONDecodeError:
                self.used_titles = set()

    def save_history(self) -> None:
        """Sauvegarde l'historique dans le fichier JSON."""
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(self.used_titles), f, indent=2)

    def add_story(self, title: str) -> None:
        """Ajoute un titre à l'historique et sauvegarde."""
        self.used_titles.add(title)
        self.save_history()

    def is_story_used(self, title: str) -> bool:
        """Vérifie si une histoire a déjà été utilisée."""
        return title in self.used_titles

    def clear_history(self) -> None:
        """Efface tout l'historique."""
        self.used_titles.clear()
        self.save_history()
