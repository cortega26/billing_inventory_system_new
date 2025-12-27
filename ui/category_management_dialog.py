from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from services.category_service import CategoryService
from utils.decorators import handle_exceptions, ui_operation
from utils.exceptions import DatabaseException, UIException, ValidationException
from utils.helpers import show_info_message
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.validation.validators import validate_string


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
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def accept(self):
        name = validate_string(
            self.name_input.text().strip(), min_length=1, max_length=50
        )
        if self.category:
            self.category_service.update_category(self.category.id, name)
            logger.info(f"Category updated: ID {self.category.id}, Name: {name}")
        else:
            category_id = self.category_service.create_category(name)
            logger.info(f"Category created: ID {category_id}, Name: {name}")
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
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_categories(self):
        try:
            self.category_list.clear()
            categories = self.category_service.get_all_categories()
            for category in categories:
                self.category_list.addItem(category.name)
            self.update_status(f"Loaded {len(categories)} categories")
            logger.info(f"Loaded {len(categories)} categories")
        except Exception as e:
            logger.error(f"Error loading categories: {str(e)}")
            raise DatabaseException(f"Failed to load categories: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def add_category(self):
        dialog = AddEditCategoryDialog(self)
        if dialog.exec():
            self.load_categories()
            show_info_message("Success", "Category added successfully.")
            event_system.category_added.emit()
            logger.info("New category added")

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def edit_category(self):
        current_item = self.category_list.currentItem()
        if current_item:
            category = self.category_service.get_category_by_name(current_item.text())
            if category:
                dialog = AddEditCategoryDialog(self, category)
                if dialog.exec():
                    self.load_categories()
                    show_info_message("Success", "Category updated successfully.")
                    event_system.category_updated.emit(category.id)
                    logger.info(f"Category updated: ID {category.id}")
            else:
                raise ValidationException(f"Category '{current_item.text()}' not found")
        else:
            raise ValidationException("Please select a category to edit.")

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
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
                    event_system.category_deleted.emit(category.id)
                    logger.info(f"Category deleted: ID {category.id}")
                else:
                    raise ValidationException(
                        f"Category '{current_item.text()}' not found"
                    )
        else:
            raise ValidationException("Please select a category to delete.")

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def search_categories(self):
        search_term = validate_string(self.search_input.text().strip(), max_length=50)
        if search_term:
            categories = self.category_service.search_categories(search_term)
            self.category_list.clear()
            for category in categories:
                self.category_list.addItem(category.name)
            self.update_status(
                f"Found {len(categories)} categories matching '{search_term}'"
            )
            logger.info(f"Searched categories: {len(categories)} results")
        else:
            self.load_categories()

    def update_status(self, message: str):
        self.status_label.setText(message)
        logger.info(message)
