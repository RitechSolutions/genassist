from pathlib import Path
from typing import List, Tuple

from tqdm.auto import tqdm


def load_txt(path: Path) -> Tuple[str, str]:
    """
    Loads a single txt file and returns a (filename, text) tuple.
    """
    with open(path, encoding='utf-8') as f:
        text = f.read().strip()
    return (path.stem, text)


def load_file(path: Path) -> Tuple[str, str]:
    """
    Loads a single file. Calls the appropriate function based on its extension.
    """
    if path.suffix == '.txt':
        return load_txt(path)
    else:
        raise NotImplementedError(f"Extensions ending in {path.suffix} not supported yet.")


def load_folder(path: Path, ext: str | None = None) -> List[Tuple[str, str]]:
    """
    Loads documents from the folder. If ext is provided, will load only
    those files ending in ext (e.g., 'txt').
    """
    path = Path(path)
    if not ext.startswith('.'):
        ext = f".{ext}"

    docs: List[Tuple[str, str]] = []
    for file in tqdm(path.iterdir(), desc="Reading documents"):
        if file.suffix == ext:
            node = load_file(file)
            docs.append(node)

    return docs
