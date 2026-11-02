import glob
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def _wait_download(download_dir, previous_files, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        files = (
            glob.glob(os.path.join(download_dir, "*.xlsx"))
            + glob.glob(os.path.join(download_dir, "*.xls"))
            + glob.glob(os.path.join(download_dir, "*.csv"))
        )
        temp_files = glob.glob(os.path.join(download_dir, "*.crdownload")) + glob.glob(os.path.join(download_dir, "*.tmp"))
        new_files = [p for p in files if p not in previous_files]
        if new_files and not temp_files:
            return max(new_files, key=os.path.getmtime)
        time.sleep(0.5)
    raise TimeoutError("Файл не завантажився за 120 секунд.")


def _export_current_status(driver, wait, legacy, download_dir):
    before = set(glob.glob(os.path.join(download_dir, "*")))
    excel_button = wait.until(EC.presence_of_element_located((By.XPATH, "//button[.//i[contains(@class, 'icon-file-excel')]]")))
    driver.execute_script("arguments[0].click();", excel_button)
    try:
        regular = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(text(), 'звичайний', 'ЗВИЧАЙНИЙ'), 'ЗВИЧАЙНИЙ')]")))
        driver.execute_script("arguments[0].click();", regular)
    except Exception:
        pass
    return _wait_download(download_dir, before)


def _select_status(driver, legacy, status):
    elements = driver.find_elements(By.XPATH, f"//*[normalize-space(text())='{status}']")
    for element in elements:
        if element.is_displayed():
            legacy.safe_click(driver, element)
            legacy.wait_for_crm_loader(driver, timeout=60)
            return
    raise RuntimeError(f"У лівому меню CRM не знайдено видимий статус «{status}».")


def _download_both_reports(legacy, download_dir="temp_downloads_dorobky"):
    os.makedirs(download_dir, exist_ok=True)
    for path in glob.glob(os.path.join(download_dir, "*")):
        try:
            os.remove(path)
        except Exception:
            pass

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=old")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1024,768")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--mute-audio")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--renderer-process-limit=1")
    options.add_argument("--no-zygote")
    if os.path.exists("/usr/bin/chromium"):
        options.binary_location = "/usr/bin/chromium"
    abs_dir = os.path.abspath(download_dir)
    options.add_experimental_option("prefs", {
        "download.default_directory": abs_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "profile.managed_default_content_settings.images": 2,
    })
    if os.path.exists("/usr/bin/chromedriver"):
        driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)
    else:
        driver = webdriver.Chrome(options=options)

    try:
        for command in ("Page.setDownloadBehavior", "Browser.setDownloadBehavior"):
            try:
                driver.execute_cdp_cmd(command, {"behavior": "allow", "downloadPath": abs_dir})
            except Exception:
                pass

        wait = WebDriverWait(driver, 45)
        orders_url = "https://crm2006091.asteril.com/orders"
        driver.get(orders_url)

        cookies_file = legacy._resolve_secret_path("asteril_cookies.json")
        if os.path.exists(cookies_file):
            with open(cookies_file, "r") as fh:
                cookies = json.load(fh)
            for cookie in cookies:
                cookie.pop("sameSite", None)
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    pass
            driver.refresh()

        if "login" in driver.current_url:
            login = os.environ.get("ASTERIL_LOGIN")
            password = os.environ.get("ASTERIL_PASSWORD")
            if not login or not password:
                raise RuntimeError("Не задано ASTERIL_LOGIN / ASTERIL_PASSWORD у Render.")
            email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            password_input = driver.find_element(By.NAME, "password")
            email_input.clear(); email_input.send_keys(login)
            password_input.clear(); password_input.send_keys(password)
            driver.find_element(By.XPATH, "//button[@type='submit']").click()
            wait.until(lambda d: "login" not in d.current_url)
            if driver.current_url.rstrip("/") != orders_url:
                driver.get(orders_url)

        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(translate(text(), 'ФІЛЬТРУВАТИ', 'фільтрувати'), 'фільтр')] | //button[contains(@class, 'filter')]")))
        except TimeoutException:
            raise RuntimeError("CRM не завантажила сторінку замовлень.")

        legacy.clear_all_filters(driver, timeout=45)
        result = []
        for index, status in enumerate(("Доробка ТТН", "Доробка склад")):
            _select_status(driver, legacy, status)
            path = _export_current_status(driver, wait, legacy, download_dir)
            saved = os.path.join(download_dir, f"dorobky_{index}.xlsx")
            if os.path.abspath(path) != os.path.abspath(saved):
                os.replace(path, saved)
            result.append(saved)
        return result
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def process_dorobky_fast(legacy, rework_slot):
    ttn_file, warehouse_file = _download_both_reports(legacy)
    df = pd.concat([pd.read_excel(ttn_file), pd.read_excel(warehouse_file)], ignore_index=True)
    df.columns = df.columns.astype(str).str.strip()

    required = ["№", "Статус", "Відповідальний"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError("У звіті CRM не знайдено обов'язкові стовпці: " + ", ".join(missing))

    comment = "Доробка.1" if "Доробка.1" in df.columns else "Доробка"
    statuses = df["Статус"].fillna("").astype(str).str.strip()
    responsible = df["Відповідальний"].fillna("").astype(str).str.strip()
    responsible_lower = responsible.str.casefold()
    manager_mask = responsible_lower.str.startswith("тех") | responsible_lower.str.contains("стажер", regex=False)
    filtered = df[statuses.isin({"Доробка ТТН", "Доробка склад"}) & manager_mask].copy()
    if comment not in filtered.columns:
        filtered[comment] = ""
    rows = filtered[["№", "Статус", "Відповідальний", comment]].fillna("").values.tolist()

    client = legacy.get_gspread_client()
    sheet = client.open_by_key("1dY9HLJzDW9lX94TCiH5zpbhohLJaDmkh0tq-EYOXPg0").worksheet("Листопад")
    existing = sheet.get("A:D")
    last_used = max((i for i, row in enumerate(existing, 1) if any(str(v).strip() for v in row)), default=0)
    first_row = last_used + 1
    legacy.ensure_capacity(sheet, first_row + len(rows))
    header = f"Вивантаження від {datetime.now(ZoneInfo('Europe/Kyiv')).strftime('%d.%m.%Y')} — {rework_slot}"
    values = [[header, "", "", ""]] + rows
    sheet.update(range_name=f"A{first_row}:D{first_row + len(values) - 1}", values=values, value_input_option="USER_ENTERED")
    return len(filtered)
