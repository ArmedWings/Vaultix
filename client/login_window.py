from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                            QLabel, QPushButton, QLineEdit, QMessageBox)
from PyQt6.QtCore import Qt
import requests
import hashlib
import client_config as client_config
from client.token_storage import TokenStorage

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.token_storage = TokenStorage()
        self.initUI()

    def check_saved_session(self) -> bool:
        # Проверяем все сохраненные сессии
        all_tokens = self.token_storage.get_all_tokens()
        for email, tokens in all_tokens.items():
            try:
                # Пробуем сделать тестовый запрос с токеном
                headers = {'Authorization': f'Bearer {tokens["access_token"]}'}
                response = requests.get(
                    f'{client_config.SERVER_URL}/test-auth',
                    headers=headers
                )
                
                if response.status_code == 200:
                    print(f"Сессия активна для {email}")
                    self.open_main_window(email)
                    return True
                    
                # Если токен истек, пробуем обновить через refresh token
                response = requests.post(
                    f'{client_config.SERVER_URL}/refresh-token',
                    json={'current_refresh_token': tokens['refresh_token']}
                )
                if response.status_code == 200:
                    data = response.json()
                    self.token_storage.store_tokens(
                        email,
                        data['access_token'],
                        data['refresh_token']
                    )
                    self.open_main_window(email)
                    return True
            except Exception as e:
                print(f"Ошибка проверки сессии: {e}")
                self.token_storage.clear_tokens(email)
        return False

    def initUI(self):
        self.setWindowTitle('Вход в систему')
        self.setGeometry(100, 100, 400, 300)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Заголовок
        title = QLabel("Система управления складом")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)

        # Поля для входа
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email")
        layout.addWidget(self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)

        # Кнопки
        login_button = QPushButton("Войти")
        login_button.clicked.connect(self.login)
        layout.addWidget(login_button)

        register_button = QPushButton("Зарегистрироваться")
        register_button.clicked.connect(self.register)
        layout.addWidget(register_button)

    def hash_password(self, password: str) -> str:
        salted = password + client_config.HASH_SALT
        return hashlib.sha256(salted.encode()).hexdigest()

    def login(self):
        email = self.email_input.text()
        password = self.hash_password(self.password_input.text())

        try:
            response = requests.post(f'{client_config.SERVER_URL}/login',
                                   json={'email': email, 'password': password})
            
            if response.status_code == 200:
                data = response.json()
                print(data.get("message"))
                if data.get("message") == "Код для входа отправлен на ваш email":
                    print(f"Успешный вход для пользователя {email}")
                    # Импортируем здесь для избежания циклического импорта
                    from .verification_window import VerificationWindow
                    self.verification_window = VerificationWindow(email)
                    self.verification_window.show()
                    self.hide()
                else:
                    print(f"Ошибка входа для пользователя {email}")
                    QMessageBox.warning(self, 'Ошибка', 'Неверные данные для входа')
            else:
                error_data = response.json()
                error_message = error_data.get("detail", "Неизвестная ошибка")
                QMessageBox.warning(self, 'Ошибка', error_message)
        except:
            QMessageBox.warning(self, 'Ошибка', 'Ошибка подключения к серверу')

    def register(self):
        email = self.email_input.text()
        password = self.hash_password(self.password_input.text())

        try:
            response = requests.post(f'{client_config.SERVER_URL}/register',
                                   json={'email': email, 'password': password})
            
            if response.status_code == 200:
                QMessageBox.information(self, 'Успех', 'Регистрация успешна')
            else:
                error_data = response.json()
                error_message = error_data.get("detail", "Ошибка при регистрации")
                QMessageBox.warning(self, 'Ошибка', error_message)
        except:
            QMessageBox.warning(self, 'Ошибка', 'Ошибка подключения к серверу')

    def open_main_window(self, email):
        # Импортируем здесь для избежания циклического импорта
        from .main_window import MainWindow
        self.main_window = MainWindow(email)
        self.main_window.show()
        self.hide() 