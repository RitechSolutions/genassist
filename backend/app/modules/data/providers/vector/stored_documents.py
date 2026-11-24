"""Documents as the vector store holds them: each one's pieces joined back in reading order."""

from collections import defaultdict
from typing import Any, Dict, List, Sequence

from ..models import StoredDocument

PIECE_MARK = "_chunk_"


def document_id_of(piece_id: str) -> str:
    """The piece's document: everything before its last mark, as a document's own name may hold one."""
    document_id, mark, _ = piece_id.rpartition(PIECE_MARK)
    return document_id if mark else piece_id


def position_of(piece_id: str) -> int:
    """Where the piece sits in its document; a piece without a number comes first."""
    _, mark, number = piece_id.rpartition(PIECE_MARK)
    return int(number) if mark and number.isdigit() else 0


def pieces_by_document(piece_ids: Sequence[str]) -> Dict[str, List[str]]:
    """Piece ids grouped by their document, each group in reading order."""
    grouped: Dict[str, List[str]] = defaultdict(list)
    for piece_id in piece_ids:
        grouped[document_id_of(piece_id)].append(piece_id)
    return {doc_id: sorted(ids, key=position_of) for doc_id, ids in grouped.items()}


def joined_document(doc_id: str, pieces: Sequence[Any]) -> StoredDocument:
    """One document from its stored pieces; its title is the name search results show."""
    in_order = sorted(pieces, key=lambda piece: position_of(piece.id))
    names = [piece.metadata.get("name") for piece in in_order]
    title = next((name for name in names if name), None)
    return StoredDocument(id=doc_id, title=title, content="\n".join(piece.content for piece in in_order))
