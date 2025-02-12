from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, EmailStr
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import config
from contextlib import asynccontextmanager
from datetime import datetime
import redis
from time import time

# Инициализация Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Константы для ограничения
GLOBAL_REQUEST_LIMIT = 10
LOGIN_REQUEST_LIMIT = 3
REGISTER_REQUEST_LIMIT = 1
VERIFY_REQUEST_LIMIT = 3  # Добавлено ограничение на попытки ввода кода
TIME_WINDOW = 60  # 60 секунд

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# Модели данных Pydantic для валидации
class UserRegister(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class VerifyCode(BaseModel):
    email: EmailStr
    code: str

# Класс для работы с БД через контекстный менеджер
class Database:
    def __init__(self, db_name: str = config.DATABASE_NAME):
        self.db_name = db_name

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_name)
        self.conn.row_factory = sqlite3.Row
        return self.conn.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.commit()
        self.conn.close()

def init_db():
    with Database() as cursor:
        cursor.execute('''CREATE TABLE IF NOT EXISTS users
                         (email TEXT PRIMARY KEY, 
                          password TEXT,
                          verification_code TEXT,
                          code_created_at TIMESTAMP,
                          last_code_request TIMESTAMP)''')

def hash_password(password: str) -> str:
    return password

def generate_verification_code() -> str:
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

async def send_verification_email(email: str, code: str) -> bool:
    try:
        msg = MIMEMultipart()
        msg['From'] = config.SMTP_EMAIL
        msg['To'] = email
        msg['Subject'] = "Код подтверждения"
        
        message = f"Ваш код подтверждения: {code}"
        msg.attach(MIMEText(message, 'plain', 'utf-8'))

        server = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT)
        server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Код подтверждения {code} отправлен на {email}")
        return True
    except Exception as e:
        print("Ошибка отправки email:", e)
        return False

async def can_request_new_code(email: str) -> bool:
    with Database() as cursor:
        cursor.execute(
            'SELECT last_code_request FROM users WHERE email = ?',
            (email,)
        )
        result = cursor.fetchone()
        if not result or not result['last_code_request']:
            return True
            
        last_request = datetime.fromisoformat(result['last_code_request'])
        time_passed = datetime.now() - last_request
        return time_passed.total_seconds() >= 60  # 60 секунд задержка

def check_rate_limit(ip_address: str, endpoint: str, limit: int) -> bool:
    key = f"{endpoint}:{ip_address}"
    request_count = redis_client.get(key)

    if request_count is None:
        redis_client.set(key, 1, ex=TIME_WINDOW)
    else:
        request_count = int(request_count)
        if request_count >= limit:
            return False
        redis_client.incr(key)
    
    return True

@app.post("/register")
async def register(user: UserRegister, request: Request):
    ip_address = request.client.host  # Получаем IP-адрес клиента

    if not check_rate_limit(ip_address, "register", REGISTER_REQUEST_LIMIT):
        raise HTTPException(
            status_code=429,
            detail="Слишком много регистраций. Пожалуйста, подождите перед следующей попыткой."
        )

    with Database() as cursor:
        cursor.execute('SELECT email FROM users WHERE email = ?', (user.email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Email уже зарегистрирован"
            )
            
        try:
            cursor.execute(
                'INSERT INTO users (email, password) VALUES (?, ?)',
                (user.email, user.password)
            )
            print(f"Зарегистрирован новый пользователь: {user.email}")
            return {"message": "Регистрация прошла успешно"}  # Успешный ответ
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail="Registration failed"
            )

@app.post("/login")
async def login(user: UserLogin, request: Request):
    ip_address = request.client.host  # Получаем IP-адрес клиента

    if not check_rate_limit(ip_address, "login", LOGIN_REQUEST_LIMIT):
        raise HTTPException(
            status_code=429,
            detail="Слишком много запросов на вход. Пожалуйста, подождите перед следующей попыткой."
        )

    with Database() as cursor:
        cursor.execute(
            'SELECT password FROM users WHERE email = ?',
            (user.email,)
        )
        result = cursor.fetchone()

        if not result:
            raise HTTPException(
                status_code=401,
                detail="Неверный логин или пароль"
            )

        if result['password'] == user.password:
            if not await can_request_new_code(user.email):
                raise HTTPException(
                    status_code=429,
                    detail="Подождите 60 секунд перед повторной отправкой кода"
                )

            verification_code = generate_verification_code()
            current_time = datetime.now().isoformat()
            
            cursor.execute(
                '''UPDATE users 
                   SET verification_code = ?, 
                       code_created_at = ?,
                       last_code_request = ?
                   WHERE email = ?''',
                (verification_code, current_time, current_time, user.email)
            )
            
            if await send_verification_email(user.email, verification_code):
                return {"message": "Код для входа отправлен на ваш email"}  # Успешный ответ
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Ошибка отправки кода"
                )
        else:
            raise HTTPException(
                status_code=401,
                detail="Неверный логин или пароль"
            )

@app.post("/verify")
async def verify_code(verify: VerifyCode, request: Request):
    ip_address = request.client.host  # Получаем IP-адрес клиента

    if not check_rate_limit(ip_address, "verify", VERIFY_REQUEST_LIMIT):
        raise HTTPException(
            status_code=429,
            detail="Слишком много попыток ввода кода. Пожалуйста, подождите перед следующей попыткой."
        )

    with Database() as cursor:
        cursor.execute(
            '''SELECT verification_code, code_created_at 
               FROM users WHERE email = ?''',
            (verify.email,)
        )
        result = cursor.fetchone()
        
        if not result or not result['verification_code']:
            raise HTTPException(
                status_code=404,
                detail="Код подтверждения не найден"
            )

        # Проверяем срок действия кода (5 минут)
        code_created = datetime.fromisoformat(result['code_created_at'])
        time_passed = datetime.now() - code_created
        if time_passed.total_seconds() > 300:  # 300 секунд = 5 минут
            cursor.execute(
                'UPDATE users SET verification_code = NULL WHERE email = ?',
                (verify.email,)
            )
            raise HTTPException(
                status_code=400,
                detail="Срок действия кода истек"
            )
        
        if result['verification_code'] == verify.code:
            cursor.execute(
                'UPDATE users SET verification_code = NULL WHERE email = ?',
                (verify.email,)
            )
            return {"message": "Verification successful"}  # Успешный ответ
        else:
            raise HTTPException(
                status_code=401,
                detail="Неверный код подтверждения"
            )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
