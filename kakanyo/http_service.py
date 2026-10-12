"""Local authenticated HTTP binding for the Kakanyo MCP JSON-RPC interface."""
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import ContractError
from .mcp import MAX_MESSAGE, process
from .workspace import Workspace

def create_server(workspace, host="127.0.0.1", port=8765, token=None):
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ContractError("Reference HTTP service is loopback-only; use an approved HTTPS gateway for remote clients")
    if not isinstance(token,str) or len(token)<24:
        raise ContractError("Set a long random KAKANYO_HTTP_TOKEN before starting HTTP service")
    ws=Workspace(workspace)
    class Handler(BaseHTTPRequestHandler):
        server_version="Kakanyo/0.2"
        def log_message(self,*args): pass
        def send_json(self,status,data):
            body=json.dumps(data,ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self):
            if self.path=="/health":
                self.send_json(200,{"service":"kakanyo","running":True})
            else:self.send_json(404,{"error":"Not found"})
        def do_POST(self):
            if self.path!="/mcp":
                self.send_json(404,{"error":"Not found"});return
            if self.headers.get("Origin"):
                self.send_json(403,{"error":"Cross-origin requests disabled"});return
            if not hmac.compare_digest(self.headers.get("Authorization",""),"Bearer "+token):
                self.send_json(401,{"error":"Unauthorized"});return
            try:
                size=int(self.headers.get("Content-Length","0"))
                if size<1 or size>MAX_MESSAGE:
                    self.send_json(413,{"error":"Invalid request length"});return
                result=process(ws,json.loads(self.rfile.read(size)))
            except (ValueError,UnicodeDecodeError):
                self.send_json(400,{"error":"Invalid JSON"});return
            self.send_json(200,result if result is not None else {})
    server=ThreadingHTTPServer((host,port),Handler)
    server.daemon_threads=True
    return server

def serve(workspace,host="127.0.0.1",port=8765):
    server=create_server(workspace,host,port,os.environ.get("KAKANYO_HTTP_TOKEN"))
    try:server.serve_forever(poll_interval=0.25)
    finally:server.server_close()
