"""Read-only CRM API probe for the two rework statuses.

This intentionally does not replace the Selenium exporter. The CRM's status-filter
parameter and custom-field schema must be verified before production migration.
"""
import os
import requests
from flask import jsonify

STATUS_IDS = {"Доробка склад": 441, "Доробка ТТН": 137}
BASE_URL = "https://crm2006091.asteril.com/api/v3.1/"


def _probe_status(label, status_id, key):
    # API v3.1 supports orderId lookup in the existing integration, but the
    # list/status filter is not yet verified. Probe safe parameter variants.
    variants = [
        ("statusId", {"statusId": status_id, "limit": 5}),
        ("status", {"status": status_id, "limit": 5}),
        ("status_id", {"status_id": status_id, "limit": 5}),
        ("unfiltered", {"limit": 5}),
    ]
    attempts = []
    for variant, params in variants:
        try:
            response = requests.get(
                BASE_URL + "orders",
                params={"api_key": key, **params},
                timeout=25,
                allow_redirects=False,
            )
        except requests.RequestException:
            attempts.append({"variant": variant, "error": "network"})
            continue
        attempt = {"variant": variant, "http_status": response.status_code}
        if response.status_code != 200:
            attempts.append(attempt)
            continue
        try:
            data = response.json()
        except ValueError:
            attempt["error"] = "non_json"
            attempts.append(attempt)
            continue
        if not isinstance(data, dict):
            attempt["error"] = "unexpected_json"
            attempts.append(attempt)
            continue
        error = data.get("error")
        if data.get("success") is False or (error and error != [] and error != {}):
            attempt["error"] = "crm_error"
            attempts.append(attempt)
            continue
        orders = data.get("orders")
        if not isinstance(orders, list):
            attempt["error"] = "missing_orders"
            attempt["response_keys"] = sorted(str(k) for k in data)[:20]
            attempts.append(attempt)
            continue
        fields = sorted({str(k) for order in orders if isinstance(order, dict)
                         for k in order})
        observed = {}
        for field in ("status", "statusId", "status_id", "orderStatus", "order_status"):
            values = [order.get(field) for order in orders
                      if isinstance(order, dict) and field in order]
            if values and all(isinstance(v, (str, int)) for v in values):
                observed[field] = sorted({str(v)[:50] for v in values})[:8]
        status_values = {v for vals in observed.values() for v in vals}
        verified = variant != "unfiltered" and bool(orders) and bool(status_values) and status_values == {str(status_id)}
        attempt.update({"sample_count": len(orders), "field_names": fields,
                        "status_fields": observed, "filter_verified": verified})
        attempts.append(attempt)
        # No need to request more samples after a verified status filter.
        if verified:
            break
    return {"status": label, "status_id": status_id,
            "ok": any("field_names" in attempt for attempt in attempts),
            "attempts": attempts,
            "note": "Діагностика лише читання; без персональних даних і запису."}


def preview_dorobky_api():
    key = os.environ.get("ASTERIL_API_KEY", "").strip()
    if not key:
        return jsonify({"status": "error",
                        "message": "У Render не налаштовано ASTERIL_API_KEY."}), 503
    results = [_probe_status(label, status_id, key)
               for label, status_id in STATUS_IDS.items()]
    return jsonify({"status": "preview", "read_only": True,
                    "ready_to_replace_selenium": False, "results": results})

def _safe_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def _probe_pagination_and_fields(key):
    """Bounded, read-only sampling. Never return CRM order/customer values."""
    probes = []
    samples = {}
    for label, params in (
        ("first_page", {"limit": 5}),
        ("offset_5", {"limit": 5, "offset": 5}),
        ("page_2", {"limit": 5, "page": 2}),
    ):
        try:
            response = requests.get(
                BASE_URL + "orders", params={"api_key": key, **params},
                timeout=25, allow_redirects=False,
            )
            item = {"variant": label, "http_status": response.status_code}
            if response.status_code != 200:
                probes.append(item)
                continue
            try:
                data = response.json()
            except ValueError:
                item["error"] = "non_json"
                probes.append(item)
                continue
            if not isinstance(data, dict):
                item["error"] = "unexpected_json"
                probes.append(item)
                continue
            if data.get("success") is False or data.get("error") not in (None, "", [], {}):
                item["error"] = "crm_error"
                probes.append(item)
                continue
            orders = data.get("orders")
            if not isinstance(orders, list):
                item["error"] = "missing_orders"
                probes.append(item)
                continue
            # Compare IDs in memory only. Never return raw IDs or hashes.
            ids = [str(o.get("id")) for o in orders if isinstance(o, dict) and o.get("id") is not None]
            samples[label] = ids
            item["sample_count"] = len(orders)
            item["response_keys"] = sorted(str(k) for k in data.keys())[:30]
            item["status_counts"] = {
                str(status): sum(str(o.get("status")) == str(status) for o in orders if isinstance(o, dict))
                for status in (137, 441)
            }
            item["candidate_fields"] = {
                field: {
                    "present": sum(field in o for o in orders if isinstance(o, dict)),
                    "nonempty": sum(o.get(field) not in (None, "", [], {}) for o in orders if isinstance(o, dict)),
                    "types": sorted({_safe_type(o.get(field)) for o in orders if isinstance(o, dict) and field in o}),
                }
                for field in (
                    "responsible_id", "responsible_comment", "custom_koment_menegera",
                    "custom_kommnary_skladu", "shop_id", "status"
                )
            }
            probes.append(item)
        except requests.RequestException:
            probes.append({"variant": label, "error": "network"})
    baseline = samples.get("first_page")
    for item in probes:
        ids = samples.get(item["variant"])
        if baseline is not None and ids is not None and item["variant"] != "first_page":
            item["same_ids_as_first_page"] = ids == baseline
            item["overlap_with_first_page"] = len(set(ids) & set(baseline))
    return {"probes": probes, "pagination_verified": any(
        item.get("http_status") == 200 and item.get("sample_count", 0) > 0
        and item.get("overlap_with_first_page") == 0
        for item in probes if item["variant"] != "first_page"
    ), "note": "Діагностика обмежена трьома GET-запитами. Дані замовлень не повертаються."}


def preview_dorobky_api_extended():
    key = os.environ.get("ASTERIL_API_KEY", "").strip()
    if not key:
        return jsonify({"status": "error", "message": "Не налаштовано ASTERIL_API_KEY."}), 503
    return jsonify({"status": "preview", "read_only": True,
                    "ready_to_replace_selenium": False,
                    "diagnostics": _probe_pagination_and_fields(key)})
