import os
from typing import List, Dict, Any
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.llms.openai import OpenAI
from pinecone import Pinecone

class RAGService:
    def __init__(self):
        self.api_key = os.environ.get("PINECONE_API_KEY")
        self.index_name = os.environ.get("PINECONE_INDEX_NAME", "junior-lawyer-demo")
        self.pc = None
        self.index = None
        
        if self.api_key:
            self.pc = Pinecone(api_key=self.api_key)
            self._init_index()
            
    def _init_index(self):
        try:
            pinecone_index = self.pc.Index(self.index_name)
            vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
            # Create the index from the vector store
            self.index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
        except Exception as e:
            print(f"Failed to initialize Pinecone index: {e}")
            
    def query(self, question: str, act_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Query the RAG pipeline with a legal question.
        Optionally filter by a specific act_id.
        Returns the answer and the sources used.
        """
        if not self.index:
            return {
                "answer": "RAG pipeline is not configured. Please check your PINECONE_API_KEY and OPENAI_API_KEY.",
                "sources": []
            }
            
        from app.services.llm_service import llm_load_balancer
        
        # Setup metadata filters if an act_id is provided
        filters = None
        if act_id:
            from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters
            filters = MetadataFilters(
                filters=[MetadataFilter(key="act_id", value=act_id)]
            )
            
        def perform_query(llm_instance):
            # Create a query engine with the provided llm_instance
            query_engine = self.index.as_query_engine(
                llm=llm_instance,
                similarity_top_k=3,
                filters=filters
            )
            return query_engine.query(question)
            
        # Execute query using the load balancer
        response = llm_load_balancer.execute_with_fallback(perform_query)
        
        # Format sources
        sources = []
        for node in response.source_nodes:
            source_info = {
                "text": node.node.text[:200] + "...", # Preview of text
                "metadata": node.node.metadata,
                "score": node.score
            }
            sources.append(source_info)
            
        return {
            "answer": str(response),
            "sources": sources
        }

# Singleton instance
rag_service = RAGService()
