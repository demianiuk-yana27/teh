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
    """Log in using Render credentials; no cookie file is required."""
    login = os.environ.get("ASTERIL_LOGIN", "").strip()
    password = os.environ.get("ASTERIL_PASSWORD", "")
    if not login or not password:
        raise RuntimeError(
            "У Render не налаштовано ASTERIL_LOGIN / ASTERIL_PASSWORD."
        )

    driver.get(ASTERIL_ORDERS_URL)
    wait = WebDriverWait(driver, 45)
    if "login" in driver.current_url.lower():
        email_input = wait.until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        password_input = driver.find_element(By.NAME, "password")
        email_input.clear()
        email_input.send_keys(login)
        password_input.clear()
        password_input.send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        wait.until(
            lambda browser: "login" not in browser.current_url.lower()
        )
        if driver.current_url.rstrip("/") != ASTERIL_ORDERS_URL:
            driver.get(ASTERIL_ORDERS_URL)

    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    if "login" in driver.current_url.lower():
        raise RuntimeError("Не вдалося авторизуватися в Asteril через Render.")
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
            # Safe structural diagnostics: do not expose order/customer data.
            from urllib.parse import urlparse
            current_path = urlparse(driver.current_url).path
            body = driver.find_element(By.TAG_NAME, "body")
            body_text = _normalize(body.text)
            visible_labels = sum(_normalize(name) in body_text for _, name in status_columns)
            exact_matches = sum(bool(driver.find_elements(
                By.XPATH,
                f"//*[normalize-space(text())={json.dumps(name, ensure_ascii=False)}]",
            )) for _, name in status_columns)
            raise RuntimeError(
                "Не вдалося прочитати лічильники статусів. "
                f"Діагностика: сторінка={current_path}; "
                f"назв у тексті={visible_labels}/{len(status_columns)}; "
                f"точних HTML-збігів={exact_matches}/{len(status_columns)}. "
                "Жодних даних у таблиці не змінено."
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
