import parallel_web
from dorobky_fast import process_dorobky_fast

legacy = parallel_web.base.legacy
legacy.process_dorobky = lambda rework_slot: process_dorobky_fast(legacy, rework_slot)

app = parallel_web.app
