import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QLabel, QPushButton, QLineEdit, QMessageBox)
from PyQt6.QtCore import Qt
import requests

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

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

    def login(self):
        email = self.email_input.text()
        password = self.password_input.text()

        try:
            response = requests.post('http://localhost:5000/login',
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
        password = self.password_input.text()

        try:
            response = requests.post('http://localhost:5000/register',
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
        self.initUI()

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

        # Кнопки
        verify_button = QPushButton("Подтвердить")
        verify_button.clicked.connect(self.verify_code)
        layout.addWidget(verify_button)

        resend_button = QPushButton("Отправить код повторно")
        resend_button.clicked.connect(self.resend_code)
        layout.addWidget(resend_button)

    def verify_code(self):
        code = self.code_input.text()
        try:
            response = requests.post('http://localhost:5000/verify',
                                   json={'email': self.email, 'code': code})
            
            if response.status_code == 200:
                print(f"Код подтвержден для пользователя {self.email}")
                self.open_main_window()
            else:
                error_data = response.json()
                error_message = error_data.get("detail", "Неверный код подтверждения")
                QMessageBox.warning(self, 'Ошибка', error_message)
        except:
            QMessageBox.warning(self, 'Ошибка', 'Ошибка подключения к серверу')

    def resend_code(self):
        try:
            response = requests.post('http://localhost:5000/login',
                                   json={'email': self.email, 'password': ''})
            if response.status_code == 200:
                QMessageBox.information(self, 'Успех', 'Новый код отправлен')
            else:
                error_data = response.json()
                error_message = error_data.get("detail", "Ошибка отправки кода")
                QMessageBox.warning(self, 'Ошибка', error_message)
        except:
            QMessageBox.warning(self, 'Ошибка', 'Ошибка подключения к серверу')

    def open_main_window(self):
        self.main_window = MainWindow(self.email)
        self.main_window.show()
        self.hide()

class MainWindow(QMainWindow):
    def __init__(self, email):
        super().__init__()
        self.email = email
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Система управления складом')
        self.setGeometry(100, 100, 800, 600)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Приветствие
        welcome_label = QLabel(f"Добро пожаловать, {self.email}!")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet("font-size: 24px; margin: 20px;")
        layout.addWidget(welcome_label)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec()) 