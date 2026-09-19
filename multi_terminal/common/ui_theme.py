from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor, QFont
from PySide6.QtCore import Qt

# Rockwell Automation / Industrial UI Theme Tokens
COLOR_BG_DARK      = "#1A1A1A"
COLOR_BG_LIGHT     = "#2D2D2D"
COLOR_ACCENT_RED   = "#E11B22"
COLOR_ACCENT_GREEN = "#00FF00"
COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_DIM     = "#AAAAAA"
COLOR_BORDER       = "#3D3D3D"

INDUSTRIAL_STYLE = f"""
QMainWindow {{
    background-color: {COLOR_BG_DARK};
}}

QGroupBox {{
    border: 2px solid {COLOR_BORDER};
    border-radius: 6px;
    margin-top: 1.5em;
    font-weight: bold;
    color: {COLOR_ACCENT_RED};
    background-color: {COLOR_BG_DARK};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px 0 5px;
}}

QLabel {{
    color: {COLOR_TEXT_PRIMARY};
    font-family: 'Helvetica Neue', Arial;
    font-size: 12px;
}}

QLineEdit, QTextEdit, QComboBox {{
    background-color: #0D0D0D;
    color: {COLOR_ACCENT_GREEN};
    border: 1px solid {COLOR_BORDER};
    border-radius: 3px;
    padding: 2px 5px;
    font-family: Menlo, Monaco, monospace;
    font-size: 12px;
}}

QPushButton {{
    background-color: {COLOR_BG_LIGHT};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 4px 12px;
    font-family: 'Helvetica Neue', Arial;
    font-weight: bold;
    font-size: 12px;
}}

QPushButton:hover {{
    background-color: #3D3D3D;
    border-color: {COLOR_ACCENT_RED};
}}

QPushButton:pressed {{
    background-color: {COLOR_ACCENT_RED};
}}

QSlider::groove:horizontal {{
    border: 1px solid {COLOR_BORDER};
    height: 6px;
    background: #111111;
    margin: 2px 0;
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {COLOR_ACCENT_RED};
    border: 1px solid {COLOR_BG_DARK};
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
}}

QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    background-color: {COLOR_BG_DARK};
}}

QTabBar::tab {{
    background: {COLOR_BG_LIGHT};
    color: {COLOR_TEXT_DIM};
    padding: 10px 20px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background: {COLOR_ACCENT_RED};
    color: white;
}}

QCheckBox {{
    color: {COLOR_TEXT_PRIMARY};
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {COLOR_BORDER};
    border-radius: 3px;
    background: {COLOR_BG_LIGHT};
}}

QCheckBox::indicator:checked {{
    background: {COLOR_ACCENT_RED};
}}

QProgressBar {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 5px;
    text-align: center;
    color: white;
}}

QProgressBar::chunk {{
    background-color: {COLOR_ACCENT_RED};
    width: 20px;
}}
"""

def apply_industrial_theme(app: QApplication):
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLOR_BG_DARK))
    palette.setColor(QPalette.WindowText, QColor(COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.Base, QColor(0, 0, 0))
    palette.setColor(QPalette.AlternateBase, QColor(COLOR_BG_DARK))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, QColor(COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.Button, QColor(COLOR_BG_LIGHT))
    palette.setColor(QPalette.ButtonText, QColor(COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.Link, QColor(COLOR_ACCENT_RED))
    palette.setColor(QPalette.Highlight, QColor(COLOR_ACCENT_RED))
    palette.setColor(QPalette.HighlightedText, Qt.black)

    app.setPalette(palette)
    app.setStyleSheet(INDUSTRIAL_STYLE)

    default_font = QFont("Helvetica Neue", 10)
    app.setFont(default_font)
