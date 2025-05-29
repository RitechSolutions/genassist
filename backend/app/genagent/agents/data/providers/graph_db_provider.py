from typing import Dict, List, Any
import logging
from langchain_neo4j import Neo4jGraph
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .i_data_source_provider import DataSourceProvider
logger = logging.getLogger(__name__)

class GraphDBProvider(DataSourceProvider):
    """LangChain Neo4j graph database provider implementation"""
    
    def __init__(self, uri: str = "bolt://localhost:7687", 
                 username: str = "neo4j", 
                 password: str = "password",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200):
        self.uri = uri
        self.username = username
        self.password = password
        self.graph = None
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
        )
    
    def initialize(self) -> bool:
        """Initialize the Neo4j connection using LangChain"""
        try:
            self.graph = Neo4jGraph(
                url=self.uri,
                username=self.username,
                password=self.password
            )
            
            # Test the connection by running a simple query
            self.graph.query("RETURN 1 as test")
            
            # Create constraints and indexes for better performance
            self._create_schema()
            
            logger.info("Neo4j graph initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j graph: {str(e)}")
            return False
    
    def _create_schema(self):
        """Create necessary constraints and indexes"""
        try:
            # Create constraint on Document ID
            self.graph.query("""
                CREATE CONSTRAINT document_id IF NOT EXISTS
                FOR (d:Document) REQUIRE d.id IS UNIQUE
            """)
            
            # Create constraint on Chunk ID
            self.graph.query("""
                CREATE CONSTRAINT chunk_id IF NOT EXISTS
                FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE
            """)
            
            # Create index on Keyword name
            self.graph.query("""
                CREATE INDEX keyword_name IF NOT EXISTS
                FOR (k:Keyword) ON (k.name)
            """)
            
            logger.info("Neo4j schema created successfully")
        except Exception as e:
            logger.error(f"Failed to create Neo4j schema: {str(e)}")
    
    def add_document(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> bool:
        """Add a document to Neo4j as a Document node with chunked content"""
        try:
            if not self.graph:
                if not self.initialize():
                    return False
            
            # First, delete the document if it exists
            self.delete_document(doc_id)
            
            # Create the document node with its metadata
            doc_query = """
            CREATE (d:Document {
                id: $id,
                name: $name,
                description: $description,
                content: $content
            })
            RETURN d
            """
            
            self.graph.query(
                doc_query,
                params={
                    "id": doc_id,
                    "name": metadata.get("name", ""),
                    "description": metadata.get("description", ""),
                    "content": content
                }
            )
            
            # Split the document into chunks
            chunks = self.text_splitter.split_text(content)
            
            # Extract keywords from the entire document
            all_keywords = self._extract_keywords(content)
            
            # Create keyword nodes and relationships to the document
            for keyword in all_keywords:
                keyword_query = """
                MERGE (k:Keyword {name: $keyword})
                WITH k
                MATCH (d:Document {id: $doc_id})
                MERGE (d)-[:HAS_KEYWORD]->(k)
                """
                
                self.graph.query(
                    keyword_query,
                    params={
                        "keyword": keyword,
                        "doc_id": doc_id
                    }
                )
            
            # Create chunk nodes and connect them to the document
            for i, chunk_text in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                chunk_keywords = self._extract_keywords(chunk_text)
                
                # Create the chunk node
                chunk_query = """
                CREATE (c:Chunk {
                    chunk_id: $chunk_id,
                    doc_id: $doc_id,
                    content: $content,
                    chunk_index: $chunk_index,
                    total_chunks: $total_chunks
                })
                WITH c
                MATCH (d:Document {id: $doc_id})
                CREATE (d)-[:HAS_CHUNK]->(c)
                RETURN c
                """
                
                self.graph.query(
                    chunk_query,
                    params={
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "content": chunk_text,
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    }
                )
                
                # Connect chunk to keywords
                for keyword in chunk_keywords:
                    keyword_chunk_query = """
                    MERGE (k:Keyword {name: $keyword})
                    WITH k
                    MATCH (c:Chunk {chunk_id: $chunk_id})
                    MERGE (c)-[:HAS_KEYWORD]->(k)
                    """
                    
                    self.graph.query(
                        keyword_chunk_query,
                        params={
                            "keyword": keyword,
                            "chunk_id": chunk_id
                        }
                    )
            
            logger.info(f"Added document {doc_id} with {len(chunks)} chunks to Neo4j")
            return True
        except Exception as e:
            logger.error(f"Failed to add document to Neo4j: {str(e)}")
            return False
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document and all its chunks from Neo4j"""
        try:
            if not self.graph:
                if not self.initialize():
                    return False
            
            # Delete all chunks and their relationships
            delete_chunks_query = """
            MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
            DETACH DELETE c
            """
            
            self.graph.query(
                delete_chunks_query,
                params={"doc_id": doc_id}
            )
            
            # Delete the document and its relationships
            delete_doc_query = """
            MATCH (d:Document {id: $doc_id})
            DETACH DELETE d
            """
            
            self.graph.query(
                delete_doc_query,
                params={"doc_id": doc_id}
            )
            
            logger.info(f"Deleted document {doc_id} and its chunks from Neo4j")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document from Neo4j: {str(e)}")
            return False
    
    async def search(self, query: str, limit: int = 5, doc_ids: List[str] = None) -> List[Dict[str, Any]]:
        """Search Neo4j for relevant documents based on keyword matching and content similarity"""
        try:
            if not self.graph:
                if not self.initialize():
                    return []
            
            results = []
            
            # Extract keywords from the query
            keywords = self._extract_keywords(query)
            
            if keywords:
                # First, search by keywords at the chunk level
                chunk_keyword_query = """
                MATCH (c:Chunk)-[:HAS_KEYWORD]->(k:Keyword)
                WHERE k.name IN $keywords
                WITH c, count(DISTINCT k) as matches
                ORDER BY matches DESC
                LIMIT $limit
                MATCH (d:Document)-[:HAS_CHUNK]->(c)
                RETURN d.id as id, c.chunk_id as chunk_id, c.content as content, 
                       d.name as name, d.description as description, 
                       c.chunk_index as chunk_index, c.total_chunks as total_chunks,
                       matches
                """
                
                chunk_results = self.graph.query(
                    chunk_keyword_query,
                    params={
                        "keywords": keywords,
                        "limit": limit * 3  # Get more chunks to consolidate
                    }
                )
                
                # Group chunks by document ID
                doc_chunks = {}
                for record in chunk_results:
                    doc_id = record["id"]
                    if doc_ids and doc_id not in doc_ids:
                        continue
                    if doc_id not in doc_chunks:
                        doc_chunks[doc_id] = {
                            'chunks': [],
                            'best_score': 0,
                            'metadata': {
                                'name': record["name"],
                                'description': record["description"]
                            }
                        }
                    
                    # Calculate a score based on keyword matches
                    score = record["matches"] / len(keywords)
                    
                    # Add this chunk
                    doc_chunks[doc_id]['chunks'].append({
                        'content': record["content"],
                        'score': score,
                        'chunk_index': record["chunk_index"],
                        'chunk_id': record["chunk_id"]
                    })
                    
                    # Update best score if this chunk has a better score
                    if score > doc_chunks[doc_id]['best_score']:
                        doc_chunks[doc_id]['best_score'] = score
                
                # Format the results, consolidating chunks from the same document
                for doc_id, data in doc_chunks.items():
                    # Sort chunks by their index to maintain document order
                    sorted_chunks = sorted(data['chunks'], key=lambda x: x.get('chunk_index', 0))
                    
                    # Combine chunk content
                    combined_content = "\n".join([chunk['content'] for chunk in sorted_chunks])
                    
                    results.append({
                        'id': doc_id,
                        'content': combined_content,
                        'metadata': data['metadata'],
                        'score': data['best_score'],
                        'chunk_count': len(data['chunks'])
                    })
            
            # If we don't have enough results, search by content similarity
            if len(results) < limit:
                remaining = limit - len(results)
                existing_ids = {r['id'] for r in results}
                
                # Search for content containing any of the query terms
                content_query = """
                MATCH (c:Chunk)
                WHERE c.content CONTAINS $query
                AND NOT c.doc_id IN $existing_ids
                WITH c, 0.5 as score
                LIMIT $limit
                MATCH (d:Document)-[:HAS_CHUNK]->(c)
                RETURN d.id as id, c.chunk_id as chunk_id, c.content as content, 
                       d.name as name, d.description as description,
                       c.chunk_index as chunk_index, c.total_chunks as total_chunks,
                       score
                """
                
                content_results = self.graph.query(
                    content_query,
                    params={
                        "query": query,
                        "existing_ids": list(existing_ids),
                        "limit": remaining * 3  # Get more chunks to consolidate
                    }
                )
                
                # Group chunks by document ID
                doc_chunks = {}
                for record in content_results:
                    doc_id = record["id"]
                    if doc_id not in doc_chunks:
                        doc_chunks[doc_id] = {
                            'chunks': [],
                            'best_score': 0.5,  # Default score for content matches
                            'metadata': {
                                'name': record["name"],
                                'description': record["description"]
                            }
                        }
                    
                    # Add this chunk
                    doc_chunks[doc_id]['chunks'].append({
                        'content': record["content"],
                        'score': record["score"],
                        'chunk_index': record["chunk_index"],
                        'chunk_id': record["chunk_id"]
                    })
                
                # Format the results, consolidating chunks from the same document
                for doc_id, data in doc_chunks.items():
                    # Sort chunks by their index to maintain document order
                    sorted_chunks = sorted(data['chunks'], key=lambda x: x.get('chunk_index', 0))
                    
                    # Combine chunk content
                    combined_content = "\n".join([chunk['content'] for chunk in sorted_chunks])
                    
                    results.append({
                        'id': doc_id,
                        'content': combined_content,
                        'metadata': data['metadata'],
                        'score': data['best_score'],
                        'chunk_count': len(data['chunks'])
                    })
            
            # Sort by score and limit results
            results.sort(key=lambda x: x['score'], reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to search Neo4j graph: {str(e)}")
            return []
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text
        In a real implementation, use NLP libraries like spaCy or NLTK
        """
        import re
        from collections import Counter
        
        # Remove special characters and split by whitespace
        words = re.sub(r'[^\w\s]', '', text.lower()).split()
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'of', 'and', 'or', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'but', 'if', 'then', 'else', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very'}
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Get most common words
        word_counts = Counter(filtered_words)
        keywords = [word for word, count in word_counts.most_common(15)]
        
        return keywords 