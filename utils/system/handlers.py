import contextlib
import logging.handlers
import os


class OwnerOnlyRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that keeps log files owner-only (0600) across rotations."""

    def doRollover(self) -> None:
        super().doRollover()
        with contextlib.suppress(OSError):
            os.chmod(self.baseFilename, 0o600)
