import os
import streamlit as st
from docx import Document
import pandas as pd
import PyPDF2
import openai
import fitz  # PyMuPDF
import easyocr
from pathlib import Path
import tempfile

# Fonction pour charger une base de connaissances depuis différents fichiers
def load_knowledge_base_from_directory(directory_path):
    content = []
    directory = Path(directory_path)
    try:
        for file_path in directory.iterdir():  # Parcours des fichiers dans le dossier
            if file_path.suffix == ".docx":
                content.append(load_text_from_word(file_path))
            elif file_path.suffix == ".pdf":
                content.append(load_text_from_pdf(file_path))
            elif file_path.suffix == ".xlsx":
                content.append(load_text_from_excel(file_path))
        return "\n".join(content)
    except Exception as e:
        st.error(f"Erreur lors du chargement des fichiers dans le dossier : {e}")
        return ""

# Fonction pour rechercher un fichier de devis dans un dossier spécifique
def find_devis_file(directory_path):
    """
    Recherche un fichier contenant "devis" dans son nom dans le dossier spécifié.
    Retourne le chemin du premier fichier trouvé.
    """
    directory = Path(directory_path)
    try:
        for file_path in directory.iterdir():
            if "devis" in file_path.name.lower() and file_path.suffix in [".pdf", ".docx"]:
                return file_path  # Retourne le fichier devis trouvé
    except Exception as e:
        st.error(f"Erreur lors de la recherche du devis : {e}")
    return None  # Aucun devis trouvé

# Fonction pour charger du texte depuis différents types de fichiers
def load_text_from_word(file_path):
    try:
        doc = Document(file_path)
        return "\n".join([paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()])
    except Exception as e:
        return f"Erreur lors de la lecture du fichier Word : {e}"

def load_text_from_pdf(file_path):
    try:
        pdf_reader = PyPDF2.PdfReader(file_path)
        return "\n".join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
    except Exception as e:
        return f"Erreur lors de la lecture du fichier PDF : {e}"

def load_text_from_excel(file_path):
    try:
        df = pd.read_excel(file_path)
        return df.to_string(index=False)
    except Exception as e:
        return f"Erreur lors de la lecture du fichier Excel : {e}"

# Fonction pour interroger OpenAI
def query_openai_with_context(knowledge_base_text, conversation_history, user_input, supplemental_text=""):
    openai.api_key = 'sk-svcacct-7ukQJPT9_hwKV-zquafuAdPoD2PPTTsbbjkTlOEWW5VNto-hwhAfpHaSLxa1WT3BlbkFJdnxqtkbpu5ow6NW5M2eCaF9vc48_fvTKUtORxAER5QeHL6XrRTX7qgTBVVKAA'  # Remplace par ta clé API
    try:
        messages = [
            {"role": "system", "content": """Vous êtes un assistant virtuel de Nostrum Care...
            (Texte d'instructions sur le rôle de l'assistant)"""},
            {"role": "system", "content": f"Base de connaissances :\n{knowledge_base_text}"}
        ]

        messages.extend(conversation_history)

        if supplemental_text:
            user_input = f"{user_input}\n\nInformations supplémentaires issues du PDF :\n{supplemental_text}"

        messages.append({"role": "user", "content": user_input})

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0,
            max_tokens=500
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"Erreur lors de la requête OpenAI : {e}"

# Interface utilisateur Streamlit
st.title("Nostrum AI")

# Spécifiez le chemin du dossier contenant les fichiers
directory_path = Path("./Chatgpt/streamlit/contexte")

# Charger la base de connaissances
knowledge_base = load_knowledge_base_from_directory(directory_path)
if knowledge_base:
    st.success("Base de connaissances chargée avec succès.")
else:
    st.error("Erreur lors du chargement des documents dans le dossier.")

# Initialiser l'historique de la conversation
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

# Affichage des messages sous forme de bulles
for message in st.session_state.conversation_history:
    role_style = "background-color: black; color: white;" if message["role"] == "user" else "background-color: white; color: black;"
    align = "left" if message["role"] == "user" else "right"
    st.markdown(
        f"""
        <div style='text-align: {align}; {role_style} padding: 10px; 
        border-radius: 10px; margin-bottom: 10px; max-width: 60%;'>
            <b>{'Vous' if message["role"] == "user" else 'Assistant'} :</b> {message['content']}
        </div>
        """,
        unsafe_allow_html=True,
    )

# Section de saisie utilisateur
st.write("---")
user_input = st.text_area(
    "Votre message",
    placeholder="Écrivez ici votre message...",
    label_visibility="collapsed",
    height=68,
)

# Charger un fichier PDF en complément
uploaded_pdf = st.file_uploader("Téléchargez un fichier PDF pour complémenter votre question", type=["pdf"])

supplemental_text = ""
if uploaded_pdf:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_pdf.write(uploaded_pdf.getbuffer())
        supplemental_text = load_text_from_pdf(temp_pdf.name)

# Vérification de la demande de devis et envoi du fichier s'il existe
if st.button("Envoyer"):
    if not knowledge_base:
        st.warning("La base de connaissances n'a pas été chargée correctement.")
    elif not user_input.strip():
        st.warning("Veuillez entrer une question avant d'envoyer.")
    else:
        # Vérifier si l'utilisateur demande un devis
        if "devis" in user_input.lower():
            devis_file = find_devis_file("./fichier")  # Recherche dans le dossier "fichier"
            
            if devis_file:
                with open(devis_file, "rb") as file:
                    st.download_button(
                        label="📄 Télécharger votre devis",
                        data=file,
                        file_name=devis_file.name,
                        mime="application/pdf" if devis_file.suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                st.success("Un devis a été trouvé et est disponible en téléchargement !")
            else:
                st.warning("Aucun devis trouvé dans le dossier. Veuillez contacter le service client.")

        else:
            # L'utilisateur ne demande pas de devis, donc on interroge OpenAI
            response = query_openai_with_context(knowledge_base, st.session_state.conversation_history, user_input, supplemental_text)

            if response:
                st.session_state.conversation_history.append({"role": "user", "content": user_input})
                st.session_state.conversation_history.append({"role": "assistant", "content": response})
            st.rerun()
