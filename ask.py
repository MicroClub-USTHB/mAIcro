import sys
from app.core.vector_store import get_vector_store
from app.core.llm_provider import get_llm
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from app.core.config import settings

def ask_question(question: str):
    llm = get_llm()
    vector_store = get_vector_store()
    
    # Simple RAG chain
    prompt_template = """
    You are mAIcro, an AI assistant for {org_name}.
    Answer the user question based ONLY on the provided context.
    If the context doesn't contain the answer, say "I don't have this information yet."
    
    Context:
    {context}
    
    Question: {question}
    
    Answer:"""
    
    PROMPT = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"],
        partial_variables={"org_name": settings.ORG_NAME}
    )
    
    # Use as retriever
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})
    
    qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": PROMPT}
    )
    
    response = qa.invoke(question)
    return response["result"]

if __name__ == "__main__":
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Ask mAIcro: ")
        
    if not settings.GOOGLE_API_KEY:
        print("Error: GOOGLE_API_KEY not found in .env. Please set it to run.")
        sys.exit(1)
        
    answer = ask_question(question)
    print(f"\nAnswer: {answer}")
