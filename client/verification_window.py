from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                            QLabel, QPushButton, QLineEdit, QMessageBox)
from PyQt6.QtCore import Qt, QTimer
import requests
import client_config as client_config
from client.token_storage import TokenStorage

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
        # Импортируем здесь для избежания циклического импорта
        from .main_window import MainWindow
        self.main_window = MainWindow(email)
        self.main_window.show()
        self.hide() 