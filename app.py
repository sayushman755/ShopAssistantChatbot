import os
import time
import streamlit as st
from groq import Groq

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
from langchain_pinecone import PineconeVectorStore
from langchain_core.embeddings import Embeddings

load_dotenv()

# -----------------------------
# Pinecone Configuration
# -----------------------------
api_key = os.getenv("PINECONE_API_KEY")

pc = Pinecone(api_key=api_key)

spec = ServerlessSpec(
    cloud="aws",
    region="us-east-1"
)

index_name = "shop-product-catalog"

# Connect to existing index
myindex = pc.Index(index_name)

time.sleep(1)

# -----------------------------
# Custom Embedding Wrapper
# -----------------------------
class SentenceTransformerEmbeddings(Embeddings):

    def __init__(self, model_name):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts):
        return self.model.encode(texts).tolist()

    def embed_query(self, text):
        return self.model.encode(text).tolist()

# Initialize embedding model
embedding = SentenceTransformerEmbeddings(
    'all-MiniLM-L6-v2'
)

# -----------------------------
# Pinecone Vector Store
# -----------------------------
vectorstore = PineconeVectorStore(
    index=myindex,
    embedding=embedding,
    text_key='Description'
)

# -----------------------------
# Groq Configuration
# -----------------------------
client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

# -----------------------------
# Streamlit Session
# -----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# -----------------------------
# System Prompt
# -----------------------------
system_message = (
    "You are a helpful shopping assistant. "
    "Answer only shopping and product-related questions. "
    "Use the provided product context to answer naturally. "
    "If exact information is unavailable, answer based on related product features. "
    "If the question is unrelated to shopping, respond with: "
    "'I can only provide answers related to the shop.'"
)

# -----------------------------
# Generate AI Response
# -----------------------------
def gen_answer(system_message, chat_history, prompt):

    chat_history.append(f"User: {prompt}")

    full_prompt = (
        f"{system_message}\n\n"
        + "\n".join(chat_history)
        + "\nAssistant:"
    )

    response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[
        {
            "role": "system",
            "content": system_message
        },
        {
            "role": "user",
            "content": full_prompt
        }
    ],
    temperature=0.7
)

    answer = response.choices[0].message.content

    chat_history.append(f"Assistant: {answer}")

    return answer

# -----------------------------
# Retrieve Relevant Product
# -----------------------------
def get_relevant_chunk(query, vectorstore):

    results = vectorstore.similarity_search(query, k=5)

    if results:

        metadata = results[0].metadata

        context = (
            f"Product Name: {metadata.get('ProductName', 'Not Available')}\n"
            f"Brand: {metadata.get('ProductBrand', 'Not Available')}\n"
            f"Price: {metadata.get('Price', 'Not Available')}\n"
            f"Color: {metadata.get('PrimaryColor', 'Not Available')}\n"
            f"Description: {results[0].page_content}"
        )

        return context

    return "No relevant product found."

# -----------------------------
# Final Prompt
# -----------------------------
def make_prompt(query, context):

    return (
        f"Customer Query: {query}\n\n"
        f"Product Context:\n{context}\n\n"
        f"""
Answer naturally as a shopping assistant.

If relevant products are found:
- Recommend them properly
- Mention product name, brand, and color
- Keep answer concise

If no relevant products are found:
Say politely that no matching products are available.
"""
    )

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(
    page_title="Shop Catalog Chatbot",
    page_icon="🛍",
    layout="centered"
)

st.title("🛍 Shop Catalog Chatbot")

st.write("Ask anything about products from the catalog.")

query = st.text_input("Enter your product query")

if st.button("Get Answer"):

    if query:

        with st.spinner("Searching products and generating answer..."):

            relevant_text = get_relevant_chunk(
                query,
                vectorstore
            )

            prompt = make_prompt(
                query,
                relevant_text
            )

            answer = gen_answer(
                system_message,
                st.session_state.chat_history,
                prompt
            )

        st.write("## Answer")
        st.write(answer)

        with st.expander("Relevant Product Context"):
            st.text(relevant_text)

        with st.expander("Chat History"):

            for chat in st.session_state.chat_history:
                st.write(chat)

    else:
        st.warning("Please enter a query.")