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
    try:
        response = requests.get(
            BASE_URL + "orders",
            params={"api_key": key, "statusId": status_id, "limit": 5},
            timeout=25,
            allow_redirects=False,
        )
    except requests.RequestException:
        return {"status": label, "status_id": status_id, "ok": False,
                "error": "CRM недоступна (мережевий збій)."}
    if response.status_code != 200:
        return {"status": label, "status_id": status_id, "ok": False,
                "http_status": response.status_code,
                "error": "CRM повернула HTTP-помилку."}
    try:
        data = response.json()
    except ValueError:
        return {"status": label, "status_id": status_id, "ok": False,
                "error": "CRM повернула не JSON."}
    if not isinstance(data, dict) or data.get("success") is False or data.get("error"):
        return {"status": label, "status_id": status_id, "ok": False,
                "error": "CRM відхилила запит або повернула неочікувану відповідь."}
    orders = data.get("orders")
    if not isinstance(orders, list):
        return {"status": label, "status_id": status_id, "ok": False,
                "error": "У відповіді немає масиву orders.",
                "response_keys": list(data)[:20]}
    # Do not expose order IDs, names, phones, comments or arbitrary values.
    field_names = sorted({str(k) for order in orders if isinstance(order, dict)
                          for k in order.keys()})
    status_fields = {
        k: sorted({str(order[k])[:50] for order in orders
                   if isinstance(order, dict) and k in order
                   and isinstance(order[k], (int, str))})[:8]
        for k in ("status", "statusId", "status_id", "orderStatus", "order_status")
        if any(isinstance(order, dict) and k in order for order in orders)
    }
    observed_ids = {str(v) for vals in status_fields.values() for v in vals}
    # A sample with a mismatching status indicates the API ignored the filter.
    filter_verified = bool(orders) and bool(observed_ids) and observed_ids == {str(status_id)}
    return {"status": label, "status_id": status_id, "ok": True,
            "sample_count": len(orders), "field_names": field_names,
            "status_fields": status_fields,
            "filter_verified": filter_verified,
            "note": "Лише перші 5 записів; без запису в таблицю."}


def preview_dorobky_api():
    key = os.environ.get("ASTERIL_API_KEY", "").strip()
    if not key:
        return jsonify({"status": "error",
                        "message": "У Render не налаштовано ASTERIL_API_KEY."}), 503
    results = [_probe_status(label, status_id, key)
               for label, status_id in STATUS_IDS.items()]
    return jsonify({"status": "preview", "read_only": True,
                    "ready_to_replace_selenium": False, "results": results})
