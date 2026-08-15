import hashlib
import hmac
import os
from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from config import config
from utils.system.logger import logger

PBKDF2_ITERATIONS = 600_000


def hash_pin(pin: str, salt: bytes | None = None) -> str:
    """Hash the PIN with PBKDF2-SHA256 and a fresh per-install salt."""
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def is_legacy_hash(stored: str) -> bool:
    """Detect the pre-PBKDF2 single-round SHA-256 format."""
    return (
        len(stored) == 64
        and all(c in "0123456789abcdef" for c in stored.lower())
    )


def verify_pin(stored: str, pin: str) -> bool:
    """Verify a PIN against a stored pbkdf2$iterations$salt$digest hash."""
    if is_legacy_hash(stored):
        return False
    try:
        _, iterations_s, salt_hex, digest_hex = stored.split("$")
        iterations = int(iterations_s)
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac(
            "sha256", pin.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError, AttributeError):
        return False


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Autenticación de Acceso")
        self.setModal(True)
        self.resize(320, 200)
        self.attempts = int(config.get("pin_failed_attempts", 0) or 0)
        self.max_attempts = 5
        self.lockout_window = timedelta(minutes=5)
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(12)

        # Header label
        self.header_label = QLabel()
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.layout.addWidget(self.header_label)

        # Form fields layout
        self.form_layout = QVBoxLayout()

        self.pin_hash = config.get("pin_hash", "")
        if not self.pin_hash:
            self.header_label.setText("Establecer PIN de Acceso")

            # Setup fields for first-time configuration
            self.pin_label = QLabel("Nuevo PIN (4-6 dígitos):")
            self.pin_input = QLineEdit()
            self.pin_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.pin_input.setMaxLength(6)
            self.pin_input.setPlaceholderText("Ingrese PIN de números")

            self.confirm_label = QLabel("Confirmar PIN:")
            self.confirm_input = QLineEdit()
            self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_input.setMaxLength(6)
            self.confirm_input.setPlaceholderText("Confirme su PIN")

            self.form_layout.addWidget(self.pin_label)
            self.form_layout.addWidget(self.pin_input)
            self.form_layout.addWidget(self.confirm_label)
            self.form_layout.addWidget(self.confirm_input)

            # Enable accept only when fields are valid
            self.pin_input.textChanged.connect(self.validate_setup_inputs)
            self.confirm_input.textChanged.connect(self.validate_setup_inputs)
        else:
            self.header_label.setText("Ingresar PIN de Acceso")

            # Setup field for login
            self.pin_label = QLabel("PIN:")
            self.pin_input = QLineEdit()
            self.pin_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.pin_input.setMaxLength(6)
            self.pin_input.setPlaceholderText("Ingrese su PIN")

            self.form_layout.addWidget(self.pin_label)
            self.form_layout.addWidget(self.pin_input)

            self.pin_input.textChanged.connect(self.validate_login_inputs)

        self.layout.addLayout(self.form_layout)

        # Message Label for errors
        self.msg_label = QLabel()
        self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.msg_label.setStyleSheet("color: #E57373; font-weight: bold;")
        self.layout.addWidget(self.msg_label)

        # Buttons layout
        btn_layout = QHBoxLayout()
        self.btn_accept = QPushButton("Aceptar")
        self.btn_accept.setProperty("class", "success")
        self.btn_accept.clicked.connect(self.handle_accept)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setProperty("class", "destructive")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_accept)
        btn_layout.addWidget(self.btn_cancel)
        self.layout.addLayout(btn_layout)

        # Set initial button states
        self.btn_accept.setEnabled(False)

    def validate_setup_inputs(self):
        pin = self.pin_input.text()
        confirm = self.confirm_input.text()

        # Validations:
        # 1. Digits only
        # 2. Length 4 to 6
        # 3. Match
        is_valid_pin = pin.isdigit() and 4 <= len(pin) <= 6
        matches = pin == confirm

        if len(pin) > 0 and not pin.isdigit():
            self.msg_label.setText("El PIN debe contener solo números")
        elif len(pin) > 0 and (len(pin) < 4 or len(pin) > 6):
            self.msg_label.setText("El PIN debe tener entre 4 y 6 dígitos")
        elif len(confirm) > 0 and not matches:
            self.msg_label.setText("Los PINs no coinciden")
        else:
            self.msg_label.clear()

        self.btn_accept.setEnabled(is_valid_pin and matches)

    def validate_login_inputs(self):
        pin = self.pin_input.text()
        is_valid = pin.isdigit() and 4 <= len(pin) <= 6
        if len(pin) > 0:
            if not pin.isdigit():
                self.msg_label.setText("El PIN debe contener solo números")
            else:
                self.msg_label.clear()
        self.btn_accept.setEnabled(is_valid)

    def handle_accept(self):
        if not self.pin_hash:
            # First time setup
            pin = self.pin_input.text()
            hashed = hash_pin(pin)
            try:
                config.set("pin_hash", hashed)
                config.save()
                logger.info("New PIN configured successfully")
                self.accept()
            except Exception as e:
                logger.error(f"Failed to save new PIN: {e}")
                self.msg_label.setText("Error al guardar el PIN")
        else:
            # Login validation
            pin = self.pin_input.text()
            stored = self.pin_hash
            locked_until_raw = config.get("pin_locked_until", "")
            if locked_until_raw:
                try:
                    locked_until = datetime.fromisoformat(locked_until_raw)
                except ValueError:
                    locked_until = None
                if locked_until is not None and locked_until > datetime.now():
                    remaining = locked_until - datetime.now()
                    seconds = int(remaining.total_seconds())
                    minutes, seconds = divmod(seconds, 60)
                    logger.warning("PIN login blocked by persistent lockout")
                    self.msg_label.setText(
                        "Acceso bloqueado. Intente nuevamente en "
                        f"{minutes} min {seconds} s"
                    )
                    self.reject()
                    return
            if is_legacy_hash(stored):
                logger.warning(
                    "Legacy PIN hash detected; operator must re-set the PIN"
                )
                self.msg_label.setText(
                    "El PIN usa el formato antiguo. Elimine la clave pin_hash de "
                    "~/.config/billing-inventory/app_config.json y reinicie."
                )
                self.reject()
                return
            if verify_pin(stored, pin):
                logger.info("PIN authentication successful")
                config.set("pin_failed_attempts", 0)
                config.set("pin_locked_until", "")
                config.save()
                self.accept()
            else:
                self.attempts += 1
                config.set("pin_failed_attempts", self.attempts)
                remaining = self.max_attempts - self.attempts
                logger.warning(
                    f"Failed PIN login attempt {self.attempts}/{self.max_attempts}"
                )

                if self.attempts >= self.max_attempts:
                    config.set(
                        "pin_locked_until",
                        (datetime.now() + self.lockout_window).isoformat(),
                    )
                    config.save()
                    QMessageBox.critical(
                        self,
                        "Acceso Bloqueado",
                        "Demasiados intentos fallidos. La aplicación se cerrará.",
                    )
                    self.reject()
                else:
                    self.msg_label.setText(
                        f"PIN incorrecto. Intentos restantes: {remaining}"
                    )
                    self.pin_input.clear()
                    self.pin_input.setFocus()
