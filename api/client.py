import requests
import os
from typing import Optional
from config.settings import API_URL
import sqlite3
from config.settings import DB_PATH

# API_URL = os.getenv("API_URL", "https://example.com/api")
LOGIN_ENDPOINT = "/auth/token/"
HEADERS = {"Content-Type": "application/json"}

class APIClient:
    def __init__(self):
        self.access_token = None
        self.refresh_token = None

    def login(self, username, password):
        """Авторизация пользователя и извлечение токенов из куки."""
        url = f"{API_URL}/auth/token/"
        payload = {"email": username, "password": password}
        session = requests.Session()
        response = session.post(url, json=payload)

        if response.status_code == 200:
            # Извлекаем токены из куки
            cookies = session.cookies.get_dict()
            access_token = cookies.get("access_token")
            refresh_token = cookies.get("refresh_token")

            if access_token and refresh_token:
                return {"access_token": access_token, "refresh_token": refresh_token}
            else:
                raise ValueError("Токены отсутствуют в куки")

        return None

    def refresh_tokens(self) -> bool:
        """Обновление токенов с использованием refresh-токена."""
        if not self.refresh_token:
            return False
        
        response = requests.post(
            f"{API_URL}/auth/token/refresh/",
            json={"refresh": self.refresh_token},
            headers=HEADERS,
        )
        
        if response.status_code == 200:
            self.access_token = response.json().get("access")
            return True
        return False

    def request(self, method: str, endpoint: str, data: Optional[dict] = None) -> Optional[dict]:
        """Отправка запроса к API."""
        if not self.access_token:
            return None
        
        headers = {**HEADERS, "Authorization": f"Bearer {self.access_token}"}
        url = f"{API_URL}{endpoint}"
        response = requests.request(method, url, json=data, headers=headers)
        
        if response.status_code == 401:  # Unauthorized, пробуем обновить токен
            if self.refresh_tokens():
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = requests.request(method, url, json=data, headers=headers)
        
        if response.status_code in [200, 201]:
            return response.json()
        return None


    def get_dashboard(self, telegram_id: int, start_date: str, end_date: str):
        """Запрашивает дашборд за указанный период."""
        url = f"{API_URL}/settings_site/dashboard/"
        tokens = self.get_user_tokens(telegram_id)

        if not tokens:
            raise ValueError("Пользователь не авторизован в боте.")

        access_token, refresh_token = tokens

        # Формируем куки для запроса
        cookies = {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
        payload = {"date_in": start_date, "date_out": end_date}

        # Отправляем запрос
        response = requests.post(url, json=payload, cookies=cookies)


        # Если токен истёк, пробуем обновить
        if response.status_code == 401:
            self.refresh_access_token(telegram_id)
            tokens = self.get_user_tokens(telegram_id)
            if not tokens:
                raise ValueError("Не удалось обновить токен. Требуется повторная авторизация.")
            access_token, refresh_token = tokens
            cookies = {
                "access_token": access_token,
                "refresh_token": refresh_token
            }
            response = requests.post(url, json=payload, cookies=cookies)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise ValueError("Доступ запрещён. Требуется авторизация.")
        else:
            response.raise_for_status()

        return {}

    def get_user_tokens(self, telegram_id: int):
        """Получает токены пользователя из базы данных."""
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT access_token, refresh_token FROM users WHERE telegram_id = ?", (telegram_id,))
        result = cursor.fetchone()
        conn.close()
        return result if result else None
        
    def update_cookies(self, new_cookies):
        """Обновляет куки для последующих запросов."""
        self.session_cookies.update(new_cookies)

    def get_headers(self, telegram_id: int):
        """Возвращает заголовки с токенами."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT access_token FROM users WHERE telegram_id = ?", (telegram_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            access_token = result[0]
            return {"Authorization": f"Bearer {access_token}"}
        return {}

    def refresh_access_token(self, telegram_id: int):
        """Обновляет access_token с использованием refresh_token."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT refresh_token FROM users WHERE telegram_id = ?", (telegram_id,))
        result = cursor.fetchone()

        if result:
            refresh_token = result[0]
            url = f"{API_URL}/refresh"
            response = requests.post(url, json={"refresh_token": refresh_token})
            if response.status_code == 200:
                new_access_token = response.json().get("access_token")
                cursor.execute("UPDATE users SET access_token = ? WHERE telegram_id = ?", (new_access_token, telegram_id))
                conn.commit()

        conn.close()

    def get_orders(self, telegram_id: int, page: int):
        """Получение списка заказов."""
        # order/list/1/
        url = f"{API_URL}/order/list/{page}/"
        tokens = self.get_user_tokens(telegram_id)
        if not tokens:
            raise ValueError("Пользователь не авторизован в боте.")
        access_token, refresh_token = tokens
        # Формируем куки для запроса
        cookies = {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
        response = requests.get(url, cookies=cookies)
        if response.status_code == 401:
            # Если токен истёк, обновляем куки
            self.refresh_access_token(telegram_id)
            cookies = self.get_cookies(telegram_id)
            response = requests.get(url, cookies=cookies)
        response.raise_for_status()  # Бросает исключение, если код ответа не 2xx
        return response.json()

    def get_order_details(self, telegram_id: int, order_id: int):
        """Получение деталей заказа."""
        url = f"{API_URL}/order/detail/{order_id}/"
        tokens = self.get_user_tokens(telegram_id)
        if not tokens:
            raise ValueError("Пользователь не авторизован в боте.")
        access_token, refresh_token = tokens
        # Формируем куки для запроса
        cookies = {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
        response = requests.get(url, cookies=cookies)
        if response.status_code == 401:
            # Если токен истёк, обновляем куки
            self.refresh_access_token(telegram_id)
            cookies = self.get_cookies(telegram_id)
            response = requests.get(url, cookies=cookies)
        response.raise_for_status()  # Бросает исключение, если код ответа не 2xx
        return response.json()

    def get_applications(self, telegram_id: int, page: int):
        """Получает список заявок с пагинацией."""
        url = f"{API_URL}/feedback/list/{page}/"
        cookies = self.get_cookies(telegram_id)  # Получаем авторизационные куки из базы
        response = requests.get(url, cookies=cookies)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:  # Если токен истёк
            self.refresh_access_token(telegram_id)  # Обновляем токен
            cookies = self.get_cookies(telegram_id)  # Получаем обновлённые куки
            response = requests.get(url, cookies=cookies)
            if response.status_code == 200:
                return response.json()
        return {}

    def get_application_details(self, telegram_id: int, application_id: int):
        """Получает детали конкретной заявки."""
        url = f"{API_URL}/feedback/request/{application_id}/"
        cookies = self.get_cookies(telegram_id)  # Получаем авторизационные куки из базы
        response = requests.get(url, cookies=cookies)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:  # Если токен истёк
            self.refresh_access_token(telegram_id)  # Обновляем токен
            cookies = self.get_cookies(telegram_id)  # Получаем обновлённые куки
            response = requests.get(url, cookies=cookies)
            if response.status_code == 200:
                return response.json()
        return {}

    def get_cookies(self, telegram_id: int):
        """Получает авторизационные куки пользователя из базы данных."""
        tokens = self.get_user_tokens(telegram_id)
        access_token, refresh_token = tokens
        if access_token and refresh_token:
            return {
                "access_token": access_token,
                "refresh_token": refresh_token
            }
        raise ValueError("Пользователь не авторизован")

    def get_supplier_import(self, telegram_id: int, supplier_slug: str):
        """Получает информацию об импорте поставщика."""
        url = f"{API_URL}/product_import_manager/supplier_import/"
        cookies = self.get_cookies(telegram_id)
        payload = {"slug": supplier_slug}  # Передача slug в теле запроса

        response = requests.post(url, json=payload, cookies=cookies)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:  # Если токен истёк
            self.refresh_access_token(telegram_id)
            cookies = self.get_cookies(telegram_id)
            response = requests.post(url, json=payload, cookies=cookies)
            if response.status_code == 200:
                return response.json()
        return {}

    def update_supplier_settings(self, telegram_id: int, supplier_slug: str, extra_charge: float):
        """Изменяет настройки поставщика."""
        url = f"{API_URL}/product_import_manager/supplier_import/"
        cookies = self.get_cookies(telegram_id)
        payload = {"slug": supplier_slug, "extra_charge": extra_charge}
        print(f'{payload=}')
        response = requests.put(url, json=payload, cookies=cookies)
        if response.status_code == 200:
            print(f'{response.json()=}')
            return response.json()
        elif response.status_code == 401:  # Если токен истёк
            self.refresh_access_token(telegram_id)
            cookies = self.get_cookies(telegram_id)
            response = requests.put(url, json=payload, cookies=cookies)
            if response.status_code == 200:
                return response.json()
        return {"status": "error"}