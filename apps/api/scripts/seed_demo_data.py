import os
import sys
from pathlib import Path

# Add the app directory to the python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from llama_index.core import Document, VectorStoreIndex, StorageContext
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Pinecone

# Load environment variables
load_dotenv()

# We need these API keys in the environment:
# OPENAI_API_KEY
# PINECONE_API_KEY
# PINECONE_ENVIRONMENT
# PINECONE_INDEX_NAME

def get_demo_documents():
    """Returns a list of dummy legal documents for the MVP."""
    
    doc1 = Document(
        text=(
            "In the landmark case of Kesavananda Bharati v. State of Kerala (1973), "
            "the Supreme Court of India outlined the Basic Structure Doctrine of the Constitution. "
            "The court ruled that while the Parliament has wide powers to amend the Constitution "
            "under Article 368, it cannot alter or destroy its 'basic structure'. "
            "This implies that fundamental features like democracy, secularism, federalism, "
            "and judicial review are immune from constitutional amendments."
        ),
        metadata={"source": "Kesavananda Bharati v. State of Kerala", "year": 1973, "topic": "Constitutional Law"}
    )
    
    doc2 = Document(
        text=(
            "Justice K.S. Puttaswamy (Retd.) v. Union of India (2017) is a landmark judgment "
            "of the Supreme Court of India, which holds that the right to privacy is protected "
            "as a fundamental constitutional right under Articles 14, 19 and 21 of the Constitution of India. "
            "The 9-judge bench unanimously ruled that privacy is an intrinsic part of the right to life "
            "and personal liberty under Article 21."
        ),
        metadata={"source": "Puttaswamy v. Union of India", "year": 2017, "topic": "Right to Privacy"}
    )
    
    doc3 = Document(
        text=(
            "The Indian Contract Act, 1872, Section 73 deals with compensation for loss or damage "
            "caused by breach of contract. When a contract has been broken, the party who suffers "
            "by such breach is entitled to receive, from the party who has broken the contract, "
            "compensation for any loss or damage caused to him thereby, which naturally arose "
            "in the usual course of things from such breach, or which the parties knew, when they "
            "made the contract, to be likely to result from the breach of it."
        ),
        metadata={"source": "Indian Contract Act, 1872", "topic": "Breach of Contract"}
    )

    return [doc1, doc2, doc3]

def main():
    print("Seeding Demo Knowledge Base into Pinecone...")
    
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "junior-lawyer-demo")
    
    if not api_key:
        print("ERROR: PINECONE_API_KEY not found in environment.")
        print("Please set your OpenAI and Pinecone API keys in a .env file to run the seed script.")
        return

    # Initialize Pinecone
    pc = Pinecone(api_key=api_key)
    
    # Check if index exists, create if not (Requires Pinecone Free Tier)
    if index_name not in pc.list_indexes().names():
        from pinecone import ServerlessSpec
        print(f"Creating Pinecone index '{index_name}'...")
        pc.create_index(
            name=index_name,
            dimension=1536, # OpenAI text-embedding-3-small dimension
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
    
    pinecone_index = pc.Index(index_name)
    vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    documents = get_demo_documents()
    
    print("Embedding documents and uploading to Pinecone...")
    # This automatically uses OpenAI text-embedding-ada-002 or text-embedding-3-small based on LlamaIndex defaults
    index = VectorStoreIndex.from_documents(
        documents, storage_context=storage_context
    )
    
    print("Successfully seeded demo data into Pinecone!")

if __name__ == "__main__":
    main()
