from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from config import DEFAULT_ACTIVE_BUSINESS, config
from utils.system.logger import logger


class BusinessSelectorDialog(QDialog):
    """Startup dialog to choose which business to operate with.

    Only shown when more than one business is configured. Selection is
    persisted only when the user checks "Recordar selección"; the app must
    restart to switch businesses.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selección de Negocio")
        self.setModal(True)
        self.resize(420, 300)
        self.selected_business_id: str | None = None
        self.remember_selection: bool = True
        self.setup_ui()

    @staticmethod
    def should_show() -> bool:
        """The selector is only meaningful when more than one business exists."""
        return len(config.get_businesses()) > 1

    def setup_ui(self):
        self.layout: QVBoxLayout = QVBoxLayout(self)
        self.layout.setSpacing(12)

        header_label = QLabel("Seleccione el negocio con el que operará")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.layout.addWidget(header_label)

        hint_label = QLabel(
            "El cambio de negocio se aplica al reiniciar la aplicación."
        )
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(hint_label)

        businesses = config.get_businesses()
        active_id = config.get("active_business", DEFAULT_ACTIVE_BUSINESS)
        known_ids = [business["id"] for business in businesses]
        if active_id not in known_ids:
            active_id = known_ids[0]

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.radio_buttons: dict[str, QRadioButton] = {}
        for business in businesses:
            radio = QRadioButton(f"{business['name']}  ({business['db_filename']})")
            self.button_group.addButton(radio)
            self.radio_buttons[business["id"]] = radio
            if business["id"] == active_id:
                radio.setChecked(True)
            self.layout.addWidget(radio)

        self.remember_checkbox = QCheckBox("Recordar selección")
        self.remember_checkbox.setChecked(True)
        self.layout.addWidget(self.remember_checkbox)

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

    def handle_accept(self):
        checked = [
            business_id
            for business_id, radio in self.radio_buttons.items()
            if radio.isChecked()
        ]
        if not checked:
            return
        self.selected_business_id = checked[0]
        self.remember_selection = self.remember_checkbox.isChecked()
        config.set_active_business(
            self.selected_business_id, persist=self.remember_selection
        )
        logger.info(
            f"Business selected: {self.selected_business_id} "
            f"(remember={self.remember_selection})"
        )
        self.accept()
