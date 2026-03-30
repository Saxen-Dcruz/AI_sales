from langchain_community.document_loaders import DirectoryLoader, TextLoader#class used for loading folders and text files
from langchain_core.documents import Document 
from langchain_text_splitters import RecursiveCharacterTextSplitter #class used to to recursive text splitting technique
from langchain.embeddings import HuggingFaceEmbeddings  #class used to call huggingface  embedding model used while converting chunks to embedding  and to embed query
from langchain_postgres import PGVector
import re #regex
import os # os is used for file path handling 


# --- Load .txt documents from directory ---
def load_documents_from_directory(directory_path: str):
    loader = DirectoryLoader(
        path=directory_path,
        glob="**/*.txt",
        loader_cls=lambda p: TextLoader(p, encoding="utf-8"),  
        show_progress=True
    )
    return loader.load()


# --- Split text into product-level documents ---
def split_document_by_products(text: str):
    product_pattern = r'###\*\*Product Name\*\*###'
    products = re.split(f'(?={product_pattern})', text)

    split_docs = []

    for product in products:
        product = product.strip()
        if not product:
            continue

        name_match = re.search(r'###\*\*Product Name\*\*###:?\s*\n\s*(.+)', product)
        product_name = name_match.group(1).strip() if name_match else "Unknown Product"

        split_docs.append(
            Document(
                page_content=product,
                metadata={"product_name": product_name}
            )
        )

    return split_docs


# --- Embedding Model ---
def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="BAAI/bge-m3") # returns a text embedding model using langchains HuggingFaceEmbeddings Wrapper.



# --- Main Pipeline ---
def main():

    connection_string = "postgresql+psycopg://rdl_admin:rdl_admin@localhost:5433/rdl_sales"

    # Step 1: Load documents
    directory_path = os.path.join(
        os.environ["USERPROFILE"], "Desktop", "voice_agent", "RDL_chatbot","knowledge_base"
    )
    documents = load_documents_from_directory(directory_path)

    # Step 2: Preprocess and chunk
    all_chunks = []
    for doc in documents:
        chunks = split_document_by_products(doc.page_content)
        all_chunks.extend(chunks)

    # 🔹 Debugging: show file names
    print(f"\n✅ Total documents loaded: {len(documents)}")
    for i, doc in enumerate(documents, 1):
        print(f"Doc {i}: {doc.metadata['source']}")

    # 🔹 Show only first 50 chunks (if available)
    print(f"\n✅ Total chunks loaded: {len(all_chunks)}")


        # Step 3: Generate embeddings
    embedding_model = get_embedding_model() #loads the embedding model
    db = PGVector.from_documents(
        embedding=embedding_model,
        documents=all_chunks,
        collection_name="rdl_products", # Langchain groups vectors by collection
        connection=connection_string,
        use_jsonb=True # Saves metadata as fast-queryable JSON
    )

    print("✅ Embeddings successfully saved to PostgreSQL database!")

if __name__ == "__main__":
    main()
