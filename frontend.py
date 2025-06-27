import streamlit as st
import backend as bk
import time

# criar configurar a pagina
st.set_page_config(
    page_title="Exam Simulator", 
    page_icon=":books::parrot:", 
    layout="wide")

st.title('Exam Simulator')

# criar um sidebar para upload de arquivos
with st.sidebar:
    st.subheader("Documentos")
    files = st.file_uploader(
        label="Faça o uploado do seu arquivo txt ou pdf.",
        accept_multiple_files=True,
        type=["txt", "pdf"]
    )

    st.subheader('Informações')
    st.write(f"Modelo de embedding: `{bk.embedding_model_id}`")
    st.write(f"Modelo de llm: `{bk.llm_model_id}`")
    st.write(f"Desenvolvido: `crisciano.botelho`")

if files:
    file_source = files
    st.success(f"Usando {len(files)} arquivo(s) enviados(s)")
else:
    st.warning('Por favor, faça o upload de um arquivo.')
    st.stop()

# iniciar o db na session
if 'db' not in st.session_state:
    with st.spinner('Carregando vector store...'):
        start_time= time.time()

        try:
            st.session_state.db = bk.init_db(file_source)
            end_time = time.time()
            st.success(f"Vector store carregado em {end_time - start_time:.2f} segundos")
        except Exception as e:
            st.error(f"Erro ao carregar o vector store: {e}")
            st.stop()

# iniciar a llm na session
if 'llm' not in st.session_state:
    with st.spinner('Carregando LLM...'):
        start_time= time.time()
        try:
            st.session_state.llm = bk.init_llm(bk.llm_model_id)
            end_time = time.time()
            st.success(f"LLM carregado em {end_time - start_time:.2f} segundos")
        except Exception as e:
            st.error(f"Erro ao carregar o LLM: {e}")
            st.stop()

# iniciar as messages na session
if 'messages' not in st.session_state:
    st.session_state.messages = []

# exibir o historico de mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# exibir o prompt
if prompt := st.chat_input("Faça sua pergunta"):
    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner('Llm processando pergunta...'):
        start_time= time.time()
        try:
            response = bk.retriavel(
                question=prompt, 
                db=st.session_state.db, 
                llm=st.session_state.llm
            )
            end_time = time.time()

            with st.chat_message('assistant'):
                st.markdown(response)
                st.caption(f"Tempo de resposta: {end_time - start_time:.2f} segundos")

            st.session_state.messages.append({"role": "assistant", "content": response})

        except Exception as e:
            st.error(f"Erro ao processar a pergunta: {e}")
            st.session_state.messages.append({
                'role': 'assistent',
                'content': f'Erro ao processar a pergunta: {str(e)}'
            })