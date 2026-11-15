"""API-only negative review collection; isolated Prom cookies per shop."""
import http.cookiejar
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request

from negative_reviews import _prom_session_cookies, parse_date


def _cookies():
    jar = http.cookiejar.CookieJar()
    for item in _prom_session_cookies():
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").lower()
        if domain.lstrip(".") != "prom.ua" and not domain.lstrip(".").endswith(".prom.ua"):
            continue
        if not isinstance(item.get("name"), str) or not isinstance(item.get("value"), str):
            continue
        expiry = item.get("expirationDate", item.get("expiry"))
        try:
            expiry = int(expiry) if expiry is not None else None
        except (TypeError, ValueError):
            expiry = None
        jar.set_cookie(http.cookiejar.Cookie(
            version=0, name=item["name"], value=item["value"], port=None,
            port_specified=False, domain=domain, domain_specified=True,
            domain_initial_dot=domain.startswith("."),
            path=str(item.get("path") or "/"), path_specified=True,
            secure=bool(item.get("secure", False)), expires=expiry,
            discard=expiry is None, comment=None, comment_url=None,
            rest={}, rfc2109=False))
    return jar


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read(opener, url, data=None, csrf=None):
    headers = {"Accept": "application/json, text/plain, */*",
               "User-Agent": "Mozilla/5.0",
               "Referer": "https://my.prom.ua/cms/opinions/product/prom",
               "X-Requested-With": "XMLHttpRequest"}
    if data is not None:
        headers.update({"Content-Type": "application/json",
                        "Origin": "https://my.prom.ua",
                        "Referer": "https://my.prom.ua/cms/opinions/company",
                        "X-CSRFToken": csrf})
    for attempt in range(4):
        try:
            with opener.open(urllib.request.Request(
                url, data=json.dumps(data).encode() if data is not None else None,
                headers=headers), timeout=18) as response:
                raw = response.read(800001)
                if len(raw) > 800000:
                    raise ValueError("Завелика відповідь Prom")
                if "json" not in response.headers.get("Content-Type", "").lower():
                    raise ValueError("Prom повернув не JSON")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ValueError("Некоректна структура Prom")
                return result
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            code = getattr(exc, "code", None)
            if attempt == 3 or (code is not None and code not in (429, 500, 502, 503, 504)):
                raise
            time.sleep(min(2 ** attempt, 6) + random.uniform(0, .3))


def _switch(account):
    jar = _cookies()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar), _NoRedirect())
    try:
        response = opener.open(urllib.request.Request(
            "https://my.prom.ua/remote/auth/sign-to/" + str(account),
            headers={"User-Agent": "Mozilla/5.0"}), timeout=15)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        location = response.headers.get("Location", "")
        if response.status not in (301, 302, 303) or not (
                location.startswith("/cms") or location.startswith("https://my.prom.ua/cms")):
            raise ValueError("Не підтверджено перемикання магазину")
    csrf = next((c.value for c in jar if c.name.lower() in (
        "csrftoken", "csrf_token")), None)
    if not csrf:
        raise ValueError("Відсутній CSRF після перемикання")
    return opener, urllib.parse.unquote(csrf)


def _date(value):
    dt = parse_date(str(value or "")[:10])
    return dt



def _customer_review_url(opener, opinion_id, order_id, kind):
    """Resolve the buyer-facing link using the review-type-specific Prom URL."""
    if not str(opinion_id).isdigit() or (kind == "company" and not str(order_id).isdigit()):
        raise ValueError("Немає необхідного ID для клієнтського посилання")
    if kind == "product":
        target = "https://prom.ua/product-opinions/edit/" + str(opinion_id)
    elif kind == "company":
        target = ("https://prom.ua/product-opinions/edit/" + str(opinion_id)
                  + "?order_id=" + str(order_id))
    else:
        raise ValueError("Невідомий тип відгуку")
    url = ("https://my.prom.ua/cms/opinions/get_short_url?"
           + urllib.parse.urlencode({"url": target}))
    result = _read(opener, url)
    short = result.get("shortUrl")
    if not isinstance(short, str) or not short.startswith("https://prom.ua/s/"):
        raise ValueError("Prom не повернув коректне клієнтське посилання")
    return short


def _order_id(opinion):
    """Find a real order ID, never substitute the opinion ID."""
    import re
    for key in ("linked_order_id", "linkedOrderId", "order_id", "orderId", "order_number", "orderNumber"):
        value = opinion.get(key)
        if isinstance(value, (int, str)) and str(value).strip().isdigit():
            return str(value).strip()
    for key in ("order", "order_info", "orderInfo"):
        nested = opinion.get(key)
        if isinstance(nested, dict):
            for field in ("id", "linked_order_id", "order_id", "orderId", "number", "orderNumber"):
                value = nested.get(field)
                if isinstance(value, (int, str)) and str(value).strip().isdigit():
                    return str(value).strip()
    for key in ("orderUrl", "order_url", "orderEditUrl", "order_edit_url"):
        url = opinion.get(key)
        if isinstance(url, str):
            match = re.search(r"/(?:order/edit|order)/([0-9]+)", url)
            if match:
                return match.group(1)
    return ""


def _order_field_diagnostics(opinion):
    """Log only field names, never buyer data or credentials."""
    return sorted(k for k in opinion if any(word in k.lower() for word in ("order", "url", "link")))


_EMOJI_NAMES = {
    "face_with_monocle": "🧐", "monocle": "🧐",
    "imp": "👿", "angry": "😠", "rage": "😡",
    "woman-gesturing-no": "🙅‍♀️", "woman_gesturing_no": "🙅‍♀️",
    "hourglass_flowing_sand": "⏳", "hourglass": "⌛",
    "star": "⭐", "thumbs_down": "👎", "disappointed": "😞",
    "cry": "😢", "thinking_face": "🤔", "slightly_frowning_face": "🙁",
}


def _display_emoji(value):
    """Convert Prom's emoji aliases to glyphs; never print raw alias names."""
    import re
    if not isinstance(value, str):
        return ""
    value = value.strip().strip(":")
    if not value:
        return ""
    if value in _EMOJI_NAMES:
        return _EMOJI_NAMES[value]
    if re.fullmatch(r"[a-z][a-z0-9_-]*", value):
        return ""
    return value


def _company_tags(opinion):
    """Only buyer-selected characteristics, not seller comments."""
    parts = []
    for key in ("tags", "userRatings", "user_ratings"):
        values = opinion.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, str):
                value = item.strip()
            elif isinstance(item, dict):
                value = next((str(item[k]).strip() for k in (
                    "title", "text", "label", "name", "value", "caption")
                    if isinstance(item.get(k), str) and item[k].strip()), "")
                emoji = _display_emoji(next((item[k] for k in ("emoji", "icon") if isinstance(item.get(k), str)), ""))
                if emoji and value and not value.startswith(emoji):
                    value = emoji + " " + value
            else:
                continue
            if value and value not in parts:
                parts.append(value)
    return parts


def _deleted_by_buyer(opinion):
    """Only explicit Prom deletion flags; a missing URL is not proof."""
    for key in ("deletedByAuthor", "deleted_by_author", "deletedByUser", "deleted_by_user"):
        if opinion.get(key) is True:
            return True
    # Generic deleted flags do not identify who deleted the review.
    return False


def _candidate(opinion, kind, shop):
    rating = opinion.get("rating")
    if type(rating) is not int or rating not in (1, 2, 3):
        return None
    company_id = opinion.get("companyId" if kind == "product" else "company_id")
    if str(company_id) != str(shop.id):
        raise ValueError("company_id не збігається з вибраним магазином")
    # Some company opinions have no order_id. Keep the review, using its
    # verified opinion ID as a fallback identifier (never fabricate an order).
    order_id = _order_id(opinion)
    if not order_id:
        print(f"[negative-reviews] {kind}: order ID unavailable; relevant API fields={_order_field_diagnostics(opinion)}", flush=True)
    review_id = str(opinion.get("id") or "").strip()
    if not review_id.isdigit():
        raise ValueError("Відгук без коректного ID")
    dt = _date(opinion.get("dateCreated" if kind == "product" else "date_created"))
    if not dt:
        raise ValueError("Відгук без розпізнаної дати")
    if kind == "product":
        parts = [opinion.get(k) for k in ("title", "text", "pros", "cons")]
        body = "\n".join(str(x).strip() for x in parts if isinstance(x, str) and x.strip())
        edit = ""
    else:
        body = "\n".join(filter(None, [str(opinion.get("comment_work") or "").strip(), *_company_tags(opinion)]))
        edit = ""
    return {"type": kind, "orderId": order_id, "reviewId": review_id,
            "date": dt.strftime("%d.%m.%Y"), "rating": rating,
            "text": body, "shopName": shop.name, "shopUrl": shop.url,
            "editUrl": edit if edit.startswith("https://") else "",
            "deletedByBuyer": _deleted_by_buyer(opinion)}


def collect_shop(shop, account, since, until=""):
    opener, csrf = _switch(account)
    start, end = parse_date(since), parse_date(until) if until else None
    output = {}
    for kind in ("company", "product"):
        found = []
        seen = set()
        previous = None
        ordered = True
        for page in range(1, 201):
            if kind == "company":
                data = _read(opener, "https://my.prom.ua/cms/opinions/company/list",
                             {"filters": [], "page": page, "pageType": "portal",
                              "perPage": 20, "searchQuery": "",
                              "sortingQuery": "default"}, csrf)
                opinions = data.get("opinions")
                pagination = data.get("pagination") or {}
            else:
                url = ("https://my.prom.ua/cms/opinions/product/prom/context"
                       "?page=%d&perPage=20&sortingQuery=-date_created&pageType=portal" % page)
                data = _read(opener, url)
                context = data.get("context") or {}
                opinions = context.get("opinions")
                pagination = context.get("pagination") or {}
            if not isinstance(opinions, list) or not isinstance(pagination, dict):
                raise ValueError("Неочікувана структура списку " + kind)
            if not opinions:
                break
            dates = []
            for opinion in opinions:
                if not isinstance(opinion, dict):
                    raise ValueError("Неочікуваний формат відгуку")
                cid = opinion.get("companyId" if kind == "product" else "company_id")
                if str(cid) != str(shop.id):
                    raise ValueError("Повернуто відгук іншого магазину")
                oid = opinion.get("id")
                if oid is None or str(oid) in seen:
                    raise ValueError("Повтор або відсутній ID відгуку на сторінці")
                seen.add(str(oid))
                dt = _date(opinion.get("dateCreated" if kind == "product" else "date_created"))
                if dt:
                    dates.append(dt)
                    if previous is not None and dt > previous:
                        ordered = False
                    previous = dt
                else:
                    ordered = False
                if dt and start <= dt and (end is None or dt <= end):
                    candidate = _candidate(opinion, kind, shop)
                    if candidate:
                        # Company edit links require a real order ID; never insert
                        # an opinion ID in its place.
                        if not candidate["deletedByBuyer"] and (kind == "product" or candidate["orderId"]):
                            try:
                                candidate["editUrl"] = _customer_review_url(
                                    opener, oid, candidate["orderId"], kind)
                            except (ValueError, urllib.error.HTTPError, urllib.error.URLError) as exc:
                                print(f"[negative-reviews] short URL unavailable for {kind} opinion {oid}: {type(exc).__name__}", flush=True)
                                candidate["editUrl"] = ""
                        else:
                            candidate["editUrl"] = ""
                        found.append(candidate)
            total = int(pagination.get("num_pages") or 1)
            if page >= total or (ordered and dates and max(dates) < start):
                break
        else:
            raise ValueError("Перевищено ліміт сторінок " + kind)
        output[kind] = found
    return output


def probe_analytics_pages(account):
    """Read-only HTTP probe, using the same authenticated sign-to session as review exports.

    No guessed internal API endpoints and no unverified numeric metrics.
    """
    import re
    from html import unescape
    opener, _csrf = _switch(account)
    output = {}
    for key, path in (("grades", "/cms/grades"), ("company_reviews", "/cms/opinions/company")):
        url = "https://my.prom.ua" + path
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Referer": "https://my.prom.ua/cms/",
        })
        try:
            with opener.open(req, timeout=20) as resp:
                content_type = resp.headers.get("Content-Type", "").split(";")[0].lower()
                body = resp.read(1500001)
                if len(body) > 1500000:
                    raise ValueError("Відповідь Prom завелика")
                text = body.decode("utf-8", errors="replace")
                if "html" not in content_type and "json" not in content_type:
                    raise ValueError("Неочікуваний формат відповіді: " + content_type)
                if re.search(r"captcha|cf-chl|just a moment|login-form", text, re.I):
                    raise ValueError("Prom повернув перевірку доступу або сторінку входу")
                # Report only diagnostic metadata; never return cookies, HTML or buyer data.
                output[key] = {
                    "status": "ok", "http_status": resp.status,
                    "content_type": content_type,
                    "bytes": len(body),
                    "contains_statistics_block": "statistics_block" in text,
                    "contains_company_statistics": "company_statistics" in text,
                    "contains_opinion_stats_block": "opinion_stats_block" in text,
                    "contains_successful_orders_label": "успішні замовлення" in unescape(text).lower(),
                }
        except urllib.error.HTTPError as exc:
            output[key] = {"status": "error", "http_status": exc.code,
                           "message": "Prom повернув HTTP " + str(exc.code)}
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            output[key] = {"status": "error", "message": str(exc)[:180]}
    return output


def collect_analytics_context(account):
    """Fetch the two verified Prom JSON context endpoints for one signed-in shop."""
    opener, _csrf = _switch(account)
    endpoints = {
        "grades": "https://my.prom.ua/cms/grades/context",
        "company_reviews": "https://my.prom.ua/cms/opinions/company/context",
    }
    return {name: _read(opener, url) for name, url in endpoints.items()}


def _find_named_metric(node, names):
    """Look up a metric by exact JSON key, recursively, without guessing values."""
    if isinstance(node, dict):
        for key in names:
            if key in node and type(node[key]) in (int, float):
                return node[key]
        for value in node.values():
            found = _find_named_metric(value, names)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_named_metric(value, names)
            if found is not None:
                return found
    return None


def extract_analytics_metrics(context):
    """Return only observed numeric fields, leaving unknown values unset."""
    grades = context["grades"]
    opinions = context["company_reviews"]
    monthly = {}
    def walk(node):
        if isinstance(node, dict):
            entries = node.get("countByMonth")
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    title = str(entry.get("periodTitle") or "").strip().casefold()
                    if title in ("позитивні", "негативні"):
                        monthly[title] = {
                            "month": entry.get("count1Month"),
                            "year": entry.get("count12Month"),
                        }
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(opinions)
    return {
        "monthlyPositive": monthly.get("позитивні", {}).get("month"),
        "monthlyNegative": monthly.get("негативні", {}).get("month"),
        "yearlyPositive": monthly.get("позитивні", {}).get("year"),
        "yearlyNegative": monthly.get("негативні", {}).get("year"),
        "successfulOrdersPercent": _find_named_metric(grades, ("completedOrdersPercent",)),
        "positiveReviewsPercent": _find_named_metric(grades, ("percentagePositiveReviews", "positiveOpinionsPercent")),
        "affectingOrders": _find_named_metric(grades, ("orders_in_rating_count",)),
        "affectingCancellations": _find_named_metric(grades, ("canceled_orders_in_rating_count",)),
        "readyToShipPercent": _find_named_metric(grades.get("trustAssortmentData", {}).get("stats", {}), ("completedOrdersPercent",)) if isinstance(grades, dict) and isinstance(grades.get("trustAssortmentData"), dict) else _find_named_metric(grades, ("trustAssortmentData",)),
    }
