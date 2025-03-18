from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QPushButton, QLineEdit, QMessageBox, QListWidget,
                            QInputDialog, QStackedWidget)
from PyQt6.QtCore import Qt
import requests
import client_config as client_config
from client.token_storage import TokenStorage
from .warehouse_view import WarehouseView
from typing import Optional

class MainWindow(QMainWindow):
    def __init__(self, email):
        super().__init__()
        self.email = email
        self.token_storage = TokenStorage()
        self.initUI()
        self.load_warehouses()

    def initUI(self):
        self.setWindowTitle('Система управления складом')
        self.setGeometry(100, 100, 800, 600)

        # Создаем стек виджетов для переключения между экранами
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Создаем главный экран
        self.main_screen = QWidget()
        main_layout = QHBoxLayout(self.main_screen)

        # Левая панель со списком складов (1/4 ширины)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        warehouses_label = QLabel("Мои склады")
        warehouses_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        left_layout.addWidget(warehouses_label)

        self.warehouses_list = QListWidget()
        self.warehouses_list.itemClicked.connect(self.warehouse_selected)
        left_layout.addWidget(self.warehouses_list)

        add_warehouse_button = QPushButton("+ Добавить склад")
        add_warehouse_button.clicked.connect(self.add_warehouse)
        left_layout.addWidget(add_warehouse_button)

        main_layout.addWidget(left_panel, stretch=1)

        # Правая панель (3/4 ширины)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        welcome_label = QLabel(f"Добро пожаловать, {self.email}!")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet("font-size: 24px; margin: 20px;")
        right_layout.addWidget(welcome_label)

        buttons_layout = QHBoxLayout()
        
        test_button = QPushButton("Проверить сессию")
        test_button.clicked.connect(self.test_session)
        buttons_layout.addWidget(test_button)

        logout_button = QPushButton("Выйти")
        logout_button.clicked.connect(self.logout)
        buttons_layout.addWidget(logout_button)

        right_layout.addLayout(buttons_layout)
        right_layout.addStretch()

        main_layout.addWidget(right_panel, stretch=3)

        # Добавляем главный экран в стек
        self.stacked_widget.addWidget(self.main_screen)

    def get_auth_headers(self):
        """Получает заголовки авторизации с автоматическим обновлением токена"""
        tokens = self.token_storage.get_tokens(self.email)
        if not tokens:
            QMessageBox.warning(self, 'Ошибка', 'Токены не найдены')
            return None

        headers = {'Authorization': f'Bearer {tokens["access_token"]}'}
        
        # Пробуем сделать тестовый запрос
        try:
            response = requests.get(
                f'{client_config.SERVER_URL}/test-auth',
                headers=headers
            )
            if response.status_code == 200:
                return headers
            
            # Если токен истек, пробуем обновить
            response = requests.post(
                f'{client_config.SERVER_URL}/refresh-token',
                json={'current_refresh_token': tokens['refresh_token']}
            )
            if response.status_code == 200:
                data = response.json()
                self.token_storage.store_tokens(
                    self.email,
                    data['access_token'],
                    data['refresh_token']
                )
                return {'Authorization': f'Bearer {data["access_token"]}'}
            else:
                QMessageBox.warning(self, 'Ошибка', 'Сессия истекла')
                self.logout()
                return None
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', f'Ошибка проверки сессии: {str(e)}')
            return None

    def load_warehouses(self):
        """Загружает список складов с сервера"""
        headers = self.get_auth_headers()
        if not headers:
            return

        try:
            response = requests.get(
                f'{client_config.SERVER_URL}/warehouses',
                headers=headers
            )
            
            if response.status_code == 200:
                warehouses = response.json()
                self.warehouses_list.clear()
                for warehouse in warehouses:
                    self.warehouses_list.addItem(warehouse['name'])
            else:
                QMessageBox.warning(self, 'Ошибка', 'Не удалось загрузить список складов')
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', f'Ошибка загрузки складов: {str(e)}')

    def add_warehouse(self):
        """Добавляет новый склад"""
        name, ok = QInputDialog.getText(self, 'Новый склад', 'Введите название склада:')
        
        if ok and name:
            headers = self.get_auth_headers()
            if not headers:
                return

            try:
                response = requests.post(
                    f'{client_config.SERVER_URL}/warehouses',
                    headers=headers,
                    json={'name': name}
                )
                
                if response.status_code == 200:
                    QMessageBox.information(self, 'Успех', 'Склад успешно создан')
                    self.load_warehouses()
                else:
                    QMessageBox.warning(self, 'Ошибка', 'Не удалось создать склад')
            except Exception as e:
                QMessageBox.warning(self, 'Ошибка', f'Ошибка создания склада: {str(e)}')

    def warehouse_selected(self, item):
        """Обработчик выбора склада из списка"""
        headers = self.get_auth_headers()
        if not headers:
            return

        try:
            # Сначала проверяем доступ к складу
            response = requests.get(
                f'{client_config.SERVER_URL}/warehouses',
                headers=headers,
                timeout=client_config.API_TIMEOUT
            )
            
            if response.status_code == 200:
                warehouses = response.json()
                selected_warehouse = next(
                    (w for w in warehouses if w['name'] == item.text()),
                    None
                )
                
                if selected_warehouse:
                    # Удаляем предыдущий виджет склада, если он есть
                    current = self.stacked_widget.currentWidget()
                    if current != self.main_screen:
                        self.stacked_widget.removeWidget(current)
                        current.deleteLater()
                        
                    # Создаем новый виджет склада
                    warehouse_view = WarehouseView(
                        selected_warehouse['id'],
                        selected_warehouse['name'],
                        self.email,
                        self
                    )
                    self.stacked_widget.addWidget(warehouse_view)
                    self.stacked_widget.setCurrentWidget(warehouse_view)
                else:
                    QMessageBox.warning(self, 'Ошибка', 'Склад не найден')
            else:
                QMessageBox.warning(self, 'Ошибка', 'Не удалось получить информацию о складе')
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, 'Ошибка', 'Сервер не отвечает')
        except requests.exceptions.ConnectionError:
            QMessageBox.warning(self, 'Ошибка', 'Не удалось подключиться к серверу')
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', f'Ошибка при открытии склада: {str(e)}')

    def show_main_screen(self):
        """Возвращает на главный экран"""
        # Удаляем текущий виджет склада из стека
        current_widget = self.stacked_widget.currentWidget()
        if current_widget != self.main_screen:
            self.stacked_widget.removeWidget(current_widget)
            current_widget.deleteLater()  # Освобождаем память
        self.stacked_widget.setCurrentWidget(self.main_screen)
        self.load_warehouses()  # Обновляем список складов

    def test_session(self):
        headers = self.get_auth_headers()
        if headers:
            QMessageBox.information(self, 'Успех', 'Сессия активна')

    def logout(self):
        try:
            headers = self.get_auth_headers()
            if headers:
                requests.post(
                    f'{client_config.SERVER_URL}/logout',
                    headers=headers
                )
            self.token_storage.clear_tokens(self.email)
            
            from .login_window import LoginWindow
            self.login_window = LoginWindow()
            self.login_window.show()
            self.close()
        except:
            QMessageBox.warning(self, 'Ошибка', 'Ошибка при выходе из системы') 