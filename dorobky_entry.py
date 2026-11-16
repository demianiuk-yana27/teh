import parallel_web
from dorobky_fast import process_dorobky_fast

legacy = parallel_web.base.legacy
legacy.process_dorobky = lambda rework_slot: process_dorobky_fast(legacy, rework_slot)

app = parallel_web.app


# Read-only diagnostic endpoint; the existing rework export remains unchanged.
from dorobky_api_preview import preview_dorobky_api
app.add_url_rule("/dorobky/api-preview", "dorobky_api_preview", preview_dorobky_api, methods=["GET"])

from dorobky_api_preview import preview_dorobky_api_extended
app.add_url_rule("/dorobky/api-preview-extended", "dorobky_api_preview_extended", preview_dorobky_api_extended, methods=["GET"])

from dorobky_api_preview import preview_dorobky_status_scan
app.add_url_rule("/dorobky/api-status-scan", "dorobky_api_status_scan", preview_dorobky_status_scan, methods=["GET"])
