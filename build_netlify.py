from pathlib import Path

# Content is now committed directly to netlify/index.html and the data files.
# Keep the Netlify build step as a lightweight validation only, so repeated
# deploys never try to rewrite already-generated markup.
p = Path('netlify/index.html')
if not p.exists():
    raise SystemExit('netlify/index.html is missing')

s = p.read_text(encoding='utf-8')
required = [
    'id="scripts"',
    'id="ktv"',
    'id="reviews"',
    'id="dorobky"',
    'id="negative"',
]
missing = [marker for marker in required if marker not in s]
if missing:
    raise SystemExit('Missing required sections: ' + ', '.join(missing))

print('Netlify frontend validated successfully.')
