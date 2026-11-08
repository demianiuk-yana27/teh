import os
import re
import time
from dataclasses import dataclass
from datetime import datetime

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CMS_URL = "https://my.prom.ua/cms/"
COMPANY_REVIEWS_URL = "https://my.prom.ua/cms/opinions/company"
PRODUCT_REVIEWS_URL = "https://my.prom.ua/cms/opinions/product/prom"
GRADES_URL = "https://my.prom.ua/cms/company/grades"
REVIEWS_ANALYTICS_URL = COMPANY_REVIEWS_URL
ORDER_REVIEW_SHEET_ID = "1Ci_AoA6PBtlglbY_CY4d16tRX-7rxZ8_1YbEFft_hGs"
ORDER_REVIEW_TABS = ["Yellow/Laggi/Born/Bybka/TrendVibe", "Наші", "Нові", "Дроп"]
REVIEW_PRESENT = "є відгук"


def _secret_path(filename):
    render_path = f"/etc/secrets/{filename}"
    return render_path if os.path.exists(render_path) else filename


def get_client():
    token_path = _secret_path("token.json")
    if not os.path.exists(token_path):
        raise FileNotFoundError("Не знайдено token.json для Google Sheets.")
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise RuntimeError("Google OAuth token недійсний і не може бути оновлений.")
    return gspread.authorize(creds)


def normalize_name(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def normalize_order(value):
    match = re.search(r"\d+", str(value or ""))
    return match.group(0) if match else ""


def parse_date(value):
    text = str(value or "").strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


@dataclass
class Shop:
    name: str
    id: str
    url: str = ""


def load_active_shops(spreadsheet_id):
    sheet = get_client().open_by_key(spreadsheet_id).worksheet("Список магазинів")
    rows = sheet.get("A:D")
    shops = []
    for row in rows[1:]:
        padded = row + [""] * (4 - len(row))
        if str(padded[2]).strip().upper() != "TRUE":
            continue
        name = str(padded[0]).strip()
        shop_id = normalize_order(padded[1])
        if name and shop_id:
            shops.append(Shop(name=name, id=shop_id, url=str(padded[3]).strip()))
    return shops


def _prom_session_cookies():
    """Load the encrypted Cloudflare vault over TLS, or fall back to Render secret file."""
    import json
    import urllib.request
    import urllib.parse
    import urllib.error

    endpoint = os.environ.get("PROM_SESSION_VAULT_URL", "").strip()
    token = os.environ.get("PROM_SESSION_MACHINE_TOKEN", "").strip()
    if endpoint or token:
        parsed = urllib.parse.urlsplit(endpoint)
        if (parsed.scheme != "https" or parsed.hostname not in {"teh-7rt.pages.dev", "flat-rice-6fc0-teh-prom-session-reader.demianiuk-yana27.workers.dev"} or parsed.path != "/prom-session" or parsed.port is not None or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment):
            raise RuntimeError("Неправильний PROM_SESSION_VAULT_URL: потрібен захищений endpoint Cloudflare.")
        if not token:
            raise RuntimeError("PROM_SESSION_MACHINE_TOKEN не налаштований на Render.")
        req = urllib.request.Request(endpoint, headers={"Authorization": "Bearer " + token, "Accept": "application/json", "User-Agent": "Asteril-Prom-Session-Reader/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            # Safe diagnostics: status and coarse response-header classification only.
            # Do not expose response bodies, request headers, or token values.
            content_type = (exc.headers.get("Content-Type", "") or "").lower()
            cf_ray = bool(exc.headers.get("CF-Ray"))
            cf_mitigated = (exc.headers.get("cf-mitigated", "") or "").lower() == "challenge"
            app_json = "application/json" in content_type
            reason = ("Cloudflare challenge" if cf_mitigated else
                      "JSON-відповідь Worker" if app_json else
                      "не-JSON відповідь Cloudflare")
            raise RuntimeError(f"Worker HTTP {exc.code}: {reason}; CF-Ray={cf_ray}.") from None
        except urllib.error.URLError:
            raise RuntimeError("Worker: мережева помилка або TLS.") from None
        except TimeoutError:
            raise RuntimeError("Worker: таймаут відповіді.") from None
        except (ValueError, TypeError, json.JSONDecodeError):
            raise RuntimeError("Worker: відповідь не є коректним JSON.") from None
        except Exception:
            raise RuntimeError("Worker: не вдалося прочитати відповідь.") from None
        cookies = data.get("cookies")
        if not isinstance(cookies, list):
            raise RuntimeError("Cloudflare не повернув коректну сесію Prom.")
        return cookies
    path = _secret_path("prom_cookies.json")
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else []


def check_prom_http_session(timeout=10):
    """Read-only Prom HTTP preflight with safe, per-stage status diagnostics.

    No cookies, tokens, response bodies, or arbitrary redirect URLs are logged.
    HTTP results are not proof of Chromium authentication.
    """
    import http.cookiejar
    import urllib.request
    import urllib.parse
    import urllib.error

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    def probe(url, jar):
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar), NoRedirect()
        )
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        })
        try:
            with opener.open(req, timeout=timeout) as response:
                status, headers = response.status, response.headers
        except urllib.error.HTTPError as exc:
            status, headers = exc.code, exc.headers
        except (OSError, ValueError, urllib.error.URLError, TimeoutError):
            return "network-error", False, "none"
        redirect = headers.get("Location", "")
        target = urllib.parse.urlsplit(urllib.parse.urljoin(url, redirect)) if redirect else None
        # Only report whether a redirect remains within an expected Prom hostname.
        location_class = (
            "none" if target is None else
            "prom" if target.hostname in ("prom.ua", "my.prom.ua") else
            "other"
        )
        return str(status), bool(headers.get("CF-Ray")), location_class

    try:
        try:
            items = _prom_session_cookies()
        except RuntimeError as exc:
            # _prom_session_cookies only returns safe, redacted error descriptions.
            return False, "Етап отримання cookies із Worker: " + str(exc)
        if not items:
            return False, "На сервері немає сесії Prom."
        jar = http.cookiejar.CookieJar()
        count = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain", "")).lower()
            bare = domain.lstrip(".")
            if bare != "prom.ua" and not bare.endswith(".prom.ua"):
                continue
            if not isinstance(item.get("name"), str) or not isinstance(item.get("value"), str):
                continue
            raw_expiry = item.get("expirationDate", item.get("expiry"))
            try:
                expiry = int(raw_expiry) if raw_expiry is not None else None
            except (ValueError, TypeError):
                expiry = None
            jar.set_cookie(http.cookiejar.Cookie(
                version=0, name=item["name"], value=item["value"], port=None,
                port_specified=False, domain=domain, domain_specified=True,
                domain_initial_dot=domain.startswith("."), path=str(item.get("path", "/")),
                path_specified=True, secure=bool(item.get("secure", False)),
                expires=expiry, discard=expiry is None, comment=None,
                comment_url=None, rest={}, rfc2109=False,
            ))
            count += 1
        if not count:
            return False, "У сховищі немає cookies для Prom."

        # Separate anonymous origin access from authenticated CMS navigation.
        empty_jar = http.cookiejar.CookieJar()
        public_status, public_ray, public_redirect = probe("https://prom.ua/", empty_jar)
        cms_status, cms_ray, cms_redirect = probe(CMS_URL, jar)
        summary = (
            f"Prom етапи: prom.ua без cookies HTTP {public_status} "
            f"(CF-Ray={public_ray}, redirect={public_redirect}); "
            f"my.prom.ua/cms/ з cookies HTTP {cms_status} "
            f"(CF-Ray={cms_ray}, redirect={cms_redirect})."
        )
        if cms_status == "200":
            return True, summary + " HTTP-доступ є; авторизація в Chromium потребує окремого підтвердження."
        return False, summary + " Доступ до кабінету не підтверджено."
    except Exception as exc:
        # Expose only exception type, never cookies, URLs, response bodies or secrets.
        return False, "Поетапна HTTP-перевірка: внутрішня помилка " + type(exc).__name__ + "."


class PromBrowser:
    def __init__(self, lightweight=False):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new" if lightweight else "--headless=old")
        if lightweight:
            options.page_load_strategy = "eager"
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-component-update")
            options.add_experimental_option("prefs", {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
            })
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=900,650" if lightweight else "--window-size=1400,900")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        profile_path = os.environ.get("PROM_PROFILE_PATH")
        if profile_path and os.path.isdir(profile_path):
            options.add_argument(f"--user-data-dir={os.path.abspath(profile_path)}")
        if os.path.exists("/usr/bin/chromium"):
            options.binary_location = "/usr/bin/chromium"
        if os.path.exists("/usr/bin/chromedriver"):
            self.driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)
        else:
            self.driver = webdriver.Chrome(options=options)
        self.lightweight = lightweight
        self.wait = WebDriverWait(self.driver, 15 if lightweight else 30)

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    def open_cms(self):
        # HTTP preflight can be redirected by Prom anti-bot protections even when
        # a browser session works. Browser navigation is the authoritative test.
        cookies = _prom_session_cookies()
        if not cookies and not os.environ.get("PROM_PROFILE_PATH"):
            raise RuntimeError("На сервері немає cookies або профілю Prom.")
        self.driver.set_page_load_timeout(10 if self.lightweight else 25)
        try:
            self.driver.get("https://prom.ua/")
        except Exception:
            # A page-load timeout may leave a usable document and cookie domain.
            try:
                self.driver.execute_script("window.stop()")
            except Exception:
                pass
        self._load_cookies_if_available(cookies)
        try:
            self.driver.get(CMS_URL)
        except Exception:
            try:
                self.driver.execute_script("window.stop()")
            except Exception:
                pass
        time.sleep(2)
        url = self.driver.current_url
        if "my.prom.ua/cms/" not in url:
            raise RuntimeError("Prom не підтвердив вхід через Chromium; поточна сторінка не є кабінетом.")
        # URL alone does not prove authenticated access: check for login redirects.
        body = (self.driver.execute_script("return document.body ? document.body.innerText.slice(0,3000) : ''") or "").lower()
        if ("увійти" in body or "войти" in body) and ("пароль" in body or "password" in body):
            raise RuntimeError("Prom показує форму входу замість кабінету.")
        self.dismiss_dialogs()

    def _load_cookies_if_available(self, cookies=None):
        cookies = _prom_session_cookies() if cookies is None else cookies
        if not cookies:
            return
        added = 0
        for cookie in cookies:
            clean = {k: cookie[k] for k in ("name", "value", "domain", "path", "secure", "httpOnly", "sameSite", "expiry") if k in cookie}
            if "expirationDate" in cookie and "expiry" not in clean:
                try:
                    clean["expiry"] = int(cookie["expirationDate"])
                except (ValueError, TypeError):
                    pass
            if clean.get("sameSite") not in ("Strict", "Lax", "None"):
                clean.pop("sameSite", None)
            try:
                self.driver.add_cookie(clean)
                added += 1
            except Exception:
                continue
        if not added:
            raise RuntimeError("Не вдалося встановити cookies Prom у Chromium.")

    def dismiss_dialogs(self):
        for text in ("Закрити", "Зрозуміло", "Пізніше", "Не зараз", "Пропустити"):
            try:
                for el in self.driver.find_elements(By.XPATH, f"//button[contains(normalize-space(.), '{text}')]"):
                    if el.is_displayed():
                        self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(0.2)
            except Exception:
                pass

    def switch_shop(self, shop):
        last_error = None
        for _ in range(3):
            try:
                self._switch_shop_once(shop)
                return
            except Exception as exc:
                last_error = exc
                self.open_cms()
        raise RuntimeError(f"Не вдалося перемкнути магазин {shop.name}: {last_error}")

    def _switch_shop_once(self, shop):
        if not self.driver.current_url.startswith(CMS_URL):
            self.driver.get(CMS_URL)
            time.sleep(1.5)
        self.dismiss_dialogs()
        selectors = [
            '[data-qaid="company_info"] [data-qaid="toggler_btn"]',
            '[data-qaid="company_info"]',
            '[data-testid="shop-selector-toggle"]',
            '[data-testid*="company-switch"]',
            '[data-testid*="shop-switch"]',
        ]
        toggle = None
        for selector in selectors:
            for el in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if el.is_displayed():
                    toggle = el
                    break
            if toggle:
                break
        if not toggle:
            candidates = self.driver.find_elements(By.XPATH, "//*[contains(normalize-space(.), 'ID:')]")
            visible = [x for x in candidates if x.is_displayed()]
            if visible:
                toggle = visible[-1]
        if not toggle:
            raise RuntimeError("Не знайдено перемикач магазину Prom.")
        self.driver.execute_script("arguments[0].click();", toggle)
        time.sleep(0.7)
        shop_targets = self.driver.find_elements(
            By.XPATH,
            f"//*[contains(normalize-space(.), '{shop.id}') or contains(normalize-space(.), {repr(shop.name)})]",
        )
        target = next((x for x in shop_targets if x.is_displayed()), None)
        if not target:
            raise RuntimeError(f"Магазин {shop.name} (ID {shop.id}) не знайдено у перемикачі Prom.")
        self.driver.execute_script("arguments[0].click();", target)
        time.sleep(1.5)
        self.dismiss_dialogs()

    def review_order_ids(self, since, until=None, wanted=None):
        found = set()
        since_date = parse_date(since)
        until_date = parse_date(until) if until else None
        for url in (COMPANY_REVIEWS_URL, PRODUCT_REVIEWS_URL):
            self.driver.get(url)
            time.sleep(1.5)
            for _ in range(200):
                body = self.driver.find_element(By.TAG_NAME, "body").text
                dates = []
                for m in re.finditer(r"(\d{2}\.\d{2}\.\d{2,4}).{0,500}?Замовлення\s*№\s*(\d+)", body, re.S | re.I):
                    date_value = parse_date(m.group(1))
                    order_id = m.group(2)
                    if date_value:
                        dates.append(date_value)
                    if date_value and since_date and date_value < since_date:
                        continue
                    if date_value and until_date and date_value > until_date:
                        continue
                    if wanted is None or order_id in wanted:
                        found.add(order_id)
                if wanted and wanted.issubset(found):
                    break
                if dates and since_date and min(dates) < since_date:
                    break
                next_btn = self._next_button()
                if not next_btn:
                    break
                self.driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(1)
        return found

    def _next_button(self):
        selectors = [
            "//a[@rel='next']",
            "//button[@aria-label='Наступна']",
            "//button[contains(@aria-label,'Next')]",
            "//*[self::a or self::button][normalize-space(.)='›' or normalize-space(.)='>']",
        ]
        for xpath in selectors:
            for el in self.driver.find_elements(By.XPATH, xpath):
                if el.is_displayed() and el.is_enabled() and el.get_attribute("disabled") is None:
                    return el
        return None

    def collect_review_stats(self):
        self.driver.get(REVIEWS_ANALYTICS_URL)
        block = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-qaid="statistics_block"]')))
        try:
            details = self.driver.find_element(By.CSS_SELECTOR, '[data-qaid="show_more_btn"]')
            if details.is_displayed():
                self.driver.execute_script("arguments[0].click();", details)
                time.sleep(0.5)
        except Exception:
            pass
        opinion = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-qaid="opinion_stats_block"]')))
        positive = opinion.find_element(By.CSS_SELECTOR, '[data-qaid="Позитивні"]').text
        negative = opinion.find_element(By.CSS_SELECTOR, '[data-qaid="Негативні"]').text
        p = [int(x.replace(" ", "")) for x in re.findall(r"\d[\d ]*", positive)]
        n = [int(x.replace(" ", "")) for x in re.findall(r"\d[\d ]*", negative)]
        if len(p) < 3 or len(n) < 3:
            raise RuntimeError("Prom повернув неповну статистику відгуків.")
        return {"monthlyPositive": p[0], "monthlyNegative": n[0], "yearlyPositive": p[2], "yearlyNegative": n[2]}

    def collect_performance_stats(self):
        self.driver.get(GRADES_URL)
        company = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-qaid="company_statistics"]')))
        text = company.text
        date_match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text)
        prom_date = date_match.group(1) if date_match else datetime.now().strftime("%d.%m.%Y")

        def percent(selector):
            try:
                txt = self.driver.find_element(By.CSS_SELECTOR, selector).text
                m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", txt)
                return float(m.group(1).replace(",", ".")) if m else None
            except Exception:
                return None

        def metric(label):
            m = re.search(re.escape(label) + r"\s*[:\n]?\s*([\d ]+)", text, re.I)
            return int(m.group(1).replace(" ", "")) if m else None

        return {
            "promDate": prom_date,
            "affectingOrders": metric("Замовлення, що впливають на показник"),
            "affectingCancellations": metric("Скасування, що впливають на показник"),
            "successfulOrdersPercent": percent('[data-qaid="successful-orders"]'),
            "positiveReviewsPercent": percent('[data-qaid="positive-reviews"]'),
            "readyToShipPercent": percent('[data-qaid="trusted"]'),
        }


def _find_shop_columns(values, header_rows=3):
    result = {}
    for r in range(min(header_rows, len(values))):
        for c, value in enumerate(values[r]):
            name = normalize_name(value)
            if name:
                result.setdefault(name, c + 1)
    return result


def _find_or_append_date_row(sheet, date_text, date_col=1):
    values = sheet.get_all_values()
    for idx, row in enumerate(values, start=1):
        if len(row) >= date_col and str(row[date_col - 1]).strip() == date_text:
            return idx
    row = max(len(values) + 1, 2)
    if sheet.row_count < row:
        sheet.add_rows(max(100, row - sheet.row_count))
    sheet.update(range_name=f"A{row}", values=[[date_text]], value_input_option="USER_ENTERED")
    return row


def write_stats(spreadsheet_id, shop, review_stats, performance_stats):
    book = get_client().open_by_key(spreadsheet_id)
    review_sheet = book.worksheet("Аналітика відгуків")
    performance_sheet = book.worksheet("Показники роботи")
    prom_date = performance_stats["promDate"]

    review_values = review_sheet.get_all_values()
    review_cols = _find_shop_columns(review_values, 3)
    review_col = review_cols.get(normalize_name(shop.name))
    if review_col and review_stats:
        row = _find_or_append_date_row(review_sheet, prom_date, 1)
        updates = [
            (review_col, review_stats["monthlyPositive"]),
            (review_col + 1, review_stats["monthlyNegative"]),
            (review_col + 3, review_stats["yearlyPositive"]),
            (review_col + 4, review_stats["yearlyNegative"]),
        ]
        for col, value in updates:
            review_sheet.update_cell(row, col, value)

    perf_values = performance_sheet.get_all_values()
    perf_cols = _find_shop_columns(perf_values, 4)
    perf_col = perf_cols.get(normalize_name(shop.name))
    if perf_col:
        row = _find_or_append_date_row(performance_sheet, prom_date, 2)
        values = [
            performance_stats.get("affectingOrders"),
            performance_stats.get("affectingCancellations"),
            performance_stats.get("successfulOrdersPercent"),
            performance_stats.get("positiveReviewsPercent"),
            performance_stats.get("readyToShipPercent"),
        ]
        for offset, value in enumerate(values):
            if value is not None:
                performance_sheet.update_cell(row, perf_col + offset, value)


def run_analytics(spreadsheet_id):
    shops = load_active_shops(spreadsheet_id)
    browser = PromBrowser()
    written = 0
    skipped = 0
    try:
        browser.open_cms()
        for shop in shops:
            try:
                browser.switch_shop(shop)
                review_stats = None
                performance = None
                try:
                    review_stats = browser.collect_review_stats()
                except Exception as exc:
                    print(f"[{shop.name}] Аналітика відгуків недоступна: {exc}")
                try:
                    performance = browser.collect_performance_stats()
                except Exception as exc:
                    print(f"[{shop.name}] Показники роботи недоступні: {exc}")
                if performance:
                    write_stats(spreadsheet_id, shop, review_stats, performance)
                    written += 1
                else:
                    skipped += 1
            except Exception as exc:
                skipped += 1
                print(f"[{shop.name}] Пропущено: {exc}")
    finally:
        browser.close()
    return {"written": written, "skipped": skipped, "active": len(shops)}


def _read_order_rows(since, until):
    book = get_client().open_by_key(ORDER_REVIEW_SHEET_ID)
    since_date = parse_date(since) if since else None
    until_date = parse_date(until) if until else None
    rows = []
    for tab in ORDER_REVIEW_TABS:
        sheet = book.worksheet(tab)
        values = sheet.get("C:I")
        for idx, row in enumerate(values, start=1):
            padded = row + [""] * (7 - len(row))
            date_value = parse_date(padded[0])
            shop = str(padded[1]).strip()
            order_id = normalize_order(padded[5])
            review_state = str(padded[6]).strip().casefold()
            if not date_value or not shop or not order_id or review_state == REVIEW_PRESENT:
                continue
            if since_date and date_value < since_date:
                continue
            if until_date and date_value > until_date:
                continue
            rows.append({"sheet": sheet, "row": idx, "shop": shop, "orderId": order_id})
    return rows


def run_order_review_check(spreadsheet_id, since, until=""):
    rows = _read_order_rows(since, until)
    if not rows:
        return {"checked": 0, "written": 0, "unresolved": 0}
    shops = load_active_shops(spreadsheet_id)
    by_name = {}
    for shop in shops:
        by_name.setdefault(normalize_name(shop.name), []).append(shop)
    grouped = {}
    for row in rows:
        grouped.setdefault(normalize_name(row["shop"]), []).append(row)
    browser = PromBrowser()
    written = 0
    unresolved = 0
    try:
        browser.open_cms()
        for name, order_rows in grouped.items():
            matches = by_name.get(name, [])
            if len(matches) != 1:
                unresolved += 1
                continue
            shop = matches[0]
            try:
                browser.switch_shop(shop)
                wanted = {row["orderId"] for row in order_rows}
                found = browser.review_order_ids(since, until or None, wanted)
                for row in order_rows:
                    if row["orderId"] in found:
                        current = row["sheet"].cell(row["row"], 9).value or ""
                        if str(current).strip().casefold() != REVIEW_PRESENT:
                            row["sheet"].update_cell(row["row"], 9, REVIEW_PRESENT)
                            written += 1
            except Exception as exc:
                unresolved += 1
                print(f"[{shop.name}] Помилка перевірки відгуків: {exc}")
    finally:
        browser.close()
    return {"checked": len(rows), "written": written, "unresolved": unresolved}


def run_review_export(spreadsheet_id, since, until=""):
    # Повний перенос запису негативних відгуків потребує стабільного DOM-карткового
    # парсера Prom. Цей процес навмисно не робить часткових/небезпечних записів.
    # Перевіряємо авторизацію і магазини, щоб конфігурацію можна було протестувати
    # окремо до ввімкнення запису в таблицю.
    shops = load_active_shops(spreadsheet_id)
    browser = PromBrowser()
    try:
        browser.open_cms()
        if shops:
            browser.switch_shop(shops[0])
    finally:
        browser.close()
    raise RuntimeError(
        "Вигрузка негативних відгуків підключена до модуля, але запис у таблицю ще "
        "не ввімкнений: спочатку перевіряємо Prom-сесію на тестовому Render, щоб не "
        "ризикувати некоректними записами."
    )
