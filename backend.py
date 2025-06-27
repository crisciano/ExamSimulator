import os
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_aws.embeddings import BedrockEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_aws import ChatBedrockConverse
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage
# from langchain.memory import ConversationBufferMemory
# from langchain.chains import ConversationalRetrievalChain
# from langchain.chains import (
#     create_history_aware_retriever,
#     create_retrieval_chain,
# )
# from langchain.chains.combine_documents import create_stuff_documents_chain
from langgraph.store.memory import InMemoryStore
import uuid

path_files=[
    './docs/resumo.txt',
    './docs/questions.txt',
    './docs/answers.txt'
]

embedding_model_id='amazon.titan-embed-text-v1'
llm_model_id='amazon.nova-micro-v1:0'
separators=["\n\n", "\n", " ", ""]
language='pt-br'

db_cache=None
memory_store = InMemoryStore()
namespace = "chat_history"

# criar uma função para carregar os arquivos, def data_loader
def data_loader(path_files):
    docs = []
    for path in path_files:
        try:
            loader = TextLoader(path, encoding='utf-8')
            doc = loader.load()
            docs.extend(doc)
        except:
            print(f"Error loading {path}")
    return docs

# criar uma função para upload de arquivos, def data_upload
def data_upload(files):
    docs=[]
    for file in files:
        tmp_file = os.path.join("./docs", f'tmp-{file.name}')
        with open(tmp_file, "wb") as f:
            f.write(file.getbuffer())
        doc = data_loader([tmp_file])
        os.remove(tmp_file)  # Remover o arquivo temporário após o carregament
        docs.extend(doc)
    return docs

# criar uma função para quebra do texto, def data_split
def data_split(separators):
    split = RecursiveCharacterTextSplitter(
        separators=separators,
        chunk_size=1000,
        chunk_overlap=100
    )
    return split

# criar uma função que transforma o texto em numeros, def data_embedding
def data_embedding(model_id):
    embedding = BedrockEmbeddings(
        credentials_profile_name='default',
        model_id=model_id
    )
    return embedding

# criar uma função para criar banco de dados vetorial, def data_db
def data_db(embedding, docs):
    split = data_split(separators=separators)
    split_docs = split.split_documents(docs)
    db = FAISS.from_documents(
        documents=split_docs,
        embedding=embedding
    )
    return db

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# criar uma função para iniciar o db, def init_db
def init_db(files):
    global db_cache

    if isinstance(files, list) and all( isinstance(f, str) for f in files ):
        docs = data_loader(path_files=files)
    else:
        docs = data_upload(files=files)

    embedding = data_embedding(model_id=embedding_model_id)

    db = data_db(embedding=embedding, docs=docs)

    db_cache = db

    return db

# criar uma função para iniciar a LLM, def init_llm
def init_llm(model_id):
    llm = ChatBedrockConverse(
        credentials_profile_name='default',
        model_id=model_id,
        temperature=0.1,
        max_tokens=1000,
        verbose=True
    )
    return llm

# criar uma função para salvar memória do chat usando InMemoryStore
def save_chat_memory(question, answer):
    chat_id = str(uuid.uuid4())
    
    # Salvar pergunta e resposta no InMemoryStore
    memory_store.put(
        namespace,
        chat_id,
        {
            "question": question,
            "answer": answer,
            "timestamp": str(uuid.uuid4())
        }
    )

# criar uma função para obter contexto da memória usando InMemoryStore
def get_chat_context():
    try:
        # Recuperar histórico do InMemoryStore
        history = list(memory_store.search(namespace))
        
        if not history:
            return ""
        
        context = "\n\nHistórico da conversa:\n"
        # Pegar as últimas 3 interações
        for i, item in enumerate(history[-3:], 1):
            if 'question' in item.value and 'answer' in item.value:
                context += f"Q{i}: {item.value['question']}\nR{i}: {item.value['answer']}\n\n"
        
        return context
    except:
        return ""

# criar uma função para fazer buscas no db, def retriavel
def retriavel(question, db, llm):
    docs = db.similarity_search(question, k=3)
    context = format_docs(docs)

    # Obter contexto da memória do chat usando MemorySaver
    chat_context = get_chat_context()
    
    prompt = f"""
        Você é uma IA educacional especializada em **criação e avaliação de questões de múltipla escolha**, com suporte a recuperação de informações (RAG - Retrieval-Augmented Generation).

        Sua tarefa é:

        1. Criar questões de múltipla escolha com base em resumos ou questões fornecidas em contexto (não invente dados).
        2. Avaliar respostas fornecidas pelo aluno das questões geradas.

        ---

        ### EXEMPLO DE ENTRADA (para perguntas)

        Entrada esperada:
        - "crie 2 perguntas"
        - "crie 2 questões"
        - "crie 2 perguntas ou quesões a partir do resumo"

        ---
        ### EXEMPLO DE SAÍDA (para perguntas)

        Saida esperada:
        Qual serviço da AWS é responsável por fornecer instâncias de computação escaláveis?
        A. S3  
        B. RDS  
        C. EC2  
        D. IAM  

        ---
        ### EXEMPLO DE ENTRADA (para respostas)

        Entrada esperada:
        - "1:x, 2:x"
        - "a resposta da 1 questão e x"
        - "a resposta da 1 pergunta e x"
        - "a resposta para a 1 pergunta e x e da segunda pergunta e x"

        ---

        ### EXEMPLO DE SAÍDA (para respostas incorretas)

        🔍 Feedback: A resposta está incorreta. O EC2 está relacionado à computação. O controle de identidade e permissões é feito por meio do IAM.  
        📘 Sugestão: Reforce o estudo sobre os serviços básicos da AWS e suas respectivas funções.

        ---
        ### EXEMPLO DE SAÍDA (para respostas corretas)

        🔍 Feedback: Parabéns,  seu esforço será recompensado.

        ---

        Use sempre linguagem clara, objetiva e compatível com o nível de complexidade do material fornecido.

        Responda em: {language}
        Context: 
        {context}
        Chat context: 
        {chat_context}
    """
    
    print(prompt)
    
    messages = [
        SystemMessage(content=prompt), 
        HumanMessage(content=question)
    ]

    response = llm.invoke(messages)
    answer = response.content
    
    # Salvar na memória do chat
    save_chat_memory(question=question, answer=answer)

    return answer




# testes
# docs = data_loader(path_files=path_files)
# print(docs)

# split = data_split(separators=separators)
# docs_split = split.split_documents(docs)
# print(docs_split)

# embedding=data_embedding(model_id=embedding_model_id)
# result = embedding.embed_documents(docs[1].page_content)
# print(result)

# db = data_db(embedding=embedding, docs=docs)
# query= 'criar uma pergunta sobre resumo de texto'
# result = db.similarity_search(query, k=1)

# print(result)

# messages = [
#     SystemMessage(content="You are a helpful assistant."),
#     HumanMessage(content="criar uma pergunta sobre resumo de texto")
# ]

# llm=init_llm(model_id=llm_model_id)
# response= llm.invoke(messages)

# print(response.content)

# question="criar uma pergunta sobre resumo de texto"
# db=init_db(path_files)
# llm=init_llm(model_id=llm_model_id)

# response=retriavel(question=question, db=db, llm=llm)

# print(response)
