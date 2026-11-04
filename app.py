import glob
import json
import os
import time
import traceback
import threading
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template_string, request
import pandas as pd

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

app = Flask(__name__)
process_lock = threading.Lock()

process_status = {
    "running": False,
    "process_num": None,
    "status": "idle",
    "message": "",
}


# ============================================================
# GOOGLE SHEETS
# ============================================================

def _resolve_secret_path(filename):
    render_secret_path = f"/etc/secrets/{filename}"
    if os.path.exists(render_secret_path):
        return render_secret_path
    return filename


def get_gspread_client():
    creds = None
    token_path = _resolve_secret_path("token.json")

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise FileNotFoundError(
                "Файл token.json не знайдено. Додайте його в Render "
                "у розділі Environment → Secret Files."
            )

    return gspread.authorize(creds)


def ensure_capacity(sheet, required_rows):
    if sheet.row_count < required_rows:
        sheet.add_rows(max(1000, required_rows - sheet.row_count))


def remove_data_validation(sheet, start_row, start_col, end_row, end_col):
    body = {
        "requests": [
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet.id,
                        "startRowIndex": start_row - 1,
                        "endRowIndex": end_row,
                        "startColumnIndex": start_col - 1,
                        "endColumnIndex": end_col,
                    },
                    "rule": None,
                }
            }
        ]
    }

    try:
        sheet.spreadsheet.batch_update(body)
    except Exception:
        pass


# ============================================================
# SELENIUM HELPERS
# ============================================================

def safe_click(driver, element):
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            element,
        )
        time.sleep(0.3)
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)


def wait_for_crm_loader(driver, timeout=120):
    time.sleep(1.5)

    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located(
                (
                    By.XPATH,
                    "//div[contains(@class,'loading') "
                    "or contains(@class,'spinner') "
                    "or contains(@class,'overlay') "
                    "or contains(@class,'loader')]",
                )
            )
        )
    except Exception:
        pass


def clear_all_filters(driver, timeout=45):
    wait_for_crm_loader(driver, timeout=timeout)

    reset_xpaths = [
        "//button[contains(translate(text(), 'ФІЛЬТРУВАТИ', "
        "'фільтрувати'), 'фільтр')]/following-sibling::button"
        "[contains(text(), 'x') or contains(text(), 'X') or contains(text(), '×')]",
        "//button[contains(translate(text(), 'ФІЛЬТРУВАТИ', "
        "'фільтрувати'), 'фільтр')]/following-sibling::*[1]",
        "//button[text()='x' or text()='X' or text()='×']",
        "//button[contains(@class, 'reset') or contains(@class, 'clear')]",
    ]

    clicked = False

    for _ in range(4):
        for xpath in reset_xpaths:
            try:
                for element in driver.find_elements(By.XPATH, xpath):
                    if element.is_displayed():
                        safe_click(driver, element)
                        clicked = True
                        break

                if clicked:
                    break

            except StaleElementReferenceException:
                continue

        if clicked:
            break

        time.sleep(1)

    if not clicked:
        driver.execute_script("""
            var btns = document.querySelectorAll('button');

            for (var i = 0; i < btns.length; i++) {
                var txt = btns[i].innerText.trim();

                if (txt === 'x' || txt === 'X' || txt === '×') {
                    btns[i].click();
                    break;
                }
            }
        """)

    time.sleep(2)
    wait_for_crm_loader(driver, timeout=timeout)


def find_date_input(driver, keywords):
    for keyword in keywords:
        keyword_lower = keyword.lower()

        xpaths = [
            f"//label[contains(translate(text(), "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ', "
            f"'abcdefghijklmnopqrstuvwxyzабвгґдеєжзиіїйклмнопрстуфхцчшщьюя'), "
            f"'{keyword_lower}')]/following-sibling::input",

            f"//label[contains(translate(text(), "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ', "
            f"'abcdefghijklmnopqrstuvwxyzабвгґдеєжзиіїйклмнопрстуфхцчшщьюя'), "
            f"'{keyword_lower}')]/..//input",

            f"//input[contains(translate(@placeholder, "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ', "
            f"'abcdefghijklmnopqrstuvwxyzабвгґдеєжзиіїйклмнопрстуфхцчшщьюя'), "
            f"'{keyword_lower}')]",
        ]

        for xpath in xpaths:
            try:
                for element in driver.find_elements(By.XPATH, xpath):
                    if element.is_displayed():
                        return element
            except StaleElementReferenceException:
                continue

    return None


def select_date_preset(driver, input_element, preset_name="Сьогодні"):
    safe_click(driver, input_element)
    time.sleep(1)

    for button in driver.find_elements(
        By.XPATH,
        f"//*[contains(text(), '{preset_name}') "
        f"or contains(text(), '{preset_name.lower()}')]",
    ):
        try:
            if button.is_displayed():
                safe_click(driver, button)
                break
        except StaleElementReferenceException:
            continue

    time.sleep(0.5)


def set_custom_date_range(
    driver,
    input_element,
    start_date_str,
    end_date_str=None,
):
    safe_click(driver, input_element)
    time.sleep(1)

    def force_set_value(element, date_str):
        driver.execute_script(
            "arguments[0].focus(); arguments[0].value = '';",
            element,
        )

        element.send_keys(Keys.CONTROL + "a")
        element.send_keys(Keys.BACKSPACE)
        element.send_keys(date_str)

        driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
            "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
            element,
            date_str,
        )

    start_inputs = driver.find_elements(
        By.XPATH,
        "//label[contains(text(),'Початкова')]/following-sibling::input "
        "| //input[contains(@placeholder,'Початкова')]",
    )

    if start_inputs:
        force_set_value(start_inputs[0], start_date_str)
    else:
        force_set_value(input_element, start_date_str)

    time.sleep(0.4)

    if end_date_str:
        end_inputs = driver.find_elements(
            By.XPATH,
            "//label[contains(text(),'Кінцева')]/following-sibling::input "
            "| //input[contains(@placeholder,'Кінцева')]",
        )

        if end_inputs:
            force_set_value(end_inputs[0], end_date_str)
            time.sleep(0.4)

    for button in driver.find_elements(
        By.XPATH,
        "//*[contains(text(), 'ВИБРАТИ') "
        "or contains(text(), 'Применить')]",
    ):
        try:
            if button.is_displayed():
                safe_click(driver, button)
                break
        except StaleElementReferenceException:
            continue

    time.sleep(0.5)


# ============================================================
# ЗАВАНТАЖЕННЯ ЗВІТУ З ASTERIL CRM
# Процес 2 видалено. Залишено типи 1 та 3.
# ============================================================

def download_report_from_asteril(
    domain_url,
    process_type,
    download_dir="temp_downloads",
    selected_date=None,
):
    if process_type not in (1, 3):
        raise ValueError(
            f"Невідомий тип завантаження звіту: {process_type}"
        )

    os.makedirs(download_dir, exist_ok=True)

    for file_path in glob.glob(os.path.join(download_dir, "*")):
        try:
            os.remove(file_path)
        except Exception:
            pass

    cookies_file = _resolve_secret_path("asteril_cookies.json")

    if not os.path.isabs(cookies_file):
        cookies_file = os.path.abspath(cookies_file)

    chrome_options = webdriver.ChromeOptions()
    chrome_options.set_capability(
        "goog:loggingPrefs",
        {"browser": "ALL", "performance": "ALL"},
    )

    chrome_options.add_argument("--headless=old")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1024,768")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-translate")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--metrics-recording-only")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument(
        "--disable-features=VizDisplayCompositor,TranslateUI"
    )
    chrome_options.add_argument("--renderer-process-limit=1")
    chrome_options.add_argument("--disk-cache-size=0")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--js-flags=--max-old-space-size=64")
    chrome_options.add_argument("--disable-accelerated-2d-canvas")
    chrome_options.add_argument("--no-zygote")

    system_chrome_bin = "/usr/bin/chromium"
    system_chromedriver_bin = "/usr/bin/chromedriver"

    if os.path.exists(system_chrome_bin):
        chrome_options.binary_location = system_chrome_bin

    prefs = {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "profile.managed_default_content_settings.images": 2,
    }

    chrome_options.add_experimental_option("prefs", prefs)

    if os.path.exists(system_chromedriver_bin):
        driver = webdriver.Chrome(
            service=Service(system_chromedriver_bin),
            options=chrome_options,
        )
    else:
        driver = webdriver.Chrome(options=chrome_options)

    abs_download_path = os.path.abspath(download_dir)

    try:
        try:
            driver.execute_cdp_cmd(
                "Page.setDownloadBehavior",
                {
                    "behavior": "allow",
                    "downloadPath": abs_download_path,
                },
            )
        except Exception as error:
            print(
                "=== ДІАГНОСТИКА: Page.setDownloadBehavior: "
                f"{error} ==="
            )

        try:
            driver.execute_cdp_cmd(
                "Browser.setDownloadBehavior",
                {
                    "behavior": "allow",
                    "downloadPath": abs_download_path,
                    "eventsEnabled": True,
                },
            )
        except Exception as error:
            print(
                "=== ДІАГНОСТИКА: Browser.setDownloadBehavior: "
                f"{error} ==="
            )

        wait = WebDriverWait(driver, 45)

        if not domain_url.startswith("http"):
            domain_url = "https://" + domain_url

        driver.get(domain_url)
        time.sleep(3)

        if os.path.exists(cookies_file):
            print(
                f"=== ДІАГНОСТИКА: знайдено cookies_file: "
                f"{cookies_file} ==="
            )

            try:
                with open(cookies_file, "r") as file:
                    raw_cookies = json.load(file)

                print(f"Кукі у файлі: {len(raw_cookies)}")
                added = 0
                failed = 0

                for cookie in raw_cookies:
                    cookie.pop("sameSite", None)

                    try:
                        driver.add_cookie(cookie)
                        added += 1
                    except Exception:
                        failed += 1

                print(
                    f"Додано успішно: {added}, не вдалось: {failed}"
                )

                driver.refresh()
                time.sleep(3)

            except Exception as error:
                print(
                    "=== ДІАГНОСТИКА: помилка читання cookies_file: "
                    f"{error} ==="
                )

        else:
            print(
                "=== ДІАГНОСТИКА: файл cookies НЕ знайдено: "
                f"{cookies_file} ==="
            )

        orders_url = (
            domain_url
            if domain_url.endswith("/orders")
            else domain_url.rstrip("/") + "/orders"
        )

        if driver.current_url.rstrip("/") != orders_url.rstrip("/"):
            driver.get(orders_url)

        if "login" in driver.current_url:
            print(
                "=== Кукі не авторизували сесію — виконуємо логін ==="
            )

            asteril_login = os.environ.get("ASTERIL_LOGIN")
            asteril_password = os.environ.get("ASTERIL_PASSWORD")

            if not asteril_login or not asteril_password:
                raise RuntimeError(
                    "Не задано ASTERIL_LOGIN / ASTERIL_PASSWORD "
                    "у змінних середовища Render."
                )

            email_input = wait.until(
                EC.presence_of_element_located((By.NAME, "email"))
            )

            password_input = driver.find_element(By.NAME, "password")

            email_input.clear()
            email_input.send_keys(asteril_login)

            password_input.clear()
            password_input.send_keys(asteril_password)

            driver.find_element(
                By.XPATH,
                "//button[@type='submit']",
            ).click()

            wait.until(lambda current_driver: "login" not in current_driver.current_url)
            time.sleep(2)

            if driver.current_url.rstrip("/") != orders_url.rstrip("/"):
                driver.get(orders_url)

        try:
            wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//button[contains(translate(text(), "
                        "'ФІЛЬТРУВАТИ', 'фільтрувати'), 'фільтр')] "
                        "| //button[contains(@class, 'filter')]",
                    )
                )
            )
        except TimeoutException:
            print("=== ДІАГНОСТИКА: не дочекались кнопки фільтра ===")
            raise

        time.sleep(2)
        clear_all_filters(driver, timeout=45)

        today = datetime.now()

        if process_type == 1:
            try:
                for button in driver.find_elements(
                    By.XPATH,
                    "//a[contains(text(), 'Усе') or contains(text(), 'Все')]",
                ):
                    if button.is_displayed():
                        safe_click(driver, button)
                        time.sleep(1.5)
                        break
            except Exception:
                pass

            deadline_input = find_date_input(
                driver,
                ["крайній термін", "deadline", "термін відправки"],
            )

            if deadline_input:
                select_date_preset(
                    driver,
                    deadline_input,
                    "Сьогодні",
                )

        elif process_type == 3:
            selected_date_str = (
                selected_date
                if selected_date
                else (today - timedelta(days=7)).strftime("%d.%m.%Y")
            )

            try:
                for button in driver.find_elements(
                    By.XPATH,
                    "//a[contains(text(), 'Усе') or contains(text(), 'Все')]",
                ):
                    if button.is_displayed():
                        safe_click(driver, button)
                        time.sleep(1.5)
                        break
            except Exception:
                pass

            date_create_input = find_date_input(
                driver,
                ["дата створення", "created_at", "створення"],
            )

            if date_create_input:
                set_custom_date_range(
                    driver,
                    date_create_input,
                    selected_date_str,
                    selected_date_str,
                )

        filter_btn = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[contains(translate(text(), "
                    "'ФІЛЬТРУВАТИ', 'фільтрувати'), 'фільтр')]",
                )
            )
        )

        safe_click(driver, filter_btn)
        time.sleep(4)
        wait_for_crm_loader(driver, timeout=60)

        try:
            row_count = len(
                driver.find_elements(
                    By.CSS_SELECTOR,
                    "#ajax-table tbody tr",
                )
            )
            print(
                "=== ДІАГНОСТИКА: рядків у таблиці після фільтра: "
                f"{row_count} ==="
            )
        except Exception as error:
            print(
                f"=== ДІАГНОСТИКА: не вдалось порахувати рядки: "
                f"{error} ==="
            )

        excel_button = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//button[.//i[contains(@class, 'icon-file-excel')]]",
                )
            )
        )

        print(
            "=== ДІАГНОСТИКА: знайдено кнопку Excel — "
            f"outerHTML='{excel_button.get_attribute('outerHTML')}' ==="
        )

        try:
            driver.get_log("browser")
        except Exception:
            pass

        driver.execute_script("arguments[0].click();", excel_button)

        print(
            "=== ДІАГНОСТИКА: клік по Excel виконано, "
            "чекаємо модальне вікно експорту ==="
        )

        try:
            regular_export_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//button[contains(translate(text(), "
                        "'звичайний', 'ЗВИЧАЙНИЙ'), 'ЗВИЧАЙНИЙ')]",
                    )
                )
            )

            driver.execute_script(
                "arguments[0].click();",
                regular_export_btn,
            )

            print(
                "=== ДІАГНОСТИКА: кнопку 'ЗВИЧАЙНИЙ' натиснуто ==="
            )

        except Exception as error:
            print(
                "=== ДІАГНОСТИКА: модальне вікно не з'явилось "
                f"або кнопку не знайдено: {error} ==="
            )

        time.sleep(3)

        try:
            browser_logs = driver.get_log("browser")
            severe_logs = [
                entry
                for entry in browser_logs
                if entry.get("level") == "SEVERE"
            ]

            print(
                f"=== ДІАГНОСТИКА: записів консолі: "
                f"{len(browser_logs)}, SEVERE: {len(severe_logs)} ==="
            )

            for entry in severe_logs[:5]:
                print(f"  [SEVERE] {entry.get('message')}")

        except Exception as error:
            print(
                "=== ДІАГНОСТИКА: не вдалось отримати логи: "
                f"{error} ==="
            )

        downloaded_file = None

        for i in range(120):
            time.sleep(1)

            files = (
                glob.glob(os.path.join(download_dir, "*.xlsx"))
                + glob.glob(os.path.join(download_dir, "*.xls"))
                + glob.glob(os.path.join(download_dir, "*.csv"))
            )

            temp_files = (
                glob.glob(os.path.join(download_dir, "*.crdownload"))
                + glob.glob(os.path.join(download_dir, "*.tmp"))
            )

            if i in (4, 14, 29, 59, 89) or (
                i % 30 == 0 and i > 0
            ):
                print(
                    f"=== ДІАГНОСТИКА: [{i + 1}с] вміст "
                    f"{download_dir}: {os.listdir(download_dir)} ==="
                )

            if files and not temp_files:
                downloaded_file = files[0]
                break

        if not downloaded_file:
            print(
                "=== ДІАГНОСТИКА: поточний URL перед помилкою: "
                f"{driver.current_url} ==="
            )
            raise TimeoutError(
                "Файл не завантажився в temp_downloads за 120 секунд."
            )

        return downloaded_file

    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ============================================================
# ПРОЦЕС 1 — КТВ
# ============================================================

def process_one(export_mode="partial"):
    input_file = download_report_from_asteril(
        "https://crm2006091.asteril.com/orders",
        process_type=1,
    )

    df = pd.read_excel(input_file)

    allowed_statuses = [
        "Перевірити перед відправкою58",
        "Термінові (з 9 до 14)",
        "Військовим",
        "З ттн",
        "Не переробляти ттн",
        "Не переробляти ттн (термінові)",
        "Пром оплата",
        "Замовлення з ДОК",
        "Віділення розетки",
        "Укрпошта Відправити",
        "Укрпошта Запаковано",
        "Укрпошта ВІП",
        "укр відправити(промоплата)",
        "А 1",
        "ВІП УКР",
        "А 0",
        "А 2",
        "А 3",
        "А 4",
        "А 5",
        "А 6",
        "А 7",
        "А 8",
        "А 9",
        "А10",
        "А11",
        "А12",
        "А13 (мінуса)",
        "А14 (С.С перевірка)",
        "А 15",
        "А16",
        "А17",
        "А18",
        "А19",
        "А20",
        "Одиночні",
        "Двійні",
        "Товар",
        "Комп'ютер 9(РБ)",
        "Комп'ютер 10 (Рокса)",
        "Комп'ютер 1 (Ілля)",
        "Комп'ютер 2 (Славік)",
        "Комп'ютер 3 (Віталій М )",
        "Комп'ютер 4 (Мар'ян)",
        "Комп'ютер 5 (Богдан)",
        "Комп'ютер 6 (Олександр Сільченко)",
        "Комп'ютер 7 (Валя)",
        "Комп'ютер 8 ( Валентин)",
        "для тестування",
        "Пакування перевірка",
        "Сток",
        "Богдан(л1)",
        "Мар'ян",
        "Віталій М (л4)",
        "Ілля(л1)",
        "Славік(л2)",
        "Сашко Сільченко(л4)",
        "Валентин(л3)",
        "Рокса",
        "Валя",
        "Очікує 1 день",
        "Очікує 2 дні",
        "Очікує 3 дні",
        "Очікує 4 дні",
        "Очікує 5 днів",
        "Очікує 6 днів +",
    ]

    stores_to_remove = [
        "Mona Liza",
        "One Bird",
        "Dobromarket",
        "Shop-Market-Top",
        "Trendly",
        "HomeMix-дроп",
        "Інстаграм",
        "Marcat -дроп",
        "Заміна",
        "Довідправка",
        "Інстаграм ОМ",
        "Експрес-шоп -дроп",
        "Дроп Котик trendland",
        "Дроп Котик foxxi",
        "ClickMart Shop",
        "Дропшипінг",
        "Klik Shop - дроп",
        "самовивіз",
    ]

    allowed_utm = [
        "mobile_catalog_app",
        "portal",
        "bigl",
    ]

    df.columns = df.columns.str.strip()

    for required_column in ["Статус", "Магазин", "№", "utm_medium"]:
        if required_column not in df.columns:
            raise ValueError(
                f"У звіті Asteril немає необхідної колонки: "
                f"{required_column}"
            )

    df["Статус"] = df["Статус"].astype(str).str.strip()
    df["Магазин"] = df["Магазин"].astype(str).str.strip()
    df["utm_medium"] = df["utm_medium"].astype(str).str.strip()

    if "Upsale" in df.columns:
        upsale_clean = (
            df["Upsale"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        has_upsale = ~upsale_clean.isin(
            ["", "nan", "none", "null"]
        )
    else:
        has_upsale = pd.Series(False, index=df.index)

    base_mask = (
        df["Статус"].isin(allowed_statuses)
        & ~df["Магазин"].isin(stores_to_remove)
    )

    if export_mode == "partial":
        # Неповна вигрузка: замовлення впливають на рейтинг Prom
        # АБО мають Upsale.
        base_mask = base_mask & (
            df["utm_medium"].isin(allowed_utm)
            | has_upsale
        )

    elif export_mode == "full":
        # Повна вигрузка: усі дозволені статуси,
        # крім замовлень з виключених магазинів.
        pass

    else:
        raise ValueError(
            f"Невідомий режим вигрузки: {export_mode}"
        )

    filtered_df = df[base_mask].sort_values(
        by="Статус",
        ascending=True,
    )

    client = get_gspread_client()

    sheet = client.open_by_key(
        "1sNWKNZhmE-DXancPOX5RtLhtbQ_-ThwhfqlwyVmSzSE"
    ).worksheet("КТВ")

    raw_values = (
        filtered_df[["Магазин", "№", "Статус"]]
        .fillna("")
        .values
        .tolist()
    )

    if not raw_values:
        print(
            f"=== Процес 1: режим={export_mode}, "
            "замовлень для запису немає ==="
        )
        return 0

    first_free_row = max(
        len(sheet.col_values(1)),
        len(sheet.col_values(4)),
    ) + 1

    ensure_capacity(
        sheet,
        first_free_row + len(raw_values),
    )

    remove_data_validation(
        sheet,
        first_free_row,
        1,
        first_free_row,
        2,
    )

    sheet.update(
        range_name=f"A{first_free_row}",
        values=[[datetime.now().strftime("%d.%m")]],
    )

    sheet.update(
        range_name=(
            f"D{first_free_row + 1}:"
            f"F{first_free_row + len(raw_values)}"
        ),
        values=raw_values,
    )

    print(
        f"=== Процес 1: режим={export_mode}, "
        f"відібрано замовлень={len(filtered_df)} ==="
    )

    return len(filtered_df)


# ============================================================
# ПРОЦЕС 3 — ВІДГУКИ
# ============================================================

def process_three(selected_date=None):
    input_file = download_report_from_asteril(
        "https://crm2006091.asteril.com/orders",
        process_type=3,
        selected_date=selected_date,
    )

    df = pd.read_excel(input_file)

    allowed_statuses = [
        "добавляння ттн",
        "ПеревіркаПредоплат!",
        "Очікуємо на грошовий",
        "Перед.пл. 2026",
        "ФО 2026",
        "фо отримано (дроп)",
        "ФОотримано Укрпошта 2026",
        "ФО опт",
    ]

    stores_to_remove = [
        "Дроп Котик trendland",
        "ClickMart Shop",
        "Дроп Котик foxxi",
        "Mona Liza",
        "One Bird",
        "Best-Buy",
        "Home81",
        "Dobromarket",
        "Shop-Market-Top",
        "Trendly",
        "HomeMix-дроп",
        "Інстаграм",
        "Marcat -дроп",
        "Заміна",
        "Довідправка",
        "Дропшипінг",
        "Інстаграм ОМ",
        "Експрес-шоп -дроп",
        "Skandi",
        "Klik Shop - дроп",
        "самовивіз",
    ]

    allowed_utm = ["mobile_catalog_app", "portal"]

    df.columns = df.columns.str.strip()

    if "Статус" in df.columns:
        df["Статус_clean"] = (
            df["Статус"].astype(str).str.strip()
        )

        filtered_df = df[
            df["Статус_clean"].isin(
                [status.strip() for status in allowed_statuses]
            )
        ].copy()
    else:
        filtered_df = df.copy()

    if "Магазин" in filtered_df.columns:
        filtered_df["Магазин_clean"] = (
            filtered_df["Магазин"].astype(str).str.strip()
        )

        filtered_df = filtered_df[
            ~filtered_df["Магазин_clean"].isin(
                [store.strip() for store in stores_to_remove]
            )
        ]

    if "Технічний відділ" in filtered_df.columns:
        tech_val = (
            filtered_df["Технічний відділ"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        filtered_df = filtered_df[
            filtered_df["Технічний відділ"].isna()
            | tech_val.isin(["", "-", "nan", "none", "null"])
        ]

    if "utm_medium" in filtered_df.columns:
        filtered_df["utm_clean"] = (
            filtered_df["utm_medium"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        if (
            (filtered_df["utm_clean"] != "")
            & (~filtered_df["utm_clean"].isin(["nan", "none"]))
        ).any():
            filtered_df = filtered_df[
                filtered_df["utm_clean"].isin(allowed_utm)
            ]

    if "Магазин" in filtered_df.columns:
        filtered_df = filtered_df.sort_values(
            by="Магазин",
            ascending=True,
        )

    if filtered_df.empty:
        return 0

    client = get_gspread_client()
    doc = client.open_by_key(
        "1Ci_AoA6PBtlglbY_CY4d16tRX-7rxZ8_1YbEFft_hGs"
    )

    yellow_stores = [
        "Borniatco",
        "Bybka_shop",
        "Laggi market",
        "TrendVibe",
        "Yellow Monkey",
    ]

    new_stores = [
        "Moods",
        "Praktix",
        "MIXORA",
        "ПІДЕ",
        "Vdalo Shop",
        "Velora",
        "сирник",
        "ОгоШоп",
        "Хапай",
        "Требасик",
        "Вибирайко",
        "Покупайко",
    ]

    drop_stores = [
        "Shopik",
        "Croko",
        "Vsemarket",
        "HataSpace",
        "Zevs-market - дроп",
        "TrendoMania -дроп",
        "MegaShop -дроп",
        "ToyVo - дроп",
        "Yatka -дроп",
        "BoTreba дроп",
        "FENIX-UA - дроп",
        "Easyshop-дроп",
        "BoTreba -дроп",
        "Two birds",
    ]

    df_yellow = filtered_df[
        filtered_df["Магазин"].isin(yellow_stores)
    ]

    df_new = filtered_df[
        filtered_df["Магазин"].isin(new_stores)
    ]

    df_drop = filtered_df[
        filtered_df["Магазин"].isin(drop_stores)
    ]

    df_nashi = filtered_df[
        ~filtered_df["Магазин"].isin(yellow_stores)
        & ~filtered_df["Магазин"].isin(drop_stores)
        & ~filtered_df["Магазин"].isin(new_stores)
    ]

    targets = [
        (df_yellow, "Yellow/Laggi/Born/Bybka/TrendVibe"),
        (df_drop, "Дроп"),
        (df_nashi, "Наші"),
        (df_new, "Нові"),
    ]

    cols_order = [
        "Дата створення",
        "Магазин",
        "Статус",
        "Коментар менеджера",
        "Зовнішній ID",
        "№",
    ]

    for target_df, sheet_name in targets:
        if target_df.empty:
            continue

        sheet = doc.worksheet(sheet_name)

        for column in cols_order:
            if column not in target_df.columns:
                target_df[column] = ""

        values_to_add = (
            target_df[cols_order]
            .fillna("")
            .values
            .tolist()
        )

        first_free_row = len(sheet.col_values(3)) + 1
        target_last_row = first_free_row + len(values_to_add) - 1

        ensure_capacity(sheet, target_last_row)

        sheet.update(
            range_name=f"C{first_free_row}:H{target_last_row}",
            values=values_to_add,
        )

    return len(filtered_df)


# ============================================================
# ВЕБІНТЕРФЕЙС
# ============================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Asteril CRM Automation</title>

    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            margin-top: 60px;
            background: #f4f4f9;
        }

        .container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            display: inline-block;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
            max-width: calc(100% - 40px);
            box-sizing: border-box;
        }

        .btn {
            padding: 14px 24px;
            font-size: 16px;
            margin: 10px;
            cursor: pointer;
            color: white;
            border: none;
            border-radius: 5px;
            width: 350px;
            max-width: 100%;
            font-weight: bold;
        }

        .btn-1 {
            background-color: #1f538d;
        }

        .btn-3 {
            background-color: #dc3545;
        }

        .btn:hover {
            opacity: 0.9;
        }

        #result {
            margin-top: 20px;
            font-weight: bold;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            color: #333;
        }

        .loading {
            color: #007bff;
        }

        .setting {
            margin: 16px 0;
        }

        .setting label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }

        .setting select,
        .setting input {
            padding: 10px;
            font-size: 16px;
            max-width: 100%;
            box-sizing: border-box;
        }
    </style>
</head>

<body>
    <div class="container">
        <h2>⚙️ Автоматизація вигрузок Asteril CRM</h2>

        <p>Оберіть процес для виконання на сервері:</p>

        <div class="setting">
            <label for="exportMode">📦 Тип вигрузки для КТВ:</label>

            <select id="exportMode">
                <option value="partial" selected>
                    Неповна вигрузка
                </option>
                <option value="full">
                    Повна вигрузка
                </option>
            </select>
        </div>

        <button class="btn btn-1" onclick="runProcess(1)">
            🗓️ Запустити Процес 1 (КТВ)
        </button>

        <div class="setting">
            <label for="reviewsDate">
                📅 Дата замовлень для відгуків:
            </label>

            <input
                type="date"
                id="reviewsDate"
                value="{{ default_reviews_date }}"
            >
        </div>

        <button class="btn btn-3" onclick="runProcess(3)">
            💭 Запустити Процес 3 (Відгуки)
        </button>

        <div id="result"></div>
    </div>

<script>
let statusTimer = null;

function runProcess(num) {
    const resDiv = document.getElementById("result");
    const requestBody = {};

    if (num === 1) {
        requestBody.export_mode =
            document.getElementById("exportMode").value;
    }

    if (num === 3) {
        const selectedDate =
            document.getElementById("reviewsDate").value;

        if (!selectedDate) {
            resDiv.className = "";
            resDiv.style.color = "red";
            resDiv.innerText =
                "❌ Виберіть дату для Процесу 3.";
            return;
        }

        requestBody.reviews_date = selectedDate;
    }

    resDiv.className = "loading";
    resDiv.style.color = "#007bff";
    resDiv.innerText = "⏳ Запускаємо процес " + num + "...";

    fetch("/run/" + num, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(requestBody)
    })
    .then(async response => {
        const data = await response.json();

        if (!response.ok && data.status !== "busy") {
            throw new Error(data.message || "Не вдалося запустити процес.");
        }

        return data;
    })
    .then(data => {
        if (data.status === "started") {
            resDiv.className = "loading";
            resDiv.style.color = "#007bff";
            resDiv.innerText =
                "⏳ Процес " + num +
                " запущено. Не натискайте кнопку повторно.";

            startStatusCheck();
        } else if (data.status === "busy") {
            resDiv.className = "";
            resDiv.style.color = "orange";
            resDiv.innerText = "⚠️ " + data.message;
        } else {
            resDiv.className = "";
            resDiv.style.color = "red";
            resDiv.innerText = "❌ " + data.message;
        }
    })
    .catch(error => {
        resDiv.className = "";
        resDiv.style.color = "red";
        resDiv.innerText =
            "❌ Не вдалося запустити процес: " + error.message;
    });
}

function startStatusCheck() {
    if (statusTimer) {
        clearInterval(statusTimer);
    }

    statusTimer = setInterval(() => {
        fetch("/status")
        .then(response => response.json())
        .then(data => {
            const resDiv = document.getElementById("result");

            if (data.status === "running") {
                resDiv.className = "loading";
                resDiv.style.color = "#007bff";
                resDiv.innerText =
                    "⏳ Виконується процес " +
                    data.process_num +
                    "... Не натискайте кнопку повторно.";
            } else if (data.status === "success") {
                clearInterval(statusTimer);
                statusTimer = null;

                resDiv.className = "";
                resDiv.style.color = "green";
                resDiv.innerText = "✅ " + data.message;
            } else if (data.status === "error") {
                clearInterval(statusTimer);
                statusTimer = null;

                resDiv.className = "";
                resDiv.style.color = "red";
                resDiv.innerText = "❌ Помилка: " + data.message;
            }
        })
        .catch(error => {
            console.log("Помилка перевірки статусу:", error);
        });
    }, 2000);
}
</script>

</body>
</html>
"""


# ============================================================
# ФОНОВИЙ ЗАПУСК ПРОЦЕСІВ
# Процес 2 видалено.
# ============================================================

def run_process_background(process_num, reviews_date=None, export_mode="partial"):
    global process_status

    try:
        if process_num == 1:
            count = process_one(export_mode)

            mode_text = (
                "неповна"
                if export_mode == "partial"
                else "повна"
            )

            msg = (
                f"Процес 1 (КТВ, {mode_text} вигрузка) "
                f"успішно виконано! Оброблено рядків: {count}"
            )

        elif process_num == 3:
            count = process_three(reviews_date)

            msg = (
                f"Процес 3 (Відгуки) успішно виконано! "
                f"Оброблено рядків: {count}"
            )

        else:
            raise ValueError("Невідомий процес")

        process_status = {
            "running": False,
            "process_num": process_num,
            "status": "success",
            "message": msg,
        }

    except Exception as error:
        print(f"=== ПОМИЛКА в процесі {process_num} ===")
        traceback.print_exc()

        process_status = {
            "running": False,
            "process_num": process_num,
            "status": "error",
            "message": str(error),
        }

    finally:
        process_lock.release()


# ============================================================
# ГОЛОВНА СТОРІНКА
# ============================================================

@app.route("/")
def index():
    default_reviews_date = (
        datetime.now() - timedelta(days=7)
    ).strftime("%Y-%m-%d")

    return render_template_string(
        HTML_TEMPLATE,
        default_reviews_date=default_reviews_date,
    )


# ============================================================
# ЗАПУСК ПРОЦЕСУ
# ============================================================

@app.route("/run/<int:process_num>", methods=["POST"])
def run_process_endpoint(process_num):
    global process_status

    data = request.get_json(silent=True) or {}
    reviews_date = None
    export_mode = "partial"

    if process_num not in [1, 3]:
        return jsonify({
            "status": "error",
            "message": "Невідомий процес. Доступні процеси: 1 і 3.",
        }), 400

    if process_num == 1:
        export_mode = data.get("export_mode", "partial")

        if export_mode not in ["partial", "full"]:
            return jsonify({
                "status": "error",
                "message": "Некоректний тип вигрузки.",
            }), 400

    if process_num == 3:
        reviews_date_raw = data.get("reviews_date")

        if not reviews_date_raw:
            return jsonify({
                "status": "error",
                "message": "Не вибрана дата для Процесу 3.",
            }), 400

        try:
            reviews_date = datetime.strptime(
                reviews_date_raw,
                "%Y-%m-%d",
            ).strftime("%d.%m.%Y")

        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Некоректний формат дати.",
            }), 400

    if not process_lock.acquire(blocking=False):
        return jsonify({
            "status": "busy",
            "message": (
                f"Зараз уже виконується процес "
                f"{process_status['process_num']}. "
                "Дочекайтеся його завершення."
            ),
        }), 409

    process_status = {
        "running": True,
        "process_num": process_num,
        "status": "running",
        "message": f"Виконується процес {process_num}...",
    }

    thread = threading.Thread(
        target=run_process_background,
        args=(process_num, reviews_date, export_mode),
        daemon=True,
    )

    try:
        thread.start()

    except Exception:
        process_status = {
            "running": False,
            "process_num": process_num,
            "status": "error",
            "message": "Не вдалося запустити процес.",
        }
        process_lock.release()
        raise

    return jsonify({
        "status": "started",
        "message": f"Процес {process_num} запущено.",
    })


# ============================================================
# ПЕРЕВІРКА СТАТУСУ
# ============================================================

@app.route("/status")
def get_status():
    return jsonify(process_status)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
    )
