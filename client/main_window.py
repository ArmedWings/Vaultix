from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QPushButton, QLineEdit, QMessageBox, QListWidget,
                            QInputDialog)
from PyQt6.QtCore import Qt
import requests
import client_config as client_config
from client.token_storage import TokenStorage
from typing import Optional

class MainWindow(QMainWindow):
    def __init__(self, email):
        super().__init__()
        self.email = email
        self.token_storage = TokenStorage()
        self.initUI()
        self.load_warehouses()  # Загружаем склады при инициализации

    def initUI(self):
        self.setWindowTitle('Система управления складом')
        self.setGeometry(100, 100, 800, 600)

        # Главный виджет и layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Левая панель со списком складов (1/4 ширины)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Заголовок списка складов
        warehouses_label = QLabel("Мои склады")
        warehouses_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        left_layout.addWidget(warehouses_label)

        # Список складов
        self.warehouses_list = QListWidget()
        self.warehouses_list.itemClicked.connect(self.warehouse_selected)
        left_layout.addWidget(self.warehouses_list)

        # Кнопка добавления склада
        add_warehouse_button = QPushButton("+ Добавить склад")
        add_warehouse_button.clicked.connect(self.add_warehouse)
        left_layout.addWidget(add_warehouse_button)

        main_layout.addWidget(left_panel, stretch=1)  # 1/4 ширины

        # Правая панель (3/4 ширины)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Приветствие
        welcome_label = QLabel(f"Добро пожаловать, {self.email}!")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet("font-size: 24px; margin: 20px;")
        right_layout.addWidget(welcome_label)

        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        test_button = QPushButton("Проверить сессию")
        test_button.clicked.connect(self.test_session)
        buttons_layout.addWidget(test_button)

        logout_button = QPushButton("Выйти")
        logout_button.clicked.connect(self.logout)
        buttons_layout.addWidget(logout_button)

        right_layout.addLayout(buttons_layout)
        right_layout.addStretch()  # Добавляем растяжку, чтобы виджеты были вверху

        main_layout.addWidget(right_panel, stretch=3)  # 3/4 ширины

    def load_warehouses(self):
        """Загружает список складов с сервера"""
        try:
            tokens = self.token_storage.get_tokens(self.email)
            if not tokens:
                return

            headers = {'Authorization': f'Bearer {tokens["access_token"]}'}
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
            try:
                tokens = self.token_storage.get_tokens(self.email)
                if not tokens:
                    return

                headers = {'Authorization': f'Bearer {tokens["access_token"]}'}
                response = requests.post(
                    f'{client_config.SERVER_URL}/warehouses',
                    headers=headers,
                    json={'name': name}
                )
                
                if response.status_code == 200:
                    QMessageBox.information(self, 'Успех', 'Склад успешно создан')
                    self.load_warehouses()  # Перезагружаем список складов
                else:
                    QMessageBox.warning(self, 'Ошибка', 'Не удалось создать склад')
            except Exception as e:
                QMessageBox.warning(self, 'Ошибка', f'Ошибка создания склада: {str(e)}')

    def warehouse_selected(self, item):
        """Обработчик выбора склада из списка"""
        # TODO: Добавить логику отображения содержимого склада
        QMessageBox.information(self, 'Информация', f'Выбран склад: {item.text()}')

    def test_session(self):
        try:
            tokens = self.token_storage.get_tokens(self.email)
            if not tokens:
                QMessageBox.warning(self, 'Ошибка', 'Токены не найдены')
                return

            headers = {'Authorization': f'Bearer {tokens["access_token"]}'}
            response = requests.get(
                f'{client_config.SERVER_URL}/test-auth',
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                QMessageBox.information(self, 'Успех', data['message'])
            else:
                # Пробуем обновить токен
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
                    QMessageBox.information(self, 'Успех', 'Токен обновлен, сессия активна')
                else:
                    QMessageBox.warning(self, 'Ошибка', 'Сессия истекла')
                    self.logout()
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', f'Ошибка проверки сессии: {str(e)}')

    def logout(self):
        try:
            tokens = self.token_storage.get_tokens(self.email)
            if tokens:
                headers = {'Authorization': f'Bearer {tokens["access_token"]}'}
                requests.post(
                    f'{client_config.SERVER_URL}/logout',
                    headers=headers
                )
                self.token_storage.clear_tokens(self.email)
            
            # Импортируем здесь для избежания циклического импорта
            from .login_window import LoginWindow
            self.login_window = LoginWindow()
            self.login_window.show()
            self.close()
        except:
            QMessageBox.warning(self, 'Ошибка', 'Ошибка при выходе из системы') 