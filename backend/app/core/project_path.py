from pathlib import Path

# This will give the absolute path to the project root, assuming this file is in app/core/
PROJECT_PATH = Path(__file__).resolve().parent.parent.parent

DATA_VOLUME = PROJECT_PATH / "datavolume"
DATA_VOLUME.mkdir(parents=True, exist_ok=True)

# print(f"Project path: {PROJECT_PATH}")
# print(f"Data Volume: {DATA_VOLUME}")