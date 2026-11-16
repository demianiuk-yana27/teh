import parallel_web
from dorobky_fast import process_dorobky_fast

legacy = parallel_web.base.legacy
legacy.process_dorobky = lambda rework_slot: process_dorobky_fast(legacy, rework_slot)

app = parallel_web.app


# Read-only diagnostic endpoint; the existing rework export remains unchanged.
from dorobky_api_preview import preview_dorobky_api
app.add_url_rule("/dorobky/api-preview", "dorobky_api_preview", preview_dorobky_api, methods=["GET"])
