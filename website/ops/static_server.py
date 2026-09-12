#!/usr/bin/env python3
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT='/var/lib/biella-website/current'

class Handler(SimpleHTTPRequestHandler):
    DASHBOARD_HOST='taghdisilabs.digital'
    MINITZ_HOST='minitz.taghdisilabs.digital'
    SITE_ROUTES=(
        '/', '/index.html', '/experience', '/capabilities', '/system', '/now',
        '/locker', '/founder', '/film', '/final-film',
    )

    def _map_public_site(self):
        host=self.headers.get('Host','').split(':',1)[0].lower()
        raw_path=self.path.split('?',1)[0]
        path=raw_path[:-1] if raw_path.endswith('/') and raw_path!='/' else raw_path
        if host in (self.DASHBOARD_HOST,self.MINITZ_HOST) and path in self.SITE_ROUTES:
            suffix=''
            if '?' in self.path:
                suffix='?'+self.path.split('?',1)[1]
            self.path='/live/index.html'+suffix

    def do_GET(self):
        self._map_public_site()
        super().do_GET()

    def do_HEAD(self):
        self._map_public_site()
        super().do_HEAD()

    def end_headers(self):
        path=self.path.split('?',1)[0]
        if path in ('/deployment.json','/data/investor-snapshot.json','/data/investor-deck-manifest.json','/data/locker-index.json'):
            self.send_header('Cache-Control','no-store, max-age=0')
        elif path.endswith(('.png','.jpg','.jpeg','.webp','.css','.js','.mp4')):
            self.send_header('Cache-Control','public, max-age=300')
        else:
            self.send_header('Cache-Control','no-cache')
        self.send_header('X-Content-Type-Options','nosniff')
        super().end_headers()

    def log_message(self, fmt, *args):
        pass

server=ThreadingHTTPServer(('127.0.0.1',8790),partial(Handler,directory=ROOT))
server.serve_forever()
