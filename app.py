import glob
import json
import os
import platform
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string
import pandas as pd

# --- МОДУЛІ ДЛЯ АВТОМАТИЗАЦІЇ GOOGLE SHEETS ---
import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# --- МОДУЛІ ДЛЯ АВТОМАТИЗАЦІЇ BROWSER (ASTERIL CRM) ---
from selenium import webdriver
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

app = Flask(__name__)


def get_gspread_client():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise FileNotFoundError(
                "Файл 'token.json' не знайдено на сервері! Авторизуйтеся локально та завантажте token.json у репозиторій."
            )

    return gspread.authorize(creds)


def ensure_capacity(sheet, required_rows):
    if sheet.row_count < required_rows:
        sheet.add_rows(1000)


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


def safe_click(driver, element):
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", element
        )
        time.sleep(0.3)
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)


def wait_for_crm_loader(driver, timeout=60):
    time.sleep(1.5)
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located(
                (
                    By.XPATH,
                    "//div[contains(@class,'loading') or contains(@class,'spinner') or contains(@class,'overlay') or contains(@class,'loader')]",
                )
            )
        )
    except Exception:
        pass


def clear_all_filters(driver, timeout=45):
    wait_for_crm_loader(driver, timeout=timeout)
    reset_xpaths = [
        "//button[contains(translate(text(), 'ФІЛЬТРУВАТИ', 'фільтрувати'), 'фільтр')]/following-sibling::button[contains(text(), 'x') or contains(text(), 'X') or contains(text(), '×')]",
        "//button[contains(translate(text(), 'ФІЛЬТРУВАТИ', 'фільтрувати'), 'фільтр')]/following-sibling::*[1]",
        "//button[text()='x' or text()='X' or text()='×']",
        "//button[contains(@class, 'reset') or contains(@class, 'clear')]",
    ]
    clicked = False
    for _ in range(4):
        for xpath in reset_xpaths:
            try:
                elements = driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    if el.is_displayed():
                        safe_click(driver, el)
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
    for kw in keywords:
        kw_lower = kw.lower()
        xpaths = [
            f"//label[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ', 'abcdefghijklmnopqrstuvwxyzабвгґдеєжзиіїйклмнопрстуфхцчшщьюя'), '{kw_lower}')]/following-sibling::input",
            f"//label[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ', 'abcdefghijklmnopqrstuvwxyzабвгґдеєжзиіїйклмнопрстуфхцчшщьюя'), '{kw_lower}')]/..//input",
            f"//input[contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ', 'abcdefghijklmnopqrstuvwxyzабвгґдеєжзиіїйклмнопрстуфхцчшщьюя'), '{kw_lower}')]",
        ]
        for xpath in xpaths:
            try:
                for el in driver.find_elements(By.XPATH, xpath):
                    if el.is_displayed():
                        return el
            except StaleElementReferenceException:
                continue
    return None


def select_date_preset(driver, input_element, preset_name="Сьогодні"):
    safe_click(driver, input_element)
    time.sleep(1)
    for btn in driver.find_elements(
        By.XPATH,
        f"//*[contains(text(), '{preset_name}') or contains(text(), '{preset_name.lower()}')]",
    ):
        try:
            if btn.is_displayed():
                safe_click(driver, btn)
                break
        except StaleElementReferenceException:
            continue
    time.sleep(0.5)


def set_custom_date_range(driver, input_element, start_date_str, end_date_str=None):
    safe_click(driver, input_element)
    time.sleep(1)

    def force_set_value(el, date_str):
        driver.execute_script(
            "arguments[0].focus(); arguments[0].value = '';", el
        )
        el.send_keys(Keys.CONTROL + "a")
        el.send_keys(Keys.BACKSPACE)
        el.send_keys(date_str)
        driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
            "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
            el,
            date_str,
        )

    start_inputs = driver.find_elements(
        By.XPATH,
        "//label[contains(text(),'Початкова')]/following-sibling::input | //input[contains(@placeholder,'Початкова')]",
    )
    if start_inputs:
        force_set_value(start_inputs[0], start_date_str)
    else:
        force_set_value(input_element, start_date_str)
    time.sleep(0.4)

    if end_date_str:
        end_inputs = driver.find_elements(
            By.XPATH,
            "//label[contains(text(),'Кінцева')]/following-sibling::input | //input[contains(@placeholder,'Кінцева')]",
        )
        if end_inputs:
            force_set_value(end_inputs[0], end_date_str)
            time.sleep(0.4)

    for c_btn in driver.find_elements(
        By.XPATH,
        "//*[contains(text(), 'ВИБРАТИ') or contains(text(), 'Применить')]",
    ):
        try:
            if c_btn.is_displayed():
                safe_click(driver, c_btn)
                break
        except StaleElementReferenceException:
            continue
    time.sleep(0.5)


def download_report_from_asteril(
    domain_url, process_type, download_dir="temp_downloads"
):
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    for f in glob.glob(os.path.join(download_dir, "*")):
        try:
            os.remove(f)
        except Exception:
            pass

    cookies_file = os.path.abspath("asteril_cookies.json")

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Шлях до Chromium для Render
    chrome_options.binary_location = "/usr/bin/chromium-browser"

    prefs = {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=chrome_options
    )

    try:
        if not domain_url.startswith("http"):
            domain_url = "https://" + domain_url

        driver.get(domain_url)
        time.sleep(3)

        if os.path.exists(cookies_file):
            try:
                with open(cookies_file, "r") as f:
                    for cookie in json.load(f):
                        cookie.pop("sameSite", None)
                        try:
                            driver.add_cookie(cookie)
                        except Exception:
                            pass
                driver.refresh()
                time.sleep(3)
            except Exception:
                pass

        orders_url = (
            domain_url
            if domain_url.endswith("/orders")
            else domain_url.rstrip("/") + "/orders"
        )
        if driver.current_url.rstrip("/") != orders_url.rstrip("/"):
            driver.get(orders_url)

        wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//button[contains(translate(text(), 'ФІЛЬТРУВАТИ', 'фільтрувати'), 'фільтр')] | //button[contains(@class, 'filter')]",
                )
            )
        )
        time.sleep(2)
        clear_all_filters(driver, timeout=45)

        today = datetime.now()
        if process_type == 1:
            try:
                for btn in driver.find_elements(
                    By.XPATH,
                    "//a[contains(text(), 'Усе') or contains(text(), 'Все')]",
                ):
                    if btn.is_displayed():
                        safe_click(driver, btn)
                        time.sleep(1.5)
                        break
            except Exception:
                pass
            deadline_input = find_date_input(
                driver, ["крайній термін", "deadline", "термін відправки"]
            )
            if deadline_input:
                select_date_preset(driver, deadline_input, "Сьогодні")

        elif process_type == 2:
            date_5_days_ago = (today - timedelta(days=5)).strftime("%d.%m.%Y")
            today_str = today.strftime("%d.%m.%Y")
            try:
                for btn in driver.find_elements(
                    By.XPATH, "//*[normalize-space(text())='Приїхала']"
                ):
                    if btn.is_displayed():
                        safe_click(driver, btn)
                        time.sleep(1.5)
                        break
            except Exception:
                pass
            date_change_input = find_date_input(
                driver, ["дата зміни", "updated_at", "зміни"]
            )
            if date_change_input:
                set_custom_date_range(
                    driver, date_change_input, date_5_days_ago, today_str
                )

        elif process_type == 3:
            exact_7_days_ago = (today - timedelta(days=7)).strftime("%d.%m.%Y")
            try:
                for btn in driver.find_elements(
                    By.XPATH,
                    "//a[contains(text(), 'Усе') or contains(text(), 'Все')]",
                ):
                    if btn.is_displayed():
                        safe_click(driver, btn)
                        time.sleep(1.5)
                        break
            except Exception:
                pass
            date_create_input = find_date_input(
                driver, ["дата створення", "created_at", "створення"]
            )
            if date_create_input:
                set_custom_date_range(
                    driver, date_create_input, exact_7_days_ago, exact_7_days_ago
                )

        filter_btn = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[contains(translate(text(), 'ФІЛЬТРУВАТИ', 'фільтрувати'), 'фільтр')]",
                )
            )
        )
        safe_click(driver, filter_btn)
        time.sleep(4)
        wait_for_crm_loader(driver, timeout=60)

        excel_icon = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//button[contains(@class, 'excel') or .//i[contains(@class,'excel')]] | //button[contains(text(), 'Excel')]",
                )
            )
        )
        safe_click(driver, excel_icon)
        time.sleep(1.5)

        downloaded_file = None
        for _ in range(90):
            time.sleep(1)
            files = (
                glob.glob(os.path.join(download_dir, "*.xlsx"))
                + glob.glob(os.path.join(download_dir, "*.xls"))
                + glob.glob(os.path.join(download_dir, "*.csv"))
            )
            temp_files = glob.glob(
                os.path.join(download_dir, "*.crdownload")
            ) + glob.glob(os.path.join(download_dir, "*.tmp"))
            if files and not temp_files:
                downloaded_file = files[0]
                break

        if not downloaded_file:
            raise TimeoutError(
                "Файл не завантажився в папку temp_downloads за 90 секунд."
            )
        return downloaded_file

    finally:
        try:
            driver.quit()
        except Exception:
            pass


# --- ЛОГІКА ОБРОБКИ ТА ЗАПИСУ ДЛЯ ПРОЦЕСІВ ---
def process_one():
    input_file = download_report_from_asteril(
        "https://crm2006091.asteril.com/orders", process_type=1
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
        "Дропшипінг",
    ]
    allowed_utm = ["mobile_catalog_app", "portal", "bigl"]

    df["Статус"] = df["Статус"].astype(str).str.strip()
    df["Магазин"] = df["Магазин"].astype(str).str.strip()
    df["utm_medium"] = df["utm_medium"].astype(str).str.strip()

    filtered_df = df[
        df["Статус"].isin(allowed_statuses)
        & (~df["Магазин"].isin(stores_to_remove))
        & (df["utm_medium"].isin(allowed_utm))
    ].sort_values(by="Статус", ascending=True)

    client = get_gspread_client()
    sheet = client.open_by_key(
        "1sNWKNZhmE-DXancPOX5RtLhtbQ_-ThwhfqlwyVmSzSE"
    ).worksheet("КТВ")
    raw_values = filtered_df[["Магазин", "№", "Статус"]].fillna("").values.tolist()
    if not raw_values:
        return 0

    first_free_row = len(sheet.col_values(4)) + 1
    ensure_capacity(sheet, first_free_row + len(raw_values))
    remove_data_validation(sheet, first_free_row, 1, first_free_row, 2)

    sheet.update(
        range_name=f"A{first_free_row}",
        values=[[datetime.now().strftime("%d.%m")]],
    )
    sheet.update(
        range_name=f"D{first_free_row + 1}:F{first_free_row + len(raw_values) - 1}",
        values=raw_values,
    )
    return len(filtered_df)


def process_two():
    input_file = download_report_from_asteril(
        "https://crm2006091.asteril.com/orders", process_type=2
    )
    df = pd.read_excel(input_file)

    responsible_to_remove = [
        "Менеджер дроп Ілля Діана",
        "Менеджер дроп Ілля 3 Наталя",
        "Менеджер дроп Ілля 4 Дарія",
        "Менеджер дроп Ілля 6 Микола",
        "Менеджер дроп Ілля 10 Таня",
        "Менеджер дроп Ілля Катя тех",
        "Менеджер дроп Ілля СБ",
        "Менеджер Дроп Ілля 12 Олена",
        "Саржовський Ілля CBDO (31.01.23)",
        "Андрій менеджер Богдан ДРОП",
        "Дарина менеджер Богдан ДРОП",
        "Тетяна менеджер Богдан ДРОП",
        "Богдан Дроп Менеджер 1",
        "Богдан Дроп Менеджер 2",
        "Акаунт помічника Богдан ДРОП Вадим",
        "Аліна менеджер Богдан ДРОП",
        "Тех Лопатчук Ростислав дропшипінг(22.07.2025)1172",
        "Тех- Плужник Анастасія дропшипінг (22.07.2023) 1021",
        "ТехВідділ Скобельська Інна (25.11.2025) 1218",
        "Тех Гаврилюк Ярослав прості посилки(16.09.2024) 1082",
        "Тех М'якота Владислав прості посилки*(02.06.22) 100_283",
        "Тех- Кріпак Дар'я негативні/відгуки(16.03.2023)_280",
        "Тех-Чернявська Валерія негативні/відгуки (02.07.2025) 1224",
        "Тех-Русак Тетяна негативні відгуки (27.11.2023) 907",
        "Богдан ДРОП",
    ]
    responsible_to_remove = [name.strip() for name in responsible_to_remove]

    df["Відповідальний"] = df["Відповідальний"].astype(str).str.strip()
    df["Магазин"] = df["Магазин"].astype(str).str.strip()

    filtered_df = df[~df["Відповідальний"].isin(responsible_to_remove)].sort_values(
        by="Магазин", ascending=True
    )

    client = get_gspread_client()
    sheet = client.open_by_key(
        "1sNWKNZhmE-DXancPOX5RtLhtbQ_-ThwhfqlwyVmSzSE"
    ).worksheet("Приїхала")
    raw_values = (
        filtered_df[["№", "Телефони", "Магазин", "Товари"]].fillna("").values.tolist()
    )
    if not raw_values:
        return 0

    first_free_row = len(sheet.col_values(4)) + 1
    ensure_capacity(sheet, first_free_row + len(raw_values))
    remove_data_validation(sheet, first_free_row, 1, first_free_row, 2)

    today = datetime.now()
    sheet.update(
        range_name=f"A{first_free_row}:B{first_free_row}",
        values=[
            [
                today.strftime("%d.%m"),
                (today - timedelta(days=5)).strftime("%d.%m"),
            ]
        ],
    )
    sheet.update(
        range_name=f"D{first_free_row + 1}:G{first_free_row + len(raw_values) - 1}",
        values=raw_values,
    )
    return len(filtered_df)


def process_three():
    input_file = download_report_from_asteril(
        "https://crm2006091.asteril.com/orders", process_type=3
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
    ]
    stores_to_remove = [
        "Дроп Котик trendland",
        "Дроп Котик clickmart",
        "Mona Liza",
        "One Bird",
        "Best-Buy",
        "Home81",
        "Dobromarket",
        "Shop-Market-Top",
        "Trendly",
        "HomeMix",
        "Інстаграм",
        "Marcat -дроп",
        "Заміна",
        "Довідправка",
        "Дропшипінг",
        "Інстаграм ОМ",
        "Експрес-шоп -дроп",
        "Skandi",
    ]
    allowed_utm = ["mobile_catalog_app", "portal"]

    df.columns = df.columns.str.strip()
    if "Статус" in df.columns:
        df["Статус_clean"] = df["Статус"].astype(str).str.strip()
        filtered_df = df[
            df["Статус_clean"].isin([s.strip() for s in allowed_statuses])
        ].copy()
    else:
        filtered_df = df.copy()

    if "Магазин" in filtered_df.columns:
        filtered_df["Магазин_clean"] = (
            filtered_df["Магазин"].astype(str).str.strip()
        )
        filtered_df = filtered_df[
            ~filtered_df["Магазин_clean"].isin(
                [s.strip() for s in stores_to_remove]
            )
        ]

    if "Технічний відділ" in filtered_df.columns:
        tech_val = (
            filtered_df["Технічний відділ"].astype(str).str.strip().str.lower()
        )
        filtered_df = filtered_df[
            filtered_df["Технічний відділ"].isna()
            | tech_val.isin(["", "-", "nan", "none", "null"])
        ]

    if "utm_medium" in filtered_df.columns:
        filtered_df["utm_clean"] = (
            filtered_df["utm_medium"].astype(str).str.strip().str.lower()
        )
        if (
            (filtered_df["utm_clean"] != "")
            & (~filtered_df["utm_clean"].isin(["nan", "none"]))
        ).any():
            filtered_df = filtered_df[filtered_df["utm_clean"].isin(allowed_utm)]

    if "Магазин" in filtered_df.columns:
        filtered_df = filtered_df.sort_values(by="Магазин", ascending=True)

    if filtered_df.empty:
        return 0

    client = get_gspread_client()
    doc = client.open_by_key("1Ci_AoA6PBtlglbY_CY4d16tRX-7rxZ8_1YbEFft_hGs")

    yellow_stores = [
        "Borniatco",
        "Bybka_shop",
        "Laggi market",
        "TrendVibe",
        "Yellow Monkey",
    ]
    drop_stores = [
        "Shopik",
        "LOON",
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
        "Klik Shop - дроп",
        "BoTreba -дроп",
    ]

    df_yellow = filtered_df[filtered_df["Магазин"].isin(yellow_stores)]
    df_drop = filtered_df[filtered_df["Магазин"].isin(drop_stores)]
    df_nashi = filtered_df[
        ~filtered_df["Магазин"].isin(yellow_stores)
        & ~filtered_df["Магазин"].isin(drop_stores)
    ]

    targets = [
        (df_yellow, "Yellow/Laggi/Born/Bybka/TrendVibe"),
        (df_drop, "Дроп"),
        (df_nashi, "Наші"),
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
        for col in cols_order:
            if col not in target_df.columns:
                target_df[col] = ""

        values_to_add = target_df[cols_order].fillna("").values.tolist()
        first_free_row = len(sheet.col_values(3)) + 1
        target_last_row = first_free_row + len(values_to_add) - 1

        ensure_capacity(sheet, target_last_row)
        sheet.update(
            range_name=f"C{first_free_row}:H{target_last_row}", values=values_to_add
        )

    return len(filtered_df)


# --- WEB INTERFACE (HTML + FLASK) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <title>Asteril CRM Automation</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 60px; background: #f4f4f9; }
        .container { background: white; padding: 40px; border-radius: 10px; display: inline-block; box-shadow: 0px 4px 10px rgba(0,0,0,0.1); }
        .btn { padding: 14px 24px; font-size: 16px; margin: 10px; cursor: pointer; color: white; border: none; border-radius: 5px; width: 350px; font-weight: bold; }
        .btn-1 { background-color: #1f538d; }
        .btn-2 { background-color: #28a745; }
        .btn-3 { background-color: #dc3545; }
        .btn:hover { opacity: 0.9; }
        #result { margin-top: 20px; font-weight: bold; white-space: pre-wrap; color: #333; }
        .loading { color: #007bff; }
    </style>
</head>
<body>
    <div class="container">
        <h2>⚙️ Автоматизація вигрузок Asteril CRM</h2>
        <p>Оберіть процес для виконання на сервері:</p>
        
        <button class="btn btn-1" onclick="runProcess(1)">🗓️ Запустити Процес 1 (КТВ)</button><br>
        <button class="btn btn-2" onclick="runProcess(2)">🚚 Запустити Процес 2 (Приїхала)</button><br>
        <button class="btn btn-3" onclick="runProcess(3)">📞 Запустити Процес 3 (Відгуки)</button>

        <div id="result"></div>
    </div>

    <script>
        function runProcess(num) {
            let resDiv = document.getElementById("result");
            resDiv.className = "loading";
            resDiv.innerText = "⏳ Виконується процес " + num + ", будь ласка, зачекайте (це може зайняти до 1-2 хв)...";
            
            fetch('/run/' + num, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if(data.status === 'success') {
                        resDiv.className = "";
                        resDiv.style.color = "green";
                        resDiv.innerText = "✅ " + data.message;
                    } else {
                        resDiv.className = "";
                        resDiv.style.color = "red";
                        resDiv.innerText = "❌ Помилка: " + data.message;
                    }
                })
                .catch(error => {
                    resDiv.className = "";
                    resDiv.style.color = "red";
                    resDiv.innerText = "❌ Сталася системна помилка: " + error;
                });
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/run/<int:process_num>", methods=["POST"])
def run_process_endpoint(process_num):
    try:
        if process_num == 1:
            count = process_one()
            msg = f"Процес 1 (КТВ) успішно виконано! Оброблено рядків: {count}"
        elif process_num == 2:
            count = process_two()
            msg = (
                f"Процес 2 (Приїхала) успішно виконано! Оброблено рядків: {count}"
            )
        elif process_num == 3:
            count = process_three()
            msg = (
                f"Процес 3 (Відгуки) успішно виконано! Оброблено рядків: {count}"
            )
        else:
            return jsonify({"status": "error", "message": "Невідомий процес"}), 400

        return jsonify({"status": "success", "message": msg})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
