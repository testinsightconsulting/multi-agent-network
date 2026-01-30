#!/usr/bin/env python3
"""
Script to manually ingest the knowledge base into the RAG vector database.
Run this script whenever you add new documents to the knowledge_base directory.
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.knowledge.rag_engine import RAGEngine

def main():
    print("Initializing RAG Engine...")
    try:
        rag = RAGEngine(knowledge_base_root=str(project_root / "knowledge_base"))
    except Exception as e:
        print(f"Error initializing RAG Engine: {e}")
        return

    print("Starting ingestion process...")
    print("This may take a while for large document sets.")
    
    try:
        stats = rag.ingest_all()
        
        print("\nIngestion Complete!")
        print("-" * 30)
        total_docs = 0
        for device, count in stats.items():
            print(f"{device}: {count} documents")
            total_docs += count
        print("-" * 30)
        print(f"Total Documents Processed: {total_docs}")
        
    except KeyboardInterrupt:
        print("\nIngestion cancelled by user.")
    except Exception as e:
        print(f"\nError during ingestion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
