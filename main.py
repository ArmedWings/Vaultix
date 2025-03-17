import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QLabel, QPushButton, QLineEdit, QMessageBox)
from PyQt6.QtCore import Qt, QTimer
import requests
import hashlib
import client_config
from token_storage import TokenStorage

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
        self.main_window = MainWindow(email)
        self.main_window.show()
        self.hide()

class VerificationWindow(QMainWindow):
    def __init__(self, email):
        super().__init__()
        self.email = email
        self.token_storage = TokenStorage()
        self.remaining_time = 300  # 5 минут в секундах
        self.resend_cooldown = 60  # 60 секунд задержка
        self.initUI()
        self.startCodeTimer()
        self.disableResendButton()

    def initUI(self):
        self.setWindowTitle('Подтверждение входа')
        self.setGeometry(100, 100, 400, 300)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Заголовок
        title = QLabel("Введите код подтверждения")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)

        # Поле для кода
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Введите код из email")
        layout.addWidget(self.code_input)

        # Добавляем метку для таймера
        self.timer_label = QLabel()
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.timer_label)

        # Кнопки
        verify_button = QPushButton("Подтвердить")
        verify_button.clicked.connect(self.verify_code)
        layout.addWidget(verify_button)

        self.resend_button = QPushButton("Отправить код повторно")
        self.resend_button.clicked.connect(self.resend_code)
        layout.addWidget(self.resend_button)

    def startCodeTimer(self):
        self.code_timer = QTimer()
        self.code_timer.timeout.connect(self.updateCodeTimer)
        self.code_timer.start(1000)  # Обновление каждую секунду
        self.updateCodeTimer()

    def updateCodeTimer(self):
        self.remaining_time -= 1
        minutes = self.remaining_time // 60
        seconds = self.remaining_time % 60
        self.timer_label.setText(f"Код действителен: {minutes:02d}:{seconds:02d}")
        
        if self.remaining_time <= 0:
            self.code_timer.stop()
            self.timer_label.setText("Срок действия кода истек")

    def disableResendButton(self):
        self.resend_button.setEnabled(False)
        self.cooldown_timer = QTimer()
        self.cooldown_timer.timeout.connect(self.updateResendTimer)
        self.cooldown_timer.start(1000)
        self.resend_cooldown_remaining = self.resend_cooldown
        self.updateResendTimer()

    def updateResendTimer(self):
        if self.resend_cooldown_remaining > 0:
            self.resend_button.setText(
                f"Отправить код повторно ({self.resend_cooldown_remaining})")
            self.resend_cooldown_remaining -= 1
        else:
            self.resend_button.setEnabled(True)
            self.resend_button.setText("Отправить код повторно")
            self.cooldown_timer.stop()

    def verify_code(self):
        code = self.code_input.text()
        try:
            response = requests.post(f'{client_config.SERVER_URL}/verify',
                                   json={'email': self.email, 'code': code})
            
            if response.status_code == 200:
                data = response.json()
                self.token_storage.store_tokens(
                    self.email,
                    data['access_token'],
                    data['refresh_token']
                )
                print(f"Код подтвержден для пользователя {self.email}")
                self.open_main_window(self.email)
            else:
                error_data = response.json()
                error_message = error_data.get("detail", "Неверный код подтверждения")
                QMessageBox.warning(self, 'Ошибка', error_message)
        except:
            QMessageBox.warning(self, 'Ошибка', 'Ошибка подключения к серверу')

    def resend_code(self):
        try:
            response = requests.post(f'{client_config.SERVER_URL}/login',
                                   json={'email': self.email, 'password': ''})
            if response.status_code == 200:
                QMessageBox.information(self, 'Успех', 'Новый код отправлен')
                self.remaining_time = 300  # Сбрасываем таймер кода
                self.startCodeTimer()
                self.disableResendButton()
            else:
                error_data = response.json()
                error_message = error_data.get("detail", "Ошибка отправки кода")
                QMessageBox.warning(self, 'Ошибка', error_message)
        except:
            QMessageBox.warning(self, 'Ошибка', 'Ошибка подключения к серверу')

    def open_main_window(self, email):
        self.main_window = MainWindow(email)
        self.main_window.show()
        self.hide()

class MainWindow(QMainWindow):
    def __init__(self, email):
        super().__init__()
        self.email = email
        self.token_storage = TokenStorage()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Система управления складом')
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Приветствие
        welcome_label = QLabel(f"Добро пожаловать, {self.email}!")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet("font-size: 24px; margin: 20px;")
        layout.addWidget(welcome_label)

        # Кнопка для проверки сессии
        test_button = QPushButton("Проверить сессию")
        test_button.clicked.connect(self.test_session)
        layout.addWidget(test_button)

        # Кнопка выхода
        logout_button = QPushButton("Выйти")
        logout_button.clicked.connect(self.logout)
        layout.addWidget(logout_button)

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
            
            # Открываем окно входа
            self.login_window = LoginWindow()
            self.login_window.show()
            self.close()
        except:
            QMessageBox.warning(self, 'Ошибка', 'Ошибка при выходе из системы')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    login_window = LoginWindow()
    
    # Проверяем сессию перед показом окна
    if not login_window.check_saved_session():
        login_window.show()
    
    sys.exit(app.exec()) 