from pathlib import Path

# The frontend is committed directly to netlify/index.html.
# This build step only validates the current page structure and must not
# rewrite generated markup.
p = Path('netlify/index.html')
if not p.exists():
    raise SystemExit('netlify/index.html is missing')

s = p.read_text(encoding='utf-8')
required = [
    'id="scripts"',
    'id="techfaq"',
    'id="ktv"',
    'id="reviews"',
    'id="dorobky"',
    'id="ordercount"',
    'id="negative-reviews"',
    'id="negative-analytics"',
]
missing = [marker for marker in required if marker not in s]
if missing:
    raise SystemExit('Missing required sections: ' + ', '.join(missing))

print('Netlify frontend validated successfully.')
