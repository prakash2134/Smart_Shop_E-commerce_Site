"""Starts Django admin (8011), FastAPI (8010) and the storefront (5500) together. Ctrl+C stops all."""
import os, socket, subprocess, sys, time, webbrowser
R = os.path.dirname(os.path.abspath(__file__)); os.chdir(R)
if not os.path.exists("db.sqlite3"): sys.exit("Database not found. Run: python setup_project.py")
PORTS = {"Django admin": 8011, "FastAPI": 8010, "Storefront": 5500}
for name, port in PORTS.items():
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            sys.exit(f"Port {port} ({name}) is already in use. Stop whatever is using it and try again.")
py = sys.executable
procs = [subprocess.Popen([py, "manage.py", "runserver", "8011", "--noreload"]),
         subprocess.Popen([py, "-m", "uvicorn", "api.main:app", "--port", "8010"]),
         subprocess.Popen([py, "-m", "http.server", "5500", "--directory", "frontend"])]
time.sleep(3)
print("\nStorefront : http://localhost:5500\nAPI docs   : http://localhost:8010/docs\nAdmin      : http://localhost:8011/dashboard/  (admin / admin123)\nPress Ctrl+C to stop.\n")
webbrowser.open("http://localhost:5500")
try:
    while all(p.poll() is None for p in procs): time.sleep(1)
    print("A server stopped. Scroll up to see the error.")
except KeyboardInterrupt: pass
finally:
    for p in procs: p.terminate()
