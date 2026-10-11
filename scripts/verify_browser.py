"""Host Chrome smoke check for the prepared stage-4 dashboard, using stdlib only."""
import base64
import json
import os
import socket
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

profile = Path(tempfile.mkdtemp(prefix="demandpilot-browser-", dir="/private/tmp"))
process = subprocess.Popen([
    os.getenv("CHROME_PATH", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"), "--headless=new", "--no-first-run",
    "--no-default-browser-check", "--disable-background-networking", "--disable-component-update",
    "--disable-sync", "--remote-debugging-port=0", f"--user-data-dir={profile}", "about:blank",
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def exact(sock, length):
    result = b""
    while len(result) < length:
        part = sock.recv(length - len(result))
        if not part:
            raise RuntimeError("Browser connection closed")
        result += part
    return result

try:
    for _ in range(100):
        if (profile / "DevToolsActivePort").exists():
            break
        time.sleep(0.2)
    port = int((profile / "DevToolsActivePort").read_text().splitlines()[0])
    pages = json.load(urlopen(f"http://127.0.0.1:{port}/json"))
    address = urlparse(next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page"))
    sock = socket.create_connection((address.hostname, address.port), timeout=20)
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall(f"GET {address.path} HTTP/1.1\r\nHost: {address.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
    header = b""
    while not header.endswith(b"\r\n\r\n"):
        header += exact(sock, 1)
    assert header.split(b" ")[1] == b"101", header
    sequence = 0
    def call(method, parameters=None):
        global sequence
        sequence += 1
        payload = json.dumps({"id": sequence, "method": method, "params": parameters or {}}).encode()
        length = len(payload)
        header = bytes([0x81, 0x80 | length]) if length < 126 else bytes([0x81, 0xFE]) + struct.pack("!H", length)
        mask = os.urandom(4)
        sock.sendall(header + mask + bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload)))
        while True:
            frame = exact(sock, 2)
            size = frame[1] & 127
            if size == 126:
                size = struct.unpack("!H", exact(sock, 2))[0]
            elif size == 127:
                size = struct.unpack("!Q", exact(sock, 8))[0]
            message = json.loads(exact(sock, size))
            if message.get("id") == sequence:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message["result"]
    def evaluate(expression):
        return call("Runtime.evaluate", {"expression": expression, "returnByValue": True})["result"].get("value")
    call("Page.enable")
    for label, width, height, mobile in [("desktop", 1280, 1400, False), ("mobile", 390, 844, True)]:
        call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": mobile})
        call("Page.navigate", {"url": "http://localhost:8501"})
        for _ in range(150):
            if evaluate("document.querySelectorAll('[data-testid=stMetric]').length === 4 && document.body.innerText.includes('274.01')"):
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Dashboard did not render")
        time.sleep(1)
        sizes = evaluate("({viewport:innerWidth, scroll:document.documentElement.scrollWidth, height:document.documentElement.scrollHeight, metrics:Array.from(document.querySelectorAll('[data-testid=stMetric]')).map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,width:e.getBoundingClientRect().width}))})")
        assert sizes["scroll"] <= sizes["viewport"], sizes
        if mobile:
            assert sizes["metrics"][0]["y"] < sizes["metrics"][1]["y"] < sizes["metrics"][2]["y"], sizes
        else:
            assert len({round(m["y"]) for m in sizes["metrics"][:3]}) == 1, sizes
        content_height = evaluate("Math.max(document.documentElement.scrollHeight, document.querySelector('[data-testid=stMain]').scrollHeight)")
        call("Emulation.setDeviceMetricsOverride", {"width": width, "height": content_height, "deviceScaleFactor": 1, "mobile": mobile})
        time.sleep(0.5)
        screenshot = call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                          "clip": {"x": 0, "y": 0, "width": width, "height": content_height, "scale": 1}})
        Path(f"artifacts/{label}_dashboard.png").write_bytes(base64.b64decode(screenshot["data"]))
        print(label, json.dumps(sizes), flush=True)
    sock.close()
finally:
    process.terminate()
    process.wait(timeout=15)
