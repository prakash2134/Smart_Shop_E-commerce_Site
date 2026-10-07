"""One-time setup: migrations, database, sample data, SQL dump."""
import os, shutil, sqlite3, subprocess, sys
R = os.path.dirname(os.path.abspath(__file__)); os.chdir(R)
def run(*a):
    print("->", *a); subprocess.check_call([sys.executable, *a])
if not os.path.exists(".env") and os.path.exists(".env.example"): shutil.copy(".env.example", ".env")
run("manage.py", "makemigrations", "shop")
run("manage.py", "migrate")
run("seed.py")
with open("database.sql", "w", encoding="utf-8") as f:
    for line in sqlite3.connect("db.sqlite3").iterdump(): f.write(line + "\n")
print("\nSetup complete. SQL dump written to database.sql. Next: python run_all.py")
