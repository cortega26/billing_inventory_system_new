from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                               QPushButton, QInputDialog, QMessageBox)
from services.category_service import CategoryService
from utils.logger import logger

class CategoryManagementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.category_service = CategoryService()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.category_list = QListWidget()
        layout.addWidget(self.category_list)
        
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
        
        self.load_categories()

    def load_categories(self):
        self.category_list.clear()
        categories = self.category_service.get_all_categories()
        for category in categories:
            self.category_list.addItem(category.name)

    def add_category(self):
        name, ok = QInputDialog.getText(self, "Add Category", "Category name:")
        if ok and name:
            try:
                self.category_service.create_category(name)
                self.load_categories()
            except Exception as e:
                logger.error(f"Error adding category: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to add category: {str(e)}")

    def edit_category(self):
        current_item = self.category_list.currentItem()
        if current_item:
            old_name = current_item.text()
            new_name, ok = QInputDialog.getText(self, "Edit Category", "New category name:", text=old_name)
            if ok and new_name:
                try:
                    category = self.category_service.get_category_by_name(old_name)
                    if category:
                        self.category_service.update_category(category.id, new_name)
                        self.load_categories()
                    else:
                        raise ValueError(f"Category '{old_name}' not found")
                except Exception as e:
                    logger.error(f"Error editing category: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to edit category: {str(e)}")

    def delete_category(self):
        current_item = self.category_list.currentItem()
        if current_item:
            reply = QMessageBox.question(self, "Delete Category", 
                                         f"Are you sure you want to delete the category '{current_item.text()}'?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    category = self.category_service.get_category_by_name(current_item.text())
                    if category:
                        self.category_service.delete_category(category.id)
                        self.load_categories()
                    else:
                        raise ValueError(f"Category '{current_item.text()}' not found")
                except Exception as e:
                    logger.error(f"Error deleting category: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to delete category: {str(e)}")