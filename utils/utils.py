from PySide6.QtWidgets import QTableWidget, QHeaderView, QMessageBox

def create_table(headers):
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return table

def show_error_message(title, message):
    error_box = QMessageBox()
    error_box.setIcon(QMessageBox.Icon.Critical)
    error_box.setWindowTitle(title)
    error_box.setText(message)
    error_box.exec()