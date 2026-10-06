import os

CLOUD_DB_URL = os.environ.get(
    "CLOUD_DB_URL", "postgresql://postgres:postgres@cloud-db:5432/cloud")