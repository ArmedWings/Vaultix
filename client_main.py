import sys
from PyQt6.QtWidgets import QApplication
from client.login_window import LoginWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    login_window = LoginWindow()
    
    # Проверяем сессию перед показом окна
    if not login_window.check_saved_session():
        login_window.show()
    
    sys.exit(app.exec()) 