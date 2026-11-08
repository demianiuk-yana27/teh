"""Isolated, read-only Prom review probe. Run as a separate OS process."""
import json
import os
import sys
import time
import traceback
from urllib.parse import urlsplit

STATE = "/tmp/asteril_review_probe.json"
LOCK = "/tmp/asteril_review_probe.lock"

def write(**values):
    data = {"updated_at": time.time(), **values}
    path = STATE + ".tmp." + str(os.getpid())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(path, STATE)

def main():
    browser = None
    try:
        from negative_reviews import PromBrowser, load_active_shops, COMPANY_REVIEWS_URL, PRODUCT_REVIEWS_URL
        sheet_id = (os.environ.get("REVIEW_PROBE_SHEET_ID") or os.environ.get("SHEET_ID") or os.environ.get("PROM_SHEET_ID") or "").strip()
        if not sheet_id:
            raise RuntimeError("Не задано ID таблиці для перевірки відгуків")
        write(status="running", stage="Завантажуємо список магазинів")
        shops = load_active_shops(sheet_id)
        if not shops:
            raise RuntimeError("Активних магазинів не знайдено")
        # Use the smaller test shop, never silently fall back to GoodChoise.
        import unicodedata
        def normalized_name(value):
            return ' '.join(unicodedata.normalize('NFKC', str(value)).casefold().split())
        shop = next((item for item in shops if normalized_name(item.name) == 'ладно'), None)
        if shop is None:
            raise RuntimeError('Тестовий магазин Ладно не знайдено серед активних магазинів у Списку магазинів')
        write(status="running", stage="Відкриваємо Prom", shop=shop.name)
        browser = PromBrowser()
        browser.driver.set_page_load_timeout(12)
        browser.open_cms()
        # Only one shop; avoid switch_shop's internal three-retry cycle.
        browser._switch_shop_once(shop)
        results = []
        for kind, url in (("Компанія", COMPANY_REVIEWS_URL), ("Товари", PRODUCT_REVIEWS_URL)):
            found = False
            reason = "Блоки відгуків не завантажилися"
            for attempt in range(1, 6):
                write(status="running", stage=f"{kind}: спроба {attempt}/5", shop=shop.name, results=results)
                try:
                    browser.driver.get(url)
                except Exception:
                    try:
                        browser.driver.execute_script("window.stop()")
                    except Exception:
                        pass
                end = time.monotonic() + 9
                while time.monotonic() < end:
                    current = browser.driver.current_url
                    host = (urlsplit(current).hostname or "").lower()
                    if host != "my.prom.ua" or "/cms/" not in current:
                        reason = "Prom перенаправив зі сторінки відгуків"
                        break
                    body = (browser.driver.execute_script("return document.body ? document.body.innerText.slice(0,1200) : ''") or "").lower()
                    if "пароль" in body and ("увійти" in body or "войти" in body):
                        reason = "Prom показав форму входу"
                        break
                    # Page-specific review UI, not just a successful HTTP navigation.
                    if browser.driver.find_elements("css selector", '[data-qaid="statistics_block"], [data-qaid="opinion_stats_block"], [data-qaid*="opinion"], [data-qaid*="review"]'):
                        found = True
                        break
                    time.sleep(1)
                if found or reason != "Блоки відгуків не завантажилися":
                    break
                if attempt < 5:
                    time.sleep(min(attempt * 2, 6))
            results.append({"type": kind, "ok": found, "message": "Інтерфейс відгуків доступний" if found else reason + "; це не означає відсутність відгуків"})
        write(status="success", shop=shop.name, results=results, ok=all(x["ok"] for x in results))
    except Exception as exc:
        write(status="error", message=type(exc).__name__ + ": " + str(exc).split("Stacktrace:")[0][:180])
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        try:
            os.unlink(LOCK)
        except FileNotFoundError:
            pass

if __name__ == "__main__":
    main()
