import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import faiss
import igraph as ig
import numpy as np
import numpy.typing as npt
from fastapi import UploadFile
from nltk.tokenize import sent_tokenize
from tqdm.auto import tqdm
from transformers import AutoTokenizer

from . import embedding
from .chunking.base import Chunker
from .clustering.base import Clusterer
from .config import DEFAULT_METRIC, DEFAULT_N_NEIGHBORS
from .embedding.base import Embedder
from .generation.base import Generator
from .graph.knn_graph import KNNGraphBuilder
from .index.base import Indexer
from .retrieval.base import Retriever
from .utils import get_logger

_logger = get_logger(__name__)

__all__ = [
    'Legra',
]


class Legra:
    """
    Main orchestrator for Legra.

    Steps:
      1. Load documents (from folder or list).
      2. Chunk documents (using a Chunker).
      3. Embed all chunks (using an Embedder).
      4. Build an Index (using an Indexer).
      5. Build a kNN Graph (using KNNGraphBuilder).
      6. Identify communities (using a Clusterer) and attach to chunk metadata.
      7. On query:
         a. Retrieve top-k chunks (using a Retriever).
         b. Generate answer (using a Generator) or fallback to returning raw chunks.
    """

    def __init__(
        self,
        doc_folder: Path,
        chunker: Chunker,
        embedder: Embedder,
        indexer: Indexer,
        max_tokens: int,
        graph_builder: KNNGraphBuilder | None = None,
        clusterer: Clusterer | None = None,
        retriever: Retriever | None = None,
        generator: Generator | None = None,
        extension: str = "txt",
        n_neighbors: int = DEFAULT_N_NEIGHBORS,
        metric: str = DEFAULT_METRIC,
    ) -> None:
        self.doc_folder = doc_folder
        self.chunker = chunker
        self.embedder = embedder
        self.indexer = indexer
        self.max_tokens = max_tokens
        self.graph_builder = graph_builder or KNNGraphBuilder(
            n_neighbors=n_neighbors, metric=metric
        )
        self.clusterer = clusterer
        self.retriever = retriever  # may fill after indexing
        self.generator = generator
        self.extension = extension

        # Internal storage
        self.docs_meta: List[Dict[str, Any]] = []
        self.emb_matrix: npt.NDArray | None = None

        self.community_summaries: Dict[int, str] = {}

    def _load_folder(self) -> List[Dict[str, Any]]:
        """
        Walk through self.doc_folder, load all files with self.extension.
        Returns:
            List of dicts: { 'doc_id': relative_path_str, 'text': file_contents }.
        """
        docs: List[Dict[str, Any]] = []

        for root, _, files in os.walk(self.doc_folder):
            for fname in files:
                if fname.lower().endswith(self.extension.lower()):
                    path = Path(root) / fname
                    doc_id = str(path.relative_to(self.doc_folder))
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    docs.append({"doc_id": doc_id, "text": text})

        _logger.info(f"Loaded {len(docs)} documents from {self.doc_folder}")
        return docs

    def _load_folder(self, files: list[UploadFile]) -> List[Dict[str, Any]]:
        """
        Walk through self.doc_folder, load all files with self.extension.
        Returns:
            List of dicts: { 'doc_id': relative_path_str, 'text': file_contents }.
        """
        docs: list[dict[str, Any]] = []

        for file in files:
            content = file.file.read()  # read the file contents as bytes
            text = content.decode("utf-8", errors="ignore")  # decode to string
            docs.append({
                "doc_id": file.filename,
                "text": text
                })

        _logger.info(f"Loaded {len(docs)} documents from {self.doc_folder}")
        return docs


    def add_document(self, doc_id: str, extracted_text: str, metadata: dict) -> None:
        """
        Append `doc_id` to the knowledge-base identified by metadata['kb_id'].
        Only embeddings & docs_meta are updated.  Index/graph will be rebuilt later.
        """
        # Handle updates
        self.delete_document(doc_id)

        kb_id = metadata.get("kb_id")
        if kb_id is None:
            raise ValueError("metadata must contain 'kb_id'")

        _logger.info(f"Adding document {doc_id} to KB {kb_id} …")

        # ------------------------------------------------------------------ #
        # 0. Load existing embeddings & meta for this KB (if they exist)     #
        # ------------------------------------------------------------------ #
        kb_dir = Path("legra_data").joinpath(kb_id)
        if kb_dir.exists():
            with open(kb_dir / "docs_meta.json", encoding="utf-8") as f:
                existing_meta: list[dict] = json.load(f)
            existing_embs: np.ndarray = np.load(kb_dir / "emb_matrix.npy")
        else:
            existing_meta = []
            existing_embs = np.empty((0, self.embedder.dimension), dtype=np.float32)
            kb_dir.mkdir(parents=True, exist_ok=True)

        # ------------------------------------------------------------------ #
        # 1. Chunk the new document                                          #
        # ------------------------------------------------------------------ #
        chunks: list[str] = self.chunker(extracted_text)  # List[str]
        _logger.info(f"Chunked into {len(chunks)} pieces.")

        # 2. Embed
        new_embs = self.embedder.encode(chunks)
        _logger.info("Embedding completed.")

        # 3. Build per-chunk metadata
        new_meta = [
            {
                **metadata,  # carries kb_id + any other custom fields
                "doc_id": doc_id,
                "chunk_ix": ix,
                "text": txt,
                "embedding": emb,  # kept in RAM, stripped before save()
                }
            for ix, (txt, emb) in enumerate(zip(chunks, new_embs))
            ]

        # ------------------------------------------------------------------ #
        # 4. Concatenate with previous corpus                                #
        # ------------------------------------------------------------------ #
        self.docs_meta = existing_meta + new_meta
        self.emb_matrix = (
            new_embs if existing_embs.size == 0
            else np.vstack([existing_embs, new_embs])
        )

        _logger.info(f"KB {kb_id} now has {len(self.docs_meta)} chunks total.")

        # ------------------------------------------------------------------ #
        # 5. Persist embeddings + meta         #
        # ------------------------------------------------------------------ #
        if metadata.get("finalize", False):
            # index / graph
            _logger.info("Finalizing KB.")

            self.complete_index_graph(kb_id)
            self.save(kb_id, full=True)
        else :
            self.save(kb_id, full=False)  # writes docs_meta.json + emb_matrix.npy
            _logger.info("Embeddings saved.")


    def delete_document(self, doc_id: str) -> bool:
        """
        Delete all chunks belonging to `doc_id` from the knowledge base `kb_id`.
        • Only docs_meta.json and emb_matrix.npy are rewritten.
        • The FAISS index / graph / community files are deleted because they are
          now stale; your separate “re-index” endpoint will recreate them later.
        Returns
        -------
        True  – deletion succeeded (or doc_id not present)
        False – I/O or JSON errors occurred
        """
        kb_id = (doc_id.split("#", 1)[0])[3:] # remove part after # and remove 'KB:' to extract kb_id

        kb_dir = Path("legra_data") / kb_id
        if not kb_dir.exists():
            _logger.warning(f"delete_document: KB {kb_id} does not exist.")
            return False

        try:
            # -----------------------------------------------------------------
            # 1. Load current meta + embeddings
            # -----------------------------------------------------------------
            with open(kb_dir / "docs_meta.json", encoding="utf-8") as f:
                meta: List[Dict[str, Any]] = json.load(f)

            emb = np.load(kb_dir / "emb_matrix.npy")

            # -----------------------------------------------------------------
            # 2. Build mask of rows to *keep*
            # -----------------------------------------------------------------
            keep_mask = [m["doc_id"] != doc_id for m in meta]
            if all(keep_mask):
                _logger.info(f"delete_document: {doc_id} not found in KB {kb_id}.")
                return True  # nothing to delete

            # Filter metadata and embeddings
            new_meta = [m for m, keep in zip(meta, keep_mask) if keep]
            new_emb = emb[keep_mask]

            # If KB becomes empty, wipe directory entirely
            if not new_meta:
                import shutil

                shutil.rmtree(kb_dir)
                _logger.info(f"delete_document: removed last document; "
                             f"KB {kb_id} directory deleted.")
                return True

            # -----------------------------------------------------------------
            # 3. Save stripped corpus back to disk
            # -----------------------------------------------------------------
            # Strip embeddings before saving docs_meta.json
            meta_for_save = [{k: v for k, v in m.items() if k != "embedding"}
                             for m in new_meta]

            with open(kb_dir / "docs_meta.json", "w", encoding="utf-8") as f:
                json.dump(meta_for_save, f, ensure_ascii=False, indent=2)

            np.save(kb_dir / "emb_matrix.npy", new_emb)

            # -----------------------------------------------------------------
            # 4. Remove stale index / graph files
            # -----------------------------------------------------------------
            for stale in ("faiss_index.bin", "graph.graphml",
                          "community_summaries.json"):
                p = kb_dir / stale
                if p.exists():
                    p.unlink()

            # -----------------------------------------------------------------
            # 5. Refresh in-memory state of *this* instance
            # -----------------------------------------------------------------
            self.docs_meta = new_meta
            self.emb_matrix = new_emb

            # the index / graph / labels are now invalid; clear them
            if hasattr(self, "indexer"):
                self.indexer.index = None
            self.graph = None
            self.community_labels = None

            _logger.info(f"delete_document: removed {doc_id} from KB {kb_id}. "
                         f"{len(new_meta)} chunks remain.")
            return True

        except Exception as e:
            _logger.exception(f"delete_document failed: {e}")
            return False


    def complete_index_graph(self, kb_id: str):
        # 1. Build index
        _logger.info("Building vector index...")
        self.indexer.build_index(self.emb_matrix)

        # 2. Build graph
        _logger.info("Constructing kNN graph...")
        graph, edges = self.graph_builder.fit(self.emb_matrix)
        self.graph = graph
        self.edges = edges

        # 3. Cluster if provided
        if self.clusterer is not None:
            _logger.info("Running community detection...")
            labels = self.clusterer.find_partition(graph)
            for idx, label in enumerate(labels):
                self.docs_meta[idx]["community"] = label
            self.community_labels = labels

        # 4. Prepare retriever if not provided
        if self.retriever is None:
            from .retrieval.neighbor_retriever import NeighborRetriever

            self.retriever = NeighborRetriever(
                    embedder=self.embedder, indexer=self.indexer, docs_meta=self.docs_meta
                    )
        _logger.info("Vector index completed.")
        _logger.info("Saving full indexed graph...")
        self.save(kb_id, True)
        _logger.info("Saving completed.")



    def index(self, files: list[UploadFile]) -> None:
        """
        Full indexing pipeline:
          1. Load documents
          2. Chunk each doc
          3. Embed each chunk
          4. Build index
          5. Build kNN graph
          6. Cluster communities if clusterer provided
        """
        # 1. Load
        raw_docs = self._load_folder(files)
        texts = [d["text"] for d in raw_docs]
        doc_ids = [d["doc_id"] for d in raw_docs]

        # 2. Chunk
        docs_chunked: List[List[str]] = self.chunker(texts)  # List of chunk lists
        # Flatten while keeping track of meta
        meta_list: List[Dict[str, Any]] = []
        flattened_chunks: List[str] = []
        for doc_id, chunks in zip(doc_ids, docs_chunked):
            for idx, chunk in enumerate(chunks):
                meta_list.append({"doc_id": doc_id, "chunk_ix": idx, "text": chunk})
                flattened_chunks.append(chunk)

        # 3. Embed
        _logger.info("Embedding all chunks...")
        embeddings = self.embedder.encode(flattened_chunks)

        # Attach embeddings to meta
        for i, emb in enumerate(embeddings):
            meta_list[i]["embedding"] = emb

        self.docs_meta = meta_list
        self.emb_matrix = embeddings

        # 4. Build index
        _logger.info("Building vector index...")
        self.indexer.build_index(embeddings)

        # 5. Build graph
        _logger.info("Constructing kNN graph...")
        graph, edges = self.graph_builder.fit(embeddings)
        self.graph = graph
        self.edges = edges

        # 6. Cluster if provided
        if self.clusterer is not None:
            _logger.info("Running community detection...")
            labels = self.clusterer.find_partition(graph)
            for idx, label in enumerate(labels):
                self.docs_meta[idx]["community"] = label
            self.community_labels = labels

        # 7. Prepare retriever if not provided
        if self.retriever is None:
            from .retrieval.neighbor_retriever import NeighborRetriever

            self.retriever = NeighborRetriever(
                embedder=self.embedder, indexer=self.indexer, docs_meta=self.docs_meta
            )

        _logger.info("Indexing pipeline completed.")

    def generate_node_summaries(
        self,
        generator: Generator | None = None,
        **kwargs,
    ) -> List[str]:
        """
        Generate summaries for each node using the provided generator.
        """
        generator = generator or self.generator
        if generator is None:
            raise ValueError("Cannot generate summaries without a generator.")

        texts = [doc["text"] for doc in self.docs_meta]
        summaries = [generator.generate(f"Summarize: {text}", **kwargs) for text in texts]

        for doc, summary in zip(self.docs_meta, summaries):
            doc["summary"] = summary

        return summaries

    def generate_community_summaries(
        self,
        generator: Generator | None = None,
        **kwargs,
    ) -> Dict[int, str]:
        """
        Generate summaries for each community by aggregating node summaries.
        """
        generator = generator or self.generator
        if generator is None:
            raise ValueError("Cannot generate summaries without a generator.")
        if not hasattr(self, "community_labels"):
            raise RuntimeError("Community labels not found. Run index() first.")

        # Form communities
        communities: Dict[int, List[str]] = defaultdict(list)
        for meta in self.docs_meta:
            comm = meta["community"]
            summary = meta.get("summary", meta["text"])
            communities[comm].append(summary)

        # Summarize communities
        summaries: Dict[int, str] = {}
        bar = tqdm(communities.items(), desc="Generating community summaries")
        for comm, texts in bar:
            combined_text = "\n".join(texts)
            comm_summary = self._summarize(generator, combined_text, max_tokens=self.max_tokens)
            summaries[comm] = comm_summary

        self.community_summaries = summaries
        return summaries

    def _summarize(
        self,
        generator: Generator,
        text: str,
        max_tokens: int,
        tokenizer: AutoTokenizer | None = None,
    ) -> str:
        """
        Util method to summarize long pieces of text by breaking them into
        chunks until they fit the context length.
        """
        if tokenizer is None:
            if not hasattr(generator, 'tokenizer'):
                raise ValueError(
                    f"Generator of type {generator.__class__.__name__} "
                    "does not have a tokenizer. Please pass one explicitly."
                )
            tokenizer = cast(AutoTokenizer, generator.tokenizer)

        sents = sent_tokenize(text)

        # Replace sentence preprocessing with recursive splitter
        def split_long_sentence(sent: str) -> List[str]:
            token_ids = tokenizer.encode(sent, add_special_tokens=True)
            if len(token_ids) < max_tokens - 100:
                return [sent]
            mid = len(sent) // 2
            left, right = sent[:mid], sent[mid:]
            return split_long_sentence(left) + split_long_sentence(right)

        processed_sents: List[str] = []
        for sent in sents:
            processed_sents.extend(split_long_sentence(sent))

        chunks = []
        current_chunk = []
        current_len = 0

        # 1) Get all the chunks that fit the context window.
        for sent in processed_sents:
            token_ids = tokenizer.encode(sent, add_special_tokens=True)
            if current_len + len(token_ids) < max_tokens - 100:
                current_chunk.append(sent)
                current_len += len(token_ids)
            else:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sent]
                current_len = len(token_ids)

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        # 2) Generate partial summaries.
        partial_summaries = []
        for sub_chunk in tqdm(chunks, desc="Summarizing chunks..."):
            partial_summary = generator.generate(f"Summarize: {sub_chunk}")
            partial_summaries.append(partial_summary)

        all_partial_summaries = "\n".join(partial_summaries)
        comm_summary = generator.generate(f"Summarize: {all_partial_summaries}")
        return comm_summary

    def save(self, path: str | Path, full: bool) -> None:
        """
        Save the current state to disk. Writes:
          - docs_meta.json (without embeddings)
          - emb_matrix.npy
          - faiss_index.bin (if using FaissFlatIndexer)
          - graph.graphml
          - community_summaries.json (if any)
        """
        base = Path("legra_data")
        path = base.joinpath(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save docs_meta without embeddings
        docs_meta_to_save: List[Dict[str, Any]] = []

        for meta in self.docs_meta:
            meta_copy = meta.copy()
            meta_copy.pop("embedding", None)
            docs_meta_to_save.append(meta_copy)

        with open(path / "docs_meta.json", "w", encoding="utf-8") as f:
            json.dump(docs_meta_to_save, f, ensure_ascii=False, indent=2)

        with open(path / "legra.json", "w", encoding="utf-8") as f:
            json.dump({"max_tokens": self.max_tokens}, f)

        # Save embeddings matrix
        np.save(path / "emb_matrix.npy", self.emb_matrix)

        with open(path / "embedder.json", "w", encoding="utf-8") as f:
            json.dump(
                {"class": self.embedder.__class__.__name__,
                 "model_name": self.embedder.model_name},
                f,
            )

        # Save generator config if present
        if self.generator is not None:
            gen_config = {
                "class": self.generator.__class__.__name__,
                "model_name": self.generator.model_name,
                "device": self.generator.device,
                "truncate_context_size": self.generator.truncate_context_size,
                }
            with open(path / "generator.json", "w", encoding="utf-8") as f:
                json.dump(gen_config, f, ensure_ascii=False, indent=2)

        # Save retriever config if present
        if self.retriever is not None:
            retriever_config = {
                "class": self.retriever.__class__.__name__,
                }
            with open(path / "retriever.json", "w", encoding="utf-8") as f:
                json.dump(retriever_config, f, ensure_ascii=False, indent=2)

        if full:
            # If we have indexed and created the graph
            # Save index if FaissFlatIndexer
            if isinstance(self.indexer, Indexer) and hasattr(self.indexer, "index"):
                try:
                    faiss.write_index(self.indexer.index, str(path / "faiss_index.bin"))
                except Exception:
                    pass

            # Save graph to GraphML
            self.graph.write_graphml(str(path / "graph.graphml"))

            # Save community summaries if exist
            if self.community_summaries:
                with open(path / "community_summaries.json", "w", encoding="utf-8") as f:
                    json.dump(self.community_summaries, f, ensure_ascii=False, indent=2)


    @classmethod
    def load(cls, path: str | Path, load_reason: str = "search") -> "Legra":
        """
        Load a knowledge-base snapshot from disk.

        Directory layout (some files may be missing):
            docs_meta.json                # REQUIRED
            emb_matrix.npy                # REQUIRED
            faiss_index.bin               # OPTIONAL
            graph.graphml                 # OPTIONAL
            community_summaries.json      # OPTIONAL
            embedder.json                 # REQUIRED
            legra.json                    # REQUIRED  (contains max_tokens)
        """
        kb_path = Path("legra_data").joinpath(path)

        # 1. docs_meta + embeddings  ------------------------------------
        with open(kb_path / "docs_meta.json", encoding="utf-8") as f:
            docs_meta: List[Dict[str, Any]] = json.load(f)

        emb_matrix: npt.NDArray = np.load(kb_path / "emb_matrix.npy")

        # 2. (optional) graph  ------------------------------------------
        graph_file = kb_path / "graph.graphml"
        graph: Optional[ig.Graph] = (
            ig.Graph.Read_GraphML(str(graph_file)) if graph_file.exists() else None
        )

        # 3. embedder  ---------------------------------------------------
        with open(kb_path / "embedder.json", encoding="utf-8") as f:
            econf = json.load(f)
        embedder_cls = getattr(embedding, econf["class"])
        embedder = embedder_cls(model_name=econf["model_name"])

        # 4. generator (optional) ----------------------------------------
        from app.modules.data.providers.legra.generation import hf_generation  # adjust import as needed

        gen_file = kb_path / "generator.json"
        generator: Optional[Generator] = None
        if gen_file.exists():
            with open(gen_file, encoding="utf-8") as f:
                gconf = json.load(f)
            generator_cls = getattr(hf_generation, gconf["class"])
            generator = generator_cls(
                    model_name=gconf["model_name"],
                    device=gconf["device"],
                    truncate_context_size=gconf["truncate_context_size"],
                    )

        # 5. indexer  (reuse if stored, else build) ----------------------
        from .index.faiss_index import FaissFlatIndexer as _FFI

        dim = emb_matrix.shape[1]
        indexer = _FFI(dim=dim, use_gpu=False)

        faiss_file = kb_path / "faiss_index.bin"
        if faiss_file.exists():
            indexer.index = faiss.read_index(str(faiss_file))
        else:
            if load_reason == "search":
                raise RuntimeError("Indexing has not been completed.")

        # 6. retriever (optional, but create default if missing)
        from .retrieval import neighbor_retriever

        retriever_file = kb_path / "retriever.json"

        if retriever_file.exists():
            with open(retriever_file, encoding="utf-8") as f:
                rconf = json.load(f)
            retriever_cls = getattr(neighbor_retriever, rconf["class"])
            retriever = retriever_cls(
                    embedder=embedder,
                    indexer=indexer,
                    docs_meta=docs_meta
                    )
        else:
            retriever = None

        # 7. communities & summaries  -----------------------------------
        community_labels: Optional[List[int]] = None
        if docs_meta and "community" in docs_meta[0]:
            community_labels = [m.get("community") for m in docs_meta]

        summaries_file = kb_path / "community_summaries.json"
        community_summaries: Dict[int, str] = {}
        if summaries_file.exists():
            with open(summaries_file, encoding="utf-8") as f:
                community_summaries = json.load(f)

        # 8. misc config  ------------------------------------------------
        with open(kb_path / "legra.json", encoding="utf-8") as f:
            max_tokens: int = json.load(f)["max_tokens"]

        # 9. create instance & inject loaded state -----------------------
        return cls(
                doc_folder=Path(),  # original disk source no longer needed
                chunker=None,  # chunker only used for *new* docs
                max_tokens=max_tokens,
                embedder=embedder,
                indexer=indexer,
                graph_builder=None,
                clusterer=None,
                retriever=retriever,
                generator=generator,
                )._finalize_load(
                docs_meta=docs_meta,
                emb_matrix=emb_matrix,
                graph=graph,  # may be None
                community_labels=community_labels,
                community_summaries=community_summaries,
                )


    def _finalize_load(
        self,
        docs_meta: List[Dict[str, Any]],
        emb_matrix: npt.NDArray,
        graph: Optional[ig.Graph],
        community_labels: Optional[List[int]],
        community_summaries: Dict[int, str],
    ) -> "Legra":
        self.docs_meta            = docs_meta
        self.emb_matrix           = emb_matrix
        self.graph                = graph
        self.community_labels     = community_labels
        self.community_summaries  = community_summaries
        return self


    def query(self, query_text: str, top_k: int = 5, generate: bool = True, **gen_kwargs) -> str:
        """
        Query pipeline:
          1. Retrieve top_k chunks via retriever
          2. Build a context string from retrieved chunks
          3. If a generator is configured, call generator.generate()
             else return raw chunks concatenated.
        """

        if self.retriever is None:
            raise RuntimeError("Retriever is missing.")

        # 1. Retrieve
        results = self.retriever.retrieve(query_text, top_k)
        # 2. Build context
        context_pieces = [r["text"] for r in results]
        context = "\n".join(context_pieces)

        if generate:
            # 3. Generate
            if self.generator is None:
                raise ValueError("Generator not provided.")
            return self.generator.generate(query=query_text, context=context, **gen_kwargs)
        # Fallback: return context with distances/doc info for debugging
        return context