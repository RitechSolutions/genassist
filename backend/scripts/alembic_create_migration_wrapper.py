import os
import re
import subprocess
import time
from alembic.config import Config
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALEMBIC_INI_PATH = os.path.join(BASE_DIR, "alembic.ini")

def get_versions_dir():
    alembic_cfg = Config(ALEMBIC_INI_PATH)
    script_location = alembic_cfg.get_main_option("script_location")
    return os.path.join(script_location, "versions")

VERSIONS_DIR = get_versions_dir()

def get_next_number():
    files = os.listdir(VERSIONS_DIR)
    numbered = [int(f[:5]) for f in files if re.match(r'^\d{5}_', f)]
    return max(numbered, default=0) + 1


def get_latest_generated_file(before_files):
    time.sleep(0.2)  # slight delay in case filesystem is slow
    after_files = set(os.listdir(VERSIONS_DIR))
    new_files = after_files - before_files
    new_py_files = [f for f in new_files if f.endswith('.py')]
    if not new_py_files:
        raise RuntimeError("No new migration file was created.")
    return new_py_files[0]


def create_migration(message: str):
    os.environ["MY_PROJECT_RUN_ALEMBIC"] = "1" # set to allow alembic migration because of condition in alembic/env.py

    before_files = set(os.listdir(VERSIONS_DIR))

    subprocess.run(["alembic", "revision", "--autogenerate", "-m", message], check=True)

    latest_file = get_latest_generated_file(before_files)
    # rev_hash = latest_file.split('_')[0]

    number = get_next_number()
    safe_msg = message.strip().replace(' ', '_').replace('-', '_')
    new_filename = f"{number:05d}_{safe_msg}.py"

    os.rename(
            os.path.join(VERSIONS_DIR, latest_file),
            os.path.join(VERSIONS_DIR, new_filename)
            )

    logger.info(f"Renamed {latest_file} → {new_filename}")
    os.environ["MY_PROJECT_RUN_ALEMBIC"] = "0"


if __name__ == "__main__":
    import sys


    if len(sys.argv) < 2:
        logging.info("Usage: python create_migration.py 'your message here'")
    else:
        create_migration(sys.argv[1])
