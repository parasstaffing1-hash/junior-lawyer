import os
import sys
import time
from dotenv import load_dotenv

# Setup path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.bare_acts_service import bare_acts_service, BARE_ACTS_DB
from app.services.tts_service import tts_service
from app.services.rag_service import rag_service

load_dotenv()

def ingest_acts():
    print("Starting KanoonGPT Bare Acts Ingestion Pipeline...")
    
    if not rag_service.pc:
        print("Error: Pinecone API Key not set. Cannot ingest.")
        return
        
    print(f"Connected to Pinecone Index: {rag_service.index_name}")
    
    # In a real scenario, we would connect to a DB, but we'll use our mock BARE_ACTS_DB
    acts = BARE_ACTS_DB
    
    for act in acts:
        print(f"\nProcessing Act: {act['title']}")
        
        for section in act['sections']:
            print(f"  -> Processing Section {section['section_number']}: {section['title']}")
            
            # Step 1: AI Simplification (Mocked in the DB already, but we'd call OpenAI here)
            time.sleep(0.5) # Simulate API call for simplification
            
            # Step 2: KanoonFM Audio Generation
            # This generates the mp3 and saves the URL back to our database
            audio_url = tts_service.generate_audio(
                text=section['simplified_explanation'],
                output_filename=f"{act['id']}_{section['section_number']}.mp3"
            )
            print(f"     [Audio Generated]: {audio_url}")
            
            # Step 3: Vector Embedding & Pinecone Indexing
            # We index the original text and the simplified text together for better semantic search
            document_text = f"Act: {act['title']}\nSection {section['section_number']}: {section['title']}\n\nOriginal Text: {section['text']}\n\nSimplified Explanation: {section['simplified_explanation']}"
            
            metadata = {
                "type": "bare_act_section",
                "act_id": act["id"],
                "act_title": act["title"],
                "section_number": section["section_number"],
                "section_title": section["title"],
                "audio_url": audio_url
            }
            
            # Convert to LlamaIndex Document
            from llama_index.core import Document
            doc = Document(text=document_text, metadata=metadata)
            
            # Insert into Pinecone
            try:
                rag_service.index.insert(doc)
                print(f"     [Indexed in Pinecone]")
            except Exception as e:
                print(f"     [Error Indexing]: {e}")
                
    print("\nIngestion Complete!")

if __name__ == "__main__":
    ingest_acts()
