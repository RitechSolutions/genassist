<<<<<<< HEAD
from typing import Dict, List, Any, Optional
import logging
import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
=======
import logging
import os
from typing import Any, Dict, List, Optional

from langchain.schema import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

>>>>>>> development
from .i_data_source_provider import DataSourceProvider

logger = logging.getLogger(__name__)

<<<<<<< HEAD
class VectorDBProvider(DataSourceProvider):
    """LangChain Chroma vector database provider implementation"""
    
    def __init__(self, persist_directory: str = "chroma_db", 
                 embedding_model_name: str = "all-MiniLM-L6-v2",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200):
        self.persist_directory = persist_directory
        self.embedding_model_name = embedding_model_name
=======

class VectorDBProvider(DataSourceProvider):
    """LangChain Chroma vector database provider implementation"""

    def __init__(
        self,
        persist_directory: str = "chroma_db",
        embedding_model_name: str = "all-MiniLM-L6-v2",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        collection_name: str = "knowledge_base",
    ):
        self.persist_directory = persist_directory
        self.embedding_model_name = embedding_model_name
        self.collection_name = collection_name
>>>>>>> development
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embeddings = None
        self.vectorstore = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
        )
<<<<<<< HEAD
    
=======

>>>>>>> development
    def initialize(self) -> bool:
        """Initialize the Chroma client and embeddings"""
        try:
            from langchain_chroma import Chroma

            # Ensure the persist directory exists
            os.makedirs(self.persist_directory, exist_ok=True)
<<<<<<< HEAD
            
=======

>>>>>>> development
            # Initialize embeddings
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.embedding_model_name
            )
<<<<<<< HEAD
            
=======

>>>>>>> development
            # Initialize or load the vector store
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
<<<<<<< HEAD
                collection_name="knowledge_base"
            )
            
=======
                collection_name=self.collection_name,
            )

            # self.vectorstore.reset_collection()

>>>>>>> development
            logger.info("LangChain Chroma initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize LangChain Chroma: {str(e)}")
            return False
<<<<<<< HEAD
    
    def add_document(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> bool:
=======

    async def add_document(
        self, doc_id: str, content: str, metadata: Dict[str, Any]
    ) -> bool:
>>>>>>> development
        """Add a document to the Chroma collection with chunking"""
        try:
            if not self.vectorstore or not self.embeddings:
                if not self.initialize():
                    return False
<<<<<<< HEAD
            
            # First delete if it exists (to handle updates)
            self.delete_document(doc_id)
            
            # Split the document into chunks
            chunks = self.text_splitter.split_text(content)
            
            # Create LangChain Documents for each chunk
            documents = []
            chunk_ids = []
            
=======

            # First delete if it exists (to handle updates)
            await self.delete_document(doc_id)

            # Split the document into chunks
            chunks = self.text_splitter.split_text(content)

            # Create LangChain Documents for each chunk
            documents = []
            chunk_ids = []

>>>>>>> development
            for i, chunk_text in enumerate(chunks):
                # Create a unique ID for each chunk
                chunk_id = f"{doc_id}_chunk_{i}"
                chunk_ids.append(chunk_id)
<<<<<<< HEAD
                
=======

>>>>>>> development
                # Create metadata for the chunk
                chunk_metadata = {
                    **metadata,
                    "id": doc_id,  # Keep the original document ID
                    "chunk_id": chunk_id,
                    "chunk_index": i,
<<<<<<< HEAD
                    "total_chunks": len(chunks)
                }
                
                # Create a document for the chunk
                doc = Document(
                    page_content=chunk_text,
                    metadata=chunk_metadata
                )
                documents.append(doc)
            
            # Add the chunks to the vector store
            if documents:
                self.vectorstore.add_documents(
                    documents,
                    ids=chunk_ids
                )
                
                logger.info(f"Added document {doc_id} with {len(chunks)} chunks to LangChain Chroma")
=======
                    "total_chunks": len(chunks),
                }

                # Create a document for the chunk
                doc = Document(page_content=chunk_text, metadata=chunk_metadata)
                documents.append(doc)

            # Add the chunks to the vector store
            if documents:
                self.vectorstore.add_documents(documents, ids=chunk_ids)

                logger.info(
                    f"Added document {doc_id} with {len(chunks)} chunks to LangChain Chroma"
                )
>>>>>>> development
                return True
            else:
                logger.warning(f"No chunks created for document {doc_id}")
                return False
<<<<<<< HEAD
                
        except Exception as e:
            logger.error(f"Failed to add document to LangChain Chroma: {str(e)}")
            return False
    
    def delete_document(self, doc_id: str) -> bool:
=======

        except Exception as e:
            logger.error(f"Failed to add document to LangChain Chroma: {str(e)}")
            return False

    async def get_document_ids(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """Get all document IDs for a given knowledge base ID"""
        logger.info(f"VectorDB: Getting document IDs for knowledge base ID {kb_id}")
        results = self.vectorstore.get(where={"kb_id": kb_id}, include=["metadatas"])
        if results:
            ids = results.get("ids")
            logger.info(f"Found {ids} document IDs for knowledge base ID {kb_id}")

            # if len(ids) == 0:
            #    res = self.vectorstore.get()
            #    logger.info(f"Found {res} document IDs without kb filter for knowledge base ID {kb_id}")
            #    ids = res.get("ids")
            return ids

        logger.warning(f"No document IDs found for knowledge base ID {kb_id}")
        return None

    async def delete_document(self, doc_id: str) -> bool:
>>>>>>> development
        """Delete all chunks of a document from the Chroma collection"""
        try:
            if not self.vectorstore or not self.embeddings:
                if not self.initialize():
                    return False
<<<<<<< HEAD
            
=======

>>>>>>> development
            # Get all chunks with the document ID in metadata
            # This requires a collection scan, which is not ideal for large collections
            # A better approach would be to maintain a separate index of doc_id to chunk_ids
            try:
                # Use the where filter to find all chunks for this document
<<<<<<< HEAD
                results = self.vectorstore.get(
                    where={"id": doc_id}
                )
                
                if results and results.get('ids'):
                    # Delete all chunks
                    self.vectorstore.delete(results['ids'])
                    logger.info(f"Deleted document {doc_id} with {len(results['ids'])} chunks from LangChain Chroma")
=======
                results = self.vectorstore.get(where={"id": doc_id}, include=["metadatas"])
                if not results or len(results.get("ids")) == 0:
                    results = self.vectorstore.get(ids=[doc_id], include=["metadatas"])

                if results and results.get("ids"):
                    # Delete all chunks
                    self.vectorstore.delete(results["ids"])
                    logger.info(
                        f"Deleted document {doc_id} with {len(results['ids'])} chunks from LangChain Chroma"
                    )
>>>>>>> development
                    return True
                else:
                    logger.info(f"No chunks found for document {doc_id}")
                    return True  # Consider it a success if there's nothing to delete
<<<<<<< HEAD
                    
            except Exception as inner_e:
                logger.warning(f"Error finding chunks for document {doc_id}: {str(inner_e)}")
                # Fall back to a prefix search if the where filter doesn't work
                try:
                    # This is a fallback approach that assumes chunk IDs start with the document ID
                    all_ids = self.vectorstore.get()['ids']
                    chunk_ids = [cid for cid in all_ids if cid.startswith(f"{doc_id}_chunk_")]
                    
                    if chunk_ids:
                        self.vectorstore.delete(chunk_ids)
                        logger.info(f"Deleted document {doc_id} with {len(chunk_ids)} chunks from LangChain Chroma")
                    return True
                except Exception as fallback_e:
                    logger.error(f"Fallback deletion failed for document {doc_id}: {str(fallback_e)}")
                    return False
            
        except Exception as e:
            logger.error(f"Failed to delete document from LangChain Chroma: {str(e)}")
            return False
    
    async def search(self, query: str, limit: int = 5, doc_ids: List[str] = None) -> List[Dict[str, Any]]:
=======

            except Exception as inner_e:
                logger.warning(
                    f"Error finding chunks for document {doc_id}: {str(inner_e)}"
                )
                # Fall back to a prefix search if the where filter doesn't work
                try:
                    # This is a fallback approach that assumes chunk IDs start with the document ID
                    all_ids = self.vectorstore.get()["ids"]
                    chunk_ids = [
                        cid for cid in all_ids if cid.startswith(f"{doc_id}_chunk_")
                    ]

                    if chunk_ids:
                        self.vectorstore.delete(chunk_ids)
                        logger.info(
                            f"Deleted document {doc_id} with {len(chunk_ids)} chunks from LangChain Chroma"
                        )
                    return True
                except Exception as fallback_e:
                    logger.error(
                        f"Fallback deletion failed for document {doc_id}: {str(fallback_e)}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Failed to delete document from LangChain Chroma: {str(e)}")
            return False

    async def search(
        self, query: str, limit: int = 5, kb_ids: List[str] = None
    ) -> List[Dict[str, Any]]:
>>>>>>> development
        """Search the Chroma collection using similarity search and merge chunks from the same document"""
        try:
            if not self.vectorstore or not self.embeddings:
                if not self.initialize():
                    return []
<<<<<<< HEAD
            
            # Increase the limit to get more chunks, which we'll consolidate
            chunk_limit = limit * 3

            # Perform similarity search
            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=chunk_limit
            )
            
            # Group chunks by original document ID
            doc_chunks = {}
            for doc, score in results:
                doc_id = doc.metadata.get('id', '')
                if doc_ids and doc_id not in doc_ids:
                    logger.info(f"Skipping document {doc_id} because it's not in the restricted list {doc_ids}")
                    continue
                if doc_id not in doc_chunks:
                    doc_chunks[doc_id] = {
                        'chunks': [],
                        'best_score': score,
                        'metadata': doc.metadata
                    }
                
                # Add this chunk
                doc_chunks[doc_id]['chunks'].append({
                    'content': doc.page_content,
                    'score': score,
                    'chunk_index': doc.metadata.get('chunk_index', 0)
                })
                
                # Update best score if this chunk has a better score
                if score < doc_chunks[doc_id]['best_score']:
                    doc_chunks[doc_id]['best_score'] = score
            
=======

            # Increase the limit to get more chunks, which we'll consolidate
            chunk_limit = limit * 3

            filter = {"kb_id": kb_ids[0]}
            parts = []
            if len(kb_ids) > 1:
                for kb_id in kb_ids:
                    parts.append({"kb_id": {"eq": kb_id}})

                filter = {"$or": parts}

            # Perform similarity search
            results = self.vectorstore.similarity_search_with_score(
                query=query, k=chunk_limit, filter=filter
            )

            # Group chunks by original document IDÍ
            doc_chunks = {}
            for doc, score in results:
                doc_id = doc.metadata.get("kb_id", "")
                if kb_ids and doc_id not in kb_ids:
                    logger.info(
                        f"Skipping document {doc_id} because it's not in the restricted list {kb_ids}"
                    )
                    continue
                if doc_id not in doc_chunks:
                    doc_chunks[doc_id] = {
                        "chunks": [],
                        "best_score": score,
                        "metadata": doc.metadata,
                    }

                # Add this chunk
                doc_chunks[doc_id]["chunks"].append(
                    {
                        "content": doc.page_content,
                        "score": score,
                        "chunk_index": doc.metadata.get("chunk_index", 0),
                    }
                )

                # Update best score if this chunk has a better score
                if score < doc_chunks[doc_id]["best_score"]:
                    doc_chunks[doc_id]["best_score"] = score

>>>>>>> development
            # Format the results, consolidating chunks from the same document
            formatted_results = []
            for doc_id, data in doc_chunks.items():
                # Sort chunks by their index to maintain document order
<<<<<<< HEAD
                sorted_chunks = sorted(data['chunks'], key=lambda x: x.get('chunk_index', 0))
                
                # Combine chunk content
                combined_content = "\n".join([chunk['content'] for chunk in sorted_chunks])
                
                # Convert distance to similarity score (1 is best, 0 is worst)
                similarity = 1.0 - min(data['best_score'] / 2.0, 1.0)
                
                formatted_results.append({
                    'id': doc_id,
                    'content': combined_content,
                    'metadata': {k: v for k, v in data['metadata'].items() if k not in ['chunk_id', 'chunk_index', 'total_chunks']},
                    'score': similarity,
                    'chunk_count': len(data['chunks'])
                })
            
            # Sort by score and limit results
            formatted_results.sort(key=lambda x: x['score'], reverse=True)
            return formatted_results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to search LangChain Chroma: {str(e)}")
            return [] 
=======
                sorted_chunks = sorted(
                    data["chunks"], key=lambda x: x.get("chunk_index", 0)
                )

                # Combine chunk content
                combined_content = "\n".join(
                    [chunk["content"] for chunk in sorted_chunks]
                )

                # Convert distance to similarity score (1 is best, 0 is worst)
                similarity = 1.0 - min(data["best_score"] / 2.0, 1.0)

                formatted_results.append(
                    {
                        "id": doc_id,
                        "content": combined_content,
                        "metadata": {
                            k: v
                            for k, v in data["metadata"].items()
                            if k not in ["chunk_id", "chunk_index", "total_chunks"]
                        },
                        "score": similarity,
                        "chunk_count": len(data["chunks"]),
                    }
                )

            # Sort by score and limit results
            formatted_results.sort(key=lambda x: x["score"], reverse=True)
            return formatted_results[:limit]

        except Exception as e:
            logger.error(f"Failed to search LangChain Chroma: {str(e)}")
            return []
>>>>>>> development
