import json
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

CMS_URL = "https://my.prom.ua/cms/"
SESSION_PATH = os.environ.get("PROM_SESSION_PATH", "prom_cookies.json")


def _driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=old")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    if os.path.exists("/usr/bin/chromium"):
        options.binary_location = "/usr/bin/chromium"
    if os.path.exists("/usr/bin/chromedriver"):
        return webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)
    return webdriver.Chrome(options=options)


def _first_visible(driver, selectors):
    for by, selector in selectors:
        for element in driver.find_elements(by, selector):
            if element.is_displayed():
                return element
    return None


def _looks_authorized(driver):
    url = (driver.current_url or "").lower()
    if "my.prom.ua/cms" not in url:
        return False
    body = driver.find_element(By.TAG_NAME, "body").text.lower()
    login_markers = ("увійти", "войти", "sign in", "пароль", "password")
    return not any(marker in body[:3000] for marker in login_markers)


def _save_session(driver):
    cookies = driver.get_cookies()
    if not cookies:
        raise RuntimeError("Prom не повернув cookies сесії.")
    directory = os.path.dirname(os.path.abspath(SESSION_PATH))
    os.makedirs(directory, exist_ok=True)
    temp_path = SESSION_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as fh:
        json.dump(cookies, fh, ensure_ascii=False, indent=2)
    os.replace(temp_path, SESSION_PATH)
    try:
        os.chmod(SESSION_PATH, 0o600)
    except OSError:
        pass


def session_status():
    if os.path.exists(SESSION_PATH) and os.path.getsize(SESSION_PATH) > 2:
        return {"authorized": True, "message": "Сесію Prom збережено."}
    secret = "/etc/secrets/prom_cookies.json"
    if os.path.exists(secret) and os.path.getsize(secret) > 2:
        return {"authorized": True, "message": "Сесію Prom підключено через Secret File."}
    return {"authorized": False, "message": "Prom ще не авторизовано."}


def login_and_save(login, password):
    login = str(login or "").strip()
    password = str(password or "")
    if not login or not password:
        raise ValueError("Введіть логін і пароль Prom.")

    driver = _driver()
    try:
        driver.get(CMS_URL)
        time.sleep(2)
        if _looks_authorized(driver):
            _save_session(driver)
            return {"authorized": True, "message": "Prom уже авторизовано. Сесію збережено."}

        login_input = _first_visible(driver, [
            (By.CSS_SELECTOR, 'input[type="email"]'),
            (By.CSS_SELECTOR, 'input[name="email"]'),
            (By.CSS_SELECTOR, 'input[name="login"]'),
            (By.CSS_SELECTOR, 'input[name="username"]'),
            (By.CSS_SELECTOR, 'input[type="text"]'),
        ])
        if not login_input:
            raise RuntimeError("Не знайшла поле логіна Prom. Потрібно адаптувати форму авторизації до поточної сторінки Prom.")
        login_input.clear()
        login_input.send_keys(login)

        password_input = _first_visible(driver, [
            (By.CSS_SELECTOR, 'input[type="password"]'),
            (By.CSS_SELECTOR, 'input[name="password"]'),
        ])

        if not password_input:
            next_button = _first_visible(driver, [
                (By.CSS_SELECTOR, 'button[type="submit"]'),
                (By.XPATH, "//button[contains(., 'Далі') or contains(., 'Продолжить') or contains(., 'Увійти') or contains(., 'Войти')]")
            ])
            if next_button:
                next_button.click()
                time.sleep(2)
                password_input = _first_visible(driver, [
                    (By.CSS_SELECTOR, 'input[type="password"]'),
                    (By.CSS_SELECTOR, 'input[name="password"]'),
                ])

        if not password_input:
            raise RuntimeError("Не знайшла поле пароля Prom після введення логіна.")
        password_input.clear()
        password_input.send_keys(password)

        submit = _first_visible(driver, [
            (By.CSS_SELECTOR, 'button[type="submit"]'),
            (By.XPATH, "//button[contains(., 'Увійти') or contains(., 'Войти') or contains(., 'Sign in')]")
        ])
        if not submit:
            raise RuntimeError("Не знайшла кнопку входу Prom.")
        submit.click()

        deadline = time.time() + 25
        while time.time() < deadline:
            time.sleep(1)
            if _looks_authorized(driver):
                _save_session(driver)
                return {"authorized": True, "message": "Prom авторизовано. Сесію збережено."}

        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        if any(x in body for x in ("код", "підтвер", "подтверж", "verification", "2fa")):
            raise RuntimeError("Prom запросив додаткове підтвердження входу. Потрібно додати крок для коду підтвердження.")
        raise RuntimeError("Prom не підтвердив авторизацію. Перевірте логін/пароль або спосіб входу.")
    finally:
        driver.quit()
