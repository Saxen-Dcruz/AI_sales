import os
from sqlalchemy import create_engine, text

# Read env variables
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_SERVER")
DB_PORT = os.getenv("POSTGRES_PORT")
DB_NAME = os.getenv("POSTGRES_DB")

# Build connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"🔌 Connecting to DB at {DB_HOST}:{DB_PORT}...")

engine = create_engine(DATABASE_URL)

scripts_path = "app/scripts/migrations"

files = sorted(f for f in os.listdir(scripts_path) if f.endswith(".sql"))

with engine.connect() as conn:
    for file in files:
        file_path = os.path.join(scripts_path, file)
        print(f"🚀 Running {file}...")

        with open(file_path, "r") as f:
            sql = f.read()

        conn.execute(text(sql))
        conn.commit()

print("✅ All scripts executed successfully.")