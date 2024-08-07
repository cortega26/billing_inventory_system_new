from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QMessageBox,
    QLineEdit,
    QFormLayout,
    QDialogButtonBox,
    QLabel,
)
from PySide6.QtCore import Qt
from services.category_service import CategoryService
from utils.system.logger import logger
from utils.helpers import show_error_message, show_info_message
from utils.decorators import ui_operation


class AddEditCategoryDialog(QDialog):
    def __init__(self, parent=None, category=None):
        super().__init__(parent)
        self.category = category
        self.category_service = CategoryService()
        self.setWindowTitle("Add Category" if category is None else "Edit Category")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.name_input = QLineEdit(self.category.name if self.category else "")
        layout.addRow("Category Name:", self.name_input)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    @ui_operation(show_dialog=True)
    def accept(self):
        name = self.name_input.text().strip()
        if not name:
            show_error_message("Invalid Input", "Category name cannot be empty.")
            return

        if self.category:
            self.category_service.update_category(self.category.id, name)
        else:
            self.category_service.create_category(name)
        super().accept()


class CategoryManagementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.category_service = CategoryService()
        self.setup_ui()
        self.setWindowTitle("Category Management")

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search categories...")
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_categories)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # Category list
        self.category_list = QListWidget()
        layout.addWidget(self.category_list)

        # Buttons
        button_layout = QHBoxLayout()
        add_button = QPushButton("Add Category")
        add_button.clicked.connect(self.add_category)
        edit_button = QPushButton("Edit Category")
        edit_button.clicked.connect(self.edit_category)
        delete_button = QPushButton("Delete Category")
        delete_button.clicked.connect(self.delete_category)

        button_layout.addWidget(add_button)
        button_layout.addWidget(edit_button)
        button_layout.addWidget(delete_button)

        layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        self.load_categories()

    @ui_operation(show_dialog=True)
    def load_categories(self):
        self.category_list.clear()
        categories = self.category_service.get_all_categories()
        for category in categories:
            self.category_list.addItem(category.name)
        self.update_status(f"Loaded {len(categories)} categories")

    @ui_operation(show_dialog=True)
    def add_category(self):
        dialog = AddEditCategoryDialog(self)
        if dialog.exec():
            self.load_categories()
            show_info_message("Success", "Category added successfully.")

    @ui_operation(show_dialog=True)
    def edit_category(self):
        current_item = self.category_list.currentItem()
        if current_item:
            category = self.category_service.get_category_by_name(current_item.text())
            if category:
                dialog = AddEditCategoryDialog(self, category)
                if dialog.exec():
                    self.load_categories()
                    show_info_message("Success", "Category updated successfully.")
            else:
                raise ValueError(f"Category '{current_item.text()}' not found")
        else:
            show_error_message("Error", "Please select a category to edit.")

    @ui_operation(show_dialog=True)
    def delete_category(self):
        current_item = self.category_list.currentItem()
        if current_item:
            reply = QMessageBox.question(
                self,
                "Delete Category",
                f"Are you sure you want to delete the category '{current_item.text()}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                category = self.category_service.get_category_by_name(
                    current_item.text()
                )
                if category:
                    self.category_service.delete_category(category.id)
                    self.load_categories()
                    show_info_message("Success", "Category deleted successfully.")
                else:
                    raise ValueError(f"Category '{current_item.text()}' not found")
        else:
            show_error_message("Error", "Please select a category to delete.")

    @ui_operation(show_dialog=True)
    def search_categories(self):
        search_term = self.search_input.text().strip()
        if search_term:
            categories = self.category_service.search_categories(search_term)
            self.category_list.clear()
            for category in categories:
                self.category_list.addItem(category.name)
            self.update_status(
                f"Found {len(categories)} categories matching '{search_term}'"
            )
        else:
            self.load_categories()

    def update_status(self, message: str):
        self.status_label.setText(message)
        logger.info(message)
