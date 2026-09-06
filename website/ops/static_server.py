#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial

ROOT='/var/lib/biella-website/current'
class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        path=self.path.split('?',1)[0]
        if path in ('/deployment.json','/data/investor-snapshot.json','/data/investor-deck-manifest.json'):
            self.send_header('Cache-Control','no-store, max-age=0')
        elif path.endswith(('.png','.jpg','.jpeg','.webp','.css','.js')):
            self.send_header('Cache-Control','public, max-age=300')
        else:
            self.send_header('Cache-Control','no-cache')
        self.send_header('X-Content-Type-Options','nosniff')
        super().end_headers()
    def log_message(self, fmt, *args):
        pass

server=ThreadingHTTPServer(('127.0.0.1',8790),partial(Handler,directory=ROOT))
server.serve_forever()
