from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTableWidget, QTableWidgetItem, QLabel,
                             QLineEdit, QComboBox, QSpinBox, QDialog, QMessageBox)
from PyQt6.QtCore import Qt
import requests
from .token_storage import TokenStorage
import client_config

class WarehouseView(QWidget):
    def __init__(self, warehouse_id, warehouse_name, email, parent=None):
        super().__init__(parent)
        self.warehouse_id = warehouse_id
        self.warehouse_name = warehouse_name
        self.email = email
        self.token_storage = TokenStorage()
        self.setup_ui()
        # Проверяем доступ при инициализации
        if not self.check_access():
            self.go_back()
            return
        self.load_products()

    def check_access(self):
        """Проверяет доступ к складу"""
        headers = self.get_auth_headers()
        if not headers:
            return False

        try:
            response = requests.get(
                f"{client_config.SERVER_URL}/warehouses/{self.warehouse_id}/products",
                headers=headers,
                timeout=client_config.API_TIMEOUT
            )
            return response.status_code == 200
        except:
            return False

    def get_auth_headers(self):
        """Получает заголовки авторизации с автоматическим обновлением токена"""
        tokens = self.token_storage.get_tokens(self.email)
        if not tokens:
            QMessageBox.warning(self, "Ошибка", "Токены не найдены")
            self.go_back()
            return None

        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        
        try:
            response = requests.get(
                f"{client_config.SERVER_URL}/test-auth",
                headers=headers,
                timeout=client_config.API_TIMEOUT
            )
            if response.status_code == 200:
                return headers
            
            # Если токен истек, пробуем обновить
            response = requests.post(
                f"{client_config.SERVER_URL}/refresh-token",
                json={"current_refresh_token": tokens["refresh_token"]},
                timeout=client_config.API_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                self.token_storage.store_tokens(
                    self.email,
                    data["access_token"],
                    data["refresh_token"]
                )
                return {"Authorization": f"Bearer {data['access_token']}"}
            else:
                QMessageBox.warning(self, "Ошибка", "Сессия истекла")
                if self.parent():
                    self.parent().logout()
                return None
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, "Ошибка", "Сервер не отвечает")
            return None
        except requests.exceptions.ConnectionError:
            QMessageBox.warning(self, "Ошибка", "Не удалось подключиться к серверу")
            return None
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Ошибка проверки сессии: {str(e)}")
            return None

    def go_back(self):
        """Возвращает на главный экран"""
        # Ищем главное окно в иерархии родителей
        main_window = self.window()
        if isinstance(main_window, QMainWindow):
            main_window.show_main_screen()

    def load_products(self):
        headers = self.get_auth_headers()
        if not headers:
            self.go_back()
            return
            
        try:
            response = requests.get(
                f"{client_config.SERVER_URL}/warehouses/{self.warehouse_id}/products",
                headers=headers,
                timeout=client_config.API_TIMEOUT
            )
            if response.status_code == 200:
                products = response.json()
                self.update_products_table(products)
                self.update_categories(products)
            else:
                QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить список товаров: {response.text}")
                self.go_back()
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, "Ошибка", "Сервер не отвечает")
            self.go_back()
        except requests.exceptions.ConnectionError:
            QMessageBox.warning(self, "Ошибка", "Не удалось подключиться к серверу")
            self.go_back()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Ошибка при загрузке товаров: {str(e)}")
            self.go_back()

    def update_products_table(self, products):
        self.products_table.setRowCount(len(products))
        for row, product in enumerate(products):
            self.products_table.setItem(row, 0, QTableWidgetItem(product["category"]))
            self.products_table.setItem(row, 1, QTableWidgetItem(product["name"]))
            self.products_table.setItem(row, 2, QTableWidgetItem(str(product["current_quantity"])))
            self.products_table.setItem(row, 3, QTableWidgetItem(product["updated_at"]))

    def update_categories(self, products):
        categories = set(product["category"] for product in products)
        self.category_filter.clear()
        self.category_filter.addItem("Все категории")
        self.category_filter.addItems(sorted(categories))

    def filter_products(self):
        search_text = self.search_input.text().lower()
        category = self.category_filter.currentText()
        
        for row in range(self.products_table.rowCount()):
            name = self.products_table.item(row, 0).text().lower()
            product_category = self.products_table.item(row, 0).text()
            
            name_match = search_text in name
            category_match = category == "Все категории" or category == product_category
            
            self.products_table.setRowHidden(row, not (name_match and category_match))

    def show_add_type_dialog(self):
        dialog = AddProductTypeDialog(self.email, self)
        if dialog and dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_products()

    def show_add_product_dialog(self):
        dialog = AddProductDialog(self.warehouse_id, self.email, self)
        if dialog and dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_products()

    def show_movement_dialog(self):
        dialog = ProductMovementDialog(self.warehouse_id, self.email, self)
        if dialog and dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_products()

    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        main_layout = QVBoxLayout(self)

        # Верхняя панель
        top_panel = QHBoxLayout()
        back_button = QPushButton("← Назад")
        back_button.clicked.connect(self.go_back)
        back_button.setFixedWidth(100)
        
        title_label = QLabel(f"Склад: {self.warehouse_name}")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        stats_label = QLabel("Статистика склада")
        top_panel.addWidget(back_button)
        top_panel.addWidget(title_label)
        top_panel.addWidget(stats_label)
        top_panel.addStretch()

        # Панель управления
        control_panel = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск товаров...")
        self.search_input.textChanged.connect(self.filter_products)
        
        self.category_filter = QComboBox()
        self.category_filter.addItem("Все категории")
        self.category_filter.currentTextChanged.connect(self.filter_products)
        
        add_type_btn = QPushButton("Добавить категорию")
        add_type_btn.clicked.connect(self.show_add_type_dialog)
        
        add_product_btn = QPushButton("Добавить товар")
        add_product_btn.clicked.connect(self.show_add_product_dialog)
        
        add_movement_btn = QPushButton("Движение товара")
        add_movement_btn.clicked.connect(self.show_movement_dialog)
        
        control_panel.addWidget(self.search_input)
        control_panel.addWidget(self.category_filter)
        control_panel.addWidget(add_type_btn)
        control_panel.addWidget(add_product_btn)
        control_panel.addWidget(add_movement_btn)

        # Таблица товаров
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(4)
        self.products_table.setHorizontalHeaderLabels([
            "Категория", "Название", "Текущий остаток", "Последнее движение"
        ])
        self.products_table.horizontalHeader().setStretchLastSection(True)

        main_layout.addLayout(top_panel)
        main_layout.addLayout(control_panel)
        main_layout.addWidget(self.products_table)

class AddProductTypeDialog(QDialog):
    def __init__(self, email, parent=None):
        super().__init__(parent)
        self.email = email
        self.token_storage = TokenStorage()
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Добавить категорию товара")
        layout = QVBoxLayout(self)

        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("Категория товара")

        buttons_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.save_type)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)

        layout.addWidget(QLabel("Категория:"))
        layout.addWidget(self.category_input)
        layout.addLayout(buttons_layout)

    def save_type(self):
        tokens = self.token_storage.get_tokens(self.email)
        if not tokens:
            QMessageBox.warning(self, "Ошибка", "Сессия истекла")
            self.reject()
            return

        try:
            response = requests.post(
                f"{client_config.SERVER_URL}/product-types",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                json={
                    "category": self.category_input.text()
                }
            )
            if response.status_code == 200:
                self.accept()
            else:
                QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить тип товара: {response.text}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Ошибка при сохранении типа товара: {str(e)}")

class AddProductDialog(QDialog):
    def __init__(self, warehouse_id, email, parent=None):
        super().__init__(parent)
        self.warehouse_id = warehouse_id
        self.email = email
        self.token_storage = TokenStorage()
        self.setup_ui()
        self.load_product_types()

    def setup_ui(self):
        self.setWindowTitle("Добавить товар на склад")
        layout = QVBoxLayout(self)

        self.type_combo = QComboBox()
        self.type_combo.setPlaceholderText("Выберите категорию товара")
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Название товара")
        
        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(0, 1000000)
        self.quantity_input.setValue(0)

        buttons_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.save_product)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)

        layout.addWidget(QLabel("Категория товара:"))
        layout.addWidget(self.type_combo)
        layout.addWidget(QLabel("Название:"))
        layout.addWidget(self.name_input)
        layout.addWidget(QLabel("Начальное количество:"))
        layout.addWidget(self.quantity_input)
        layout.addLayout(buttons_layout)

    def load_product_types(self):
        tokens = self.token_storage.get_tokens(self.email)
        if not tokens:
            QMessageBox.warning(self, "Ошибка", "Сессия истекла")
            self.reject()
            return

        try:
            response = requests.get(
                f"{client_config.SERVER_URL}/product-types",
                headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
            if response.status_code == 200:
                types = response.json()
                self.type_combo.clear()
                for t in types:
                    self.type_combo.addItem(t['category'], t['id'])
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось загрузить типы товаров")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Ошибка при загрузке типов товаров: {str(e)}")

    def save_product(self):
        tokens = self.token_storage.get_tokens(self.email)
        if not tokens:
            QMessageBox.warning(self, "Ошибка", "Сессия истекла")
            self.reject()
            return

        try:
            product_type_id = self.type_combo.currentData()
            if product_type_id is None:
                QMessageBox.warning(self, "Ошибка", "Выберите категорию товара")
                return
                
            response = requests.post(
                f"{client_config.SERVER_URL}/warehouses/{self.warehouse_id}/products",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                json={
                    "product_type_id": product_type_id,
                    "name": self.name_input.text(),
                    "quantity": self.quantity_input.value()
                }
            )
            if response.status_code == 200:
                self.accept()
            else:
                QMessageBox.warning(self, "Ошибка", f"Не удалось добавить товар: {response.text}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Ошибка при добавлении товара: {str(e)}")

class ProductMovementDialog(QDialog):
    def __init__(self, warehouse_id, email, parent=None):
        super().__init__(parent)
        self.warehouse_id = warehouse_id
        self.email = email
        self.token_storage = TokenStorage()
        self.setup_ui()
        self.load_products()

    def setup_ui(self):
        self.setWindowTitle("Движение товара")
        layout = QVBoxLayout(self)

        self.product_combo = QComboBox()
        self.product_combo.setPlaceholderText("Выберите товар")
        
        self.movement_type = QComboBox()
        self.movement_type.addItems(["Приход", "Расход"])

        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(1, 1000000)

        self.comment_input = QLineEdit()
        self.comment_input.setPlaceholderText("Комментарий к операции")

        buttons_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.save_movement)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)

        layout.addWidget(QLabel("Товар:"))
        layout.addWidget(self.product_combo)
        layout.addWidget(QLabel("Тип движения:"))
        layout.addWidget(self.movement_type)
        layout.addWidget(QLabel("Количество:"))
        layout.addWidget(self.quantity_input)
        layout.addWidget(QLabel("Комментарий:"))
        layout.addWidget(self.comment_input)
        layout.addLayout(buttons_layout)

    def load_products(self):
        tokens = self.token_storage.get_tokens(self.email)
        if not tokens:
            QMessageBox.warning(self, "Ошибка", "Сессия истекла")
            self.reject()
            return

        try:
            response = requests.get(
                f"{client_config.SERVER_URL}/warehouses/{self.warehouse_id}/products",
                headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
            if response.status_code == 200:
                products = response.json()
                self.product_combo.clear()
                for p in products:
                    self.product_combo.addItem(
                        f"{p['name']} ({p['category']}) - Остаток: {p['current_quantity']}",
                        p['id']
                    )
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось загрузить товары")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Ошибка при загрузке товаров: {str(e)}")

    def save_movement(self):
        tokens = self.token_storage.get_tokens(self.email)
        if not tokens:
            QMessageBox.warning(self, "Ошибка", "Сессия истекла")
            self.reject()
            return

        try:
            product_id = self.product_combo.currentData()
            if product_id is None:
                QMessageBox.warning(self, "Ошибка", "Выберите товар")
                return
                
            movement_type = "in" if self.movement_type.currentText() == "Приход" else "out"
            
            response = requests.post(
                f"{client_config.SERVER_URL}/warehouses/{self.warehouse_id}/movements",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                json={
                    "product_id": product_id,
                    "quantity": self.quantity_input.value(),
                    "movement_type": movement_type,
                    "comment": self.comment_input.text() if self.comment_input.text() else None
                }
            )
            if response.status_code == 200:
                self.accept()
            else:
                QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить движение товара: {response.text}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Ошибка при сохранении движения: {str(e)}") 