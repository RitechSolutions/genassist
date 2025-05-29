from typing import Dict, List, Any, Optional
import logging
import os
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_embed, gpt_4o_mini_complete
from lightrag.kg.shared_storage import initialize_pipeline_status

from .i_data_source_provider import DataSourceProvider
import re
# import nest_asyncio
# nest_asyncio.apply()

class LightRAGProvider(DataSourceProvider):
    """LightRAG provider implementation"""
    
    def __init__(self, working_dir: str = "lightrag_data", 
                 embedding_func: Any = openai_embed,
                 llm_model_func: Any = gpt_4o_mini_complete,
                 search_mode: str = "mix"):
        self.working_dir = working_dir
        self.embedding_func = embedding_func
        self.llm_model_func = llm_model_func
        self.search_mode = search_mode
        self.rag = None
        self._document_map = {}  
        self.logger = logging.getLogger(__name__)# Map to track document IDs to content for deletion
    
    async def initialize(self) -> bool:
        """Initialize the LightRAG client"""
        try:
            # Ensure the working directory exists
            os.makedirs(self.working_dir, exist_ok=True)
            
            # Initialize LightRAG asynchronously
            self.rag = await self._initialize_rag()
            
            self.logger.info("LightRAG initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize LightRAG: {str(e)}")
            return False
    
    async def _initialize_rag(self) -> LightRAG:
        """Async helper to initialize LightRAG"""
        rag = LightRAG(
            working_dir=self.working_dir,
            embedding_func=self.embedding_func,
            llm_model_func=self.llm_model_func,
            chunk_token_size=512,
            chunk_overlap_token_size=50,
            vector_storage="ChromaVectorDBStorage",
            log_level="DEBUG",
            embedding_batch_num=32,
            vector_db_storage_cls_kwargs={
                "local_path": self.working_dir,
                "collection_settings": {
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 128,
                    "hnsw:search_ef": 128,
                    "hnsw:M": 16,
                    "hnsw:batch_size": 100,
                    "hnsw:sync_threshold": 1000,
                },
            },
        )
        
        self.logger.info("=============== entered initialize storages ================")
        await rag.initialize_storages()
        self.logger.info("=============== finished initialize storages ================")
        
        self.logger.info("=============== entered initialize pipeline status ================")
        await initialize_pipeline_status()
        self.logger.info("=============== finished initialize pipeline status ================")
        
        return rag
        
    async def add_document(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> bool:
        """Add a document to LightRAG"""
        if not self.rag:
            if not await self.initialize():
                return False
        
        # Insert the document into LightRAG
        # We'll add metadata as part of the content for now
        # Format: metadata as JSON string + "\n\n" + content
        metadata_str = str(metadata)
        document_with_metadata = f"{metadata_str}\n\n{content}"
        
        # Insert document asynchronously
        try:
            self.logger.info(f"TRYING Adding document {doc_id} to LightRAG")
            await self._insert_document(document_with_metadata)
            return True
        except Exception as e:
            self.logger.error(f"Failed to add document to LightRAG: {str(e)}")
            return False
    
    async def _insert_document(self, content: str):
        """Async helper to insert a document into LightRAG"""
        await self.rag.ainsert(content)
        
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from LightRAG"""
        try:
            if not self.rag:
                if not self.initialize():
                    return False
            
            # Check if we have this document
            if doc_id in self._document_map:
                # Remove from our tracking map
                self._document_map.pop(doc_id)
                
                # Delete from LightRAG
                #asyncio.run(self._delete_document(doc_id))
                
                self.logger.info(f"Deleted document {doc_id} from LightRAG")
            else:
                self.logger.info(f"No document found with ID {doc_id} to delete")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete document from LightRAG: {str(e)}")
            return False
    
    async def _delete_document(self, doc_id: str):
        """Async helper to delete a document from LightRAG"""
        # await self.rag.(doc_id)
        pass
    
    async def search(self, query: str, limit: int = 5, doc_ids: List[str] = None) -> List[Dict[str, Any]]:
        """Search LightRAG using the configured search mode"""
        try:
            if not self.rag:
                if not await self.initialize():
                    return []
            print("inside search {}, {}, {}".format(query, limit, doc_ids))
            # Perform search asynchronously
            # if asyncio.get_event_loop().is_running():
            results = await self._search_documents(query, limit, doc_ids)
            print("after search results {}".format(results))
            # else:
                # results = asyncio.run(self._search_documents(query, limit, doc_ids))
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to insideeeee search LightRAG: {str(e)}")
            return []
    
    async def _search_documents(self, query: str, limit: int, doc_ids: List[str] = None) -> List[Dict[str, Any]]:
        """Async helper to search documents in LightRAG"""
        # Create query parameters
        param = QueryParam(mode=self.search_mode, top_k=limit, response_type="Single Paragraph")
        
        # If doc_ids is provided, we need to filter results after querying
        # since LightRAG doesn't support filtering by doc_ids directly
        # raw_results = await self.rag.query(query, param=param, return_source=True)
        try:
            # Use await instead of loop.run_until_complete
            self.logger.info(f"=============== entered search docuemnts ================")
            print("inside search documents function {}, {}, {}".format(query, limit, doc_ids))
            print("param {}".format(param))
            raw_results = await self.rag.aquery(query, param=param)
            print("raw_results\n{}".format(raw_results))
            self.logger.info(f"Raw results from _search document: {raw_results}")
        except Exception as e:
            self.logger.info(f"=============== entered search docuemnts except ================")
            self.logger.error(f"Failed to search LightRAG: {e}")
            raise e
        
        
        # Format the results to match the expected output format
        formatted_results = []
        
        # Process the raw results from LightRAG
        # The exact structure depends on LightRAG's output format
        self.logger.info("============= raw_results ================")
        self.logger.info(raw_results)
        
        print("len of raw_results {}".format(len(raw_results)))
        print("first raw_results {}".format(raw_results[0]))
        print("second raw_results {}".format(raw_results[1]))
        print("third raw_results {}".format(raw_results[2]))
        print("fourth raw_results {}".format(raw_results[3]))
        
            
        result_id = "unknown_id"
        titles = re.findall(r'^###\s+(.*)', raw_results, re.MULTILINE)
        content = raw_results.split(titles[0])[1].split("###")[0].strip()
        print("content {}".format(content))
        score = 0.0
        metadata = {}
        formatted_results.append({
            'id': result_id,
            'content': content,
            'metadata': metadata,
            'score': score,
        })
        
        formatted_results.append({
                'id': "1",
                'content': raw_results,
                'metadata': {},
                'score': 1,
            })
        # Sort by score and limit results
        formatted_results.sort(key=lambda x: x['score'], reverse=True)
        return formatted_results[:limit] 