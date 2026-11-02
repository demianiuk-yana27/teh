import json
import os
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import app as legacy


ASTERIL_ORDERS_URL = "https://crm2006091.asteril.com/orders"
DOROBKY_SHEET_ID = "1dY9HLJzDW9lX94TCiH5zpbhohLJaDmkh0tq-EYOXPg0"
OVERDUE_WORKSHEET = "Прострочки"


def _build_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=old")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--mute-audio")
    options.add_argument("--renderer-process-limit=1")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--no-zygote")

    chrome_bin = "/usr/bin/chromium"
    driver_bin = "/usr/bin/chromedriver"
    if os.path.exists(chrome_bin):
        options.binary_location = chrome_bin
    if os.path.exists(driver_bin):
        return webdriver.Chrome(service=Service(driver_bin), options=options)
    return webdriver.Chrome(options=options)


def _open_asteril(driver):
    driver.get(ASTERIL_ORDERS_URL)
    time.sleep(2)

    cookies_path = legacy._resolve_secret_path("asteril_cookies.json")
    if os.path.exists(cookies_path):
        with open(cookies_path, "r") as file:
            cookies = json.load(file)
        for raw_cookie in cookies:
            cookie = dict(raw_cookie)
            cookie.pop("sameSite", None)
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        driver.refresh()
        time.sleep(3)

    if "login" in driver.current_url.lower():
        raise RuntimeError(
            "Сесія Asteril завершилась. Оновіть asteril_cookies.json у тестовому Render."
        )

    WebDriverWait(driver, 45).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    legacy.wait_for_crm_loader(driver, timeout=45)


def _normalize(value):
    return " ".join(str(value or "").replace("\n", " ").split()).casefold()


def _read_status_count(driver, status_name):
    wanted = _normalize(status_name)
    candidates = driver.find_elements(
        By.XPATH,
        f"//*[normalize-space(text())={json.dumps(status_name, ensure_ascii=False)}]",
    )

    for element in candidates:
        try:
            if not element.is_displayed() or _normalize(element.text) != wanted:
                continue

            current = element
            for _ in range(6):
                text = " ".join((current.text or "").split())
                remainder = re.sub(
                    re.escape(status_name),
                    " ",
                    text,
                    count=1,
                    flags=re.IGNORECASE,
                )
                numbers = re.findall(r"(?<!\d)(\d{1,7})(?!\d)", remainder)
                if numbers:
                    return int(numbers[-1])
                current = current.find_element(By.XPATH, "..")
        except Exception:
            continue

    return None


def _find_header_row(values):
    best_row = None
    best_score = 0
    for index, row in enumerate(values[:10], start=1):
        score = sum(1 for value in row[1:] if str(value).strip())
        if score > best_score:
            best_row = index
            best_score = score
    if not best_row or best_score < 2:
        raise RuntimeError("Не вдалося визначити рядок із назвами статусів на аркуші «Прострочки».")
    return best_row


def _date_matches(value, now):
    text = str(value or "").strip()
    accepted = {
        now.strftime("%d.%m"),
        now.strftime("%d.%m.%Y"),
        now.strftime("%-d.%-m"),
        now.strftime("%-d.%-m.%Y"),
    }
    return text in accepted


def run_order_count_report():
    client = legacy.get_gspread_client()
    sheet = client.open_by_key(DOROBKY_SHEET_ID).worksheet(OVERDUE_WORKSHEET)
    values = sheet.get_all_values()
    header_row = _find_header_row(values)
    headers = values[header_row - 1]

    status_columns = []
    for column_index, header in enumerate(headers, start=1):
        name = str(header or "").strip()
        if column_index > 1 and name:
            status_columns.append((column_index, name))

    if not status_columns:
        raise RuntimeError("На аркуші «Прострочки» не знайдено колонок зі статусами.")

    now = datetime.now(ZoneInfo("Europe/Kyiv"))
    target_row = None
    for row_index in range(header_row + 1, len(values) + 1):
        row = values[row_index - 1]
        first_cell = row[0] if row else ""
        if _date_matches(first_cell, now):
            target_row = row_index
            break

    if target_row is None:
        raise RuntimeError(
            f"На аркуші «Прострочки» не знайдено рядок за сьогоднішню дату {now.strftime('%d.%m')}."
        )

    driver = _build_driver()
    try:
        _open_asteril(driver)
        found = {}
        missing = []
        for column_index, status_name in status_columns:
            count = _read_status_count(driver, status_name)
            if count is None:
                missing.append(status_name)
            else:
                found[column_index] = count

        if missing:
            raise RuntimeError(
                "У CRM не вдалося прочитати кількість для статусів: " + ", ".join(missing)
            )

        updates = []
        for column_index, _ in status_columns:
            updates.append({
                "range": f"{legacy.gspread.utils.rowcol_to_a1(target_row, column_index)}",
                "values": [[found[column_index]]],
            })
        sheet.batch_update(updates, value_input_option="USER_ENTERED")

        return {
            "date": now.strftime("%d.%m.%Y"),
            "statuses": len(found),
            "row": target_row,
        }
    finally:
        try:
            driver.quit()
        except Exception:
            pass
