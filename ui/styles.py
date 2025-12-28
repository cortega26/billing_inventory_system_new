from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

class DesignTokens:
    # Color Palette - DARK MODE
    # Base Scale
    COLOR_BG_BASE = "#1E1E1E"
    COLOR_BG_ALT = "#2D2D2D"
    COLOR_BORDER = "#404040"
    COLOR_TEXT_PRIMARY = "#E0E0E0"
    COLOR_TEXT_SECONDARY = "#B0B0B0"
    COLOR_TEXT_DISABLED = "#707070"

    # Primary Action (Brand)
    COLOR_PRIMARY = "#64B5F6"      # Lighter blue for visibility on dark
    COLOR_PRIMARY_DARK = "#42A5F5"
    COLOR_PRIMARY_LIGHT = "#1565C0" # Darker blue for selection backgrounds

    # Semantics
    COLOR_SUCCESS = "#81C784"
    COLOR_SUCCESS_BG = "#1B5E20"    # Dark green background
    COLOR_ERROR = "#E57373"
    COLOR_ERROR_BG = "#3E2723"      # Dark red background
    COLOR_WARNING = "#FFF176"
    COLOR_WARNING_BG = "#F57F17"

    # Spacing (Px)
    SPACE_XS = "4px"
    SPACE_SM = "8px"
    SPACE_MD = "16px"
    SPACE_LG = "24px"
    
    # Typography
    FONT_FAMILY = "Segoe UI"  # System default fallback

def get_global_stylesheet() -> str:
    """
    Returns the QSS (Qt Style Sheet) for the application.
    Uses DesignTokens to ensure consistency.
    """
    return f"""
    /* Global Reset */
    * {{
        font-family: "{DesignTokens.FONT_FAMILY}", sans-serif;
        color: {DesignTokens.COLOR_TEXT_PRIMARY};
    }}

    QMainWindow, QDialog {{
        background-color: {DesignTokens.COLOR_BG_BASE};
    }}

    /* Inputs */
    QLineEdit, QDateEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {DesignTokens.COLOR_BG_BASE};
        border: 1px solid {DesignTokens.COLOR_BORDER};
        border-radius: 4px;
        padding: 4px 8px; /* Vertical: 4px (approx SPACE_XS), Horizontal: 8px (SPACE_SM) */
        min-height: 22px; /* Target ~30px total height */
        selection-background-color: {DesignTokens.COLOR_PRIMARY_LIGHT};
        selection-color: {DesignTokens.COLOR_TEXT_PRIMARY};
    }}

    QLineEdit:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 2px solid {DesignTokens.COLOR_PRIMARY};
        padding: 3px 7px; /* Adjust padding to prevent size jump from border width change */
    }}
    
    QLineEdit:disabled, QDateEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
        background-color: {DesignTokens.COLOR_BG_ALT};
        color: {DesignTokens.COLOR_TEXT_DISABLED};
    }}

    /* Buttons */
    QPushButton {{
        background-color: {DesignTokens.COLOR_BG_ALT};
        border: 1px solid {DesignTokens.COLOR_BORDER};
        border-radius: 4px;
        padding: 5px 8px;
        min-height: 22px;
    }}

    QPushButton:hover {{
        background-color: #E0E0E0; /* Slightly darker than BG_ALT */
    }}

    QPushButton:pressed {{
        background-color: {DesignTokens.COLOR_BORDER};
    }}

    /* Primary/Success Action Classes */
    QPushButton[class="primary"], QPushButton[class="success"] {{
        background-color: {DesignTokens.COLOR_SUCCESS};
        color: white;
        border: none;
        font-weight: bold;
    }}
    
    QPushButton[class="primary"]:hover, QPushButton[class="success"]:hover {{
        background-color: #388E3C; /* Darker Green */
    }}

    /* Destructive/Error Action Classes */
    QPushButton[class="destructive"], QPushButton[class="error"] {{
        background-color: {DesignTokens.COLOR_ERROR};
        color: white;
        border: none;
        font-weight: bold;
    }}

    QPushButton[class="destructive"]:hover, QPushButton[class="error"]:hover {{
        background-color: #C62828; /* Darker Red */
    }}

    /* Tables */
    QTableWidget {{
        background-color: {DesignTokens.COLOR_BG_BASE};
        gridline-color: {DesignTokens.COLOR_BORDER};
        selection-background-color: {DesignTokens.COLOR_PRIMARY_LIGHT};
        selection-color: {DesignTokens.COLOR_TEXT_PRIMARY};
        font-size: 14px;
    }}

    QHeaderView::section {{
        background-color: {DesignTokens.COLOR_BG_ALT};
        padding: 4px;
        border: 1px solid {DesignTokens.COLOR_BORDER};
        font-weight: bold;
        font-size: 12px;
    }}
    
    /* Tabs */
    QTabWidget::pane {{
        border: 1px solid {DesignTokens.COLOR_BORDER};
        top: -1px;
    }}
    
    QTabBar::tab {{
        background: {DesignTokens.COLOR_BG_ALT};
        border: 1px solid {DesignTokens.COLOR_BORDER};
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    
    QTabBar::tab:selected {{
        background: {DesignTokens.COLOR_BG_BASE};
        border-bottom-color: {DesignTokens.COLOR_BG_BASE};
        color: {DesignTokens.COLOR_PRIMARY};
        font-weight: bold;
    }}

    /* Status Bar */
    QStatusBar {{
        background-color: {DesignTokens.COLOR_BG_ALT};
        color: {DesignTokens.COLOR_TEXT_SECONDARY};
    }}
    """

def apply_theme(app: QApplication):
    """
    Applies the Design System theme to the QApplication instance.
    """
    # 1. Apply QSS
    app.setStyleSheet(get_global_stylesheet())

    # 2. Apply QPalette (Optional fallback for things QSS misses, or system integration)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(DesignTokens.COLOR_BG_BASE))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(DesignTokens.COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(DesignTokens.COLOR_BG_BASE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(DesignTokens.COLOR_BG_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(DesignTokens.COLOR_BG_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(DesignTokens.COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Text, QColor(DesignTokens.COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(DesignTokens.COLOR_BG_ALT))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(DesignTokens.COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Link, QColor(DesignTokens.COLOR_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(DesignTokens.COLOR_PRIMARY_LIGHT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(DesignTokens.COLOR_TEXT_PRIMARY))
    
    app.setPalette(palette)
