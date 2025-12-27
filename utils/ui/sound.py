import os
from typing import Protocol

from utils.system.logger import logger


class SoundPlayer(Protocol):
    """Protocol defining the interface for sound players."""

    def play(self) -> None: ...


class DummySound:
    """A silent implementation for when sound can't be played."""

    def play(self) -> None:
        """Dummy play method that does nothing."""
        pass


class SoundEffect:
    """A wrapper class for sound effects that gracefully falls back to silent mode."""

    def __init__(self, sound_file: str):
        self._player: SoundPlayer = self._create_player(sound_file)

    def _create_player(self, sound_file: str) -> SoundPlayer:
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect

            player = QSoundEffect()
            file_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "ui", "resources", sound_file
            )

            if os.path.exists(file_path):
                player.setSource(QUrl.fromLocalFile(file_path))
                player.setVolume(0.5)
                # Test if sound can be loaded
                if player.status() != QSoundEffect.Status.Error:
                    logger.info(f"Sound system initialized successfully: {file_path}")
                    return player

            logger.warning(f"Sound file not found or couldn't be loaded: {file_path}")
            return DummySound()

        except Exception as e:
            logger.info(
                f"Sound system not available ({str(e)}), running in silent mode"
            )
            return DummySound()

    def play(self) -> None:
        """Play the sound effect, silently failing if it can't be played."""
        try:
            self._player.play()
        except Exception as e:
            logger.debug(f"Could not play sound: {str(e)}")
