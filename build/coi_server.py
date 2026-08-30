import http.server, socketserver, sys
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy','same-origin')
        self.send_header('Cross-Origin-Embedder-Policy','require-corp')
        self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.send_header('Cache-Control','no-store')
        super().end_headers()
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8800
with socketserver.TCPServer(('127.0.0.1', port), H) as httpd:
    httpd.serve_forever()
