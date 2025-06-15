import json
from pathlib import Path
from typing import List, Dict
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_relevancy,
    context_recall,
    context_precision,
)
from datasets import Dataset
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import os

def load_test_cases(file_path: str) -> List[Dict]:
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data['test_cases']

def get_chroma_client():
    # Initialize ChromaDB client
    client = chromadb.Client(Settings(
        persist_directory="chroma_db",
        is_persistent=True
    ))
    return client

def retrieve_contexts(client, questions: List[str], collection_name: str = "sales_data") -> List[str]:
    # Get the collection
    collection = client.get_collection(name=collection_name)
    
    # Retrieve contexts for each question
    contexts = []
    for question in questions:
        results = collection.query(
            query_texts=[question],
            n_results=3  # Get top 3 most relevant contexts
        )
        # Combine retrieved contexts
        context = " ".join(results['documents'][0])
        contexts.append(context)
    
    return contexts

def prepare_dataset(test_cases: List[Dict], retrieved_contexts: List[str]) -> Dataset:
    questions = [tc['question'] for tc in test_cases]
    ground_truths = [tc['ground_truth'] for tc in test_cases]
    customer_contexts = [tc['customer_context'] for tc in test_cases]
    
    # Convert customer contexts to string format
    customer_contexts = [f"Company Size: {ctx['company_size']}, Industry: {ctx['industry']}, Use Case: {ctx['use_case']}" 
                        for ctx in customer_contexts]
    
    # Combine customer context with retrieved context
    contexts = [f"{cust_ctx}\nRetrieved Context: {ret_ctx}" 
               for cust_ctx, ret_ctx in zip(customer_contexts, retrieved_contexts)]
    
    return Dataset.from_dict({
        'question': questions,
        'ground_truth': ground_truths,
        'context': contexts
    })

def main():
    # Load test cases
    test_cases = load_test_cases('Data/test_cases.json')
    
    # Initialize ChromaDB client
    client = get_chroma_client()
    
    # Get questions from test cases
    questions = [tc['question'] for tc in test_cases]
    
    # Retrieve contexts from ChromaDB
    retrieved_contexts = retrieve_contexts(client, questions)
    
    # Prepare dataset with both customer context and retrieved context
    dataset = prepare_dataset(test_cases, retrieved_contexts)
    
    # Define metrics
    metrics = [
        faithfulness,
        answer_relevancy,
        context_relevancy,
        context_recall,
        context_precision,
    ]
    
    # Run evaluation
    result = evaluate(
        dataset,
        metrics=metrics,
    )
    
    # Print results
    print("\nEvaluation Results:")
    print("==================")
    for metric_name, score in result.items():
        print(f"{metric_name}: {score:.4f}")
    
    # Print example retrievals
    print("\nExample Retrievals:")
    print("==================")
    for i, (question, context) in enumerate(zip(questions[:3], retrieved_contexts[:3])):
        print(f"\nQuestion {i+1}: {question}")
        print(f"Retrieved Context: {context[:200]}...")  # Print first 200 chars

if __name__ == "__main__":
    main() 