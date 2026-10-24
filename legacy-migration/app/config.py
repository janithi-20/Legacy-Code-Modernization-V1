import os

LEGACY_DSN = os.getenv("LEGACY_DSN", "postgresql://postgres:postgres@localhost:5433/legacy?connect_timeout=5")
CLOUD_DSN = os.getenv("CLOUD_DSN", "postgresql://postgres:postgres@localhost:5434/cloud?connect_timeout=5")