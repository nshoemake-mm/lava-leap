#!/usr/bin/env python3
"""One-time port: wrap the artifact-format game file into a standalone PWA index.html.
Usage: python3 port.py path/to/lava-leap.html > index.html"""
import sys, re
src = open(sys.argv[1], encoding='utf-8').read()
# Strip a published-artifact wrapper if present (doctype ... <body> on line 1, </body></html> at end).
if src.lstrip().lower().startswith('<!doctype'):
    src = src[src.index('<body>') + len('<body>'):].lstrip('\n')
    src = re.sub(r'\s*</body>\s*</html>\s*$', '\n', src)
src = re.sub(r'<meta name="claude:[^>]*>\n?', '', src)
m = re.search(r'<title>.*?</title>\n?', src)
src = src[m.end():] if m else src
head = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">
<title>Lava Leap</title>
<meta name="theme-color" content="#1a1220">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Lava Leap">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<link rel="icon" type="image/png" href="icons/icon-192.png">
'''
# split head-ish content (links/style) from body content at first non-head tag
idx = re.search(r'</style>\s*', src)
cut = idx.end() if idx else 0
tail = '''
<script>
if ('serviceWorker' in navigator) addEventListener('load', () => navigator.serviceWorker.register('sw.js'));
</script>
</body>
</html>
'''
print(head + src[:cut] + '</head>\n<body>\n' + src[cut:] + tail, end='')
