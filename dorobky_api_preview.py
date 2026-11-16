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
