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
            # elif file_path.suffix == ".html":
            #     content.append(load_text_from_html(file_path))
        return "\n".join(content)
    except Exception as e:
        st.error(f"Erreur lors du chargement des fichiers dans le dossier : {e}")
        return ""

# Charger le contenu d'un fichier Word
def load_text_from_word(file_path):
    try:
        doc = Document(file_path)
        return "\n".join([paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()])
    except Exception as e:
        return f"Erreur lors de la lecture du fichier Word : {e}"

# Charger le contenu d'un fichier PDF
def load_text_from_pdf(file_path):
    try:
        pdf_reader = PyPDF2.PdfReader(file_path)
        return "\n".join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
    except Exception as e:
        return f"Erreur lors de la lecture du fichier PDF : {e}"

# Charger le contenu d'un fichier Excel
def load_text_from_excel(file_path):
    try:
        df = pd.read_excel(file_path)
        return df.to_string(index=False)
    except Exception as e:
        return f"Erreur lors de la lecture du fichier Excel : {e}"

# Charger le contenu d'un fichier HTML
def load_text_from_html(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Erreur lors de la lecture du fichier HTML : {e}"

# Fonction pour convertir un PDF en texte avec PyMuPDF et EasyOCR
def extract_text_from_pdf_with_fitz(pdf_file):
    try:
        with tempfile.TemporaryDirectory() as image_output_dir:  # Crée un dossier temporaire
            pdf = fitz.open(pdf_file)
            image_files = []

            for page_num in range(pdf.page_count):
                page = pdf[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image_path = Path(image_output_dir) / f"page_{page_num + 1}.png"
                pix.save(image_path)
                image_files.append(image_path)

            pdf.close()

            # Utiliser EasyOCR pour extraire le texte
            reader = easyocr.Reader(["fr"])
            text_output = []
            for image_path in image_files:
                text = reader.readtext(str(image_path), detail=0, paragraph=True)
                text_output.append(" ".join(text))

            return "\n".join(text_output)
    except Exception as e:
        return f"Erreur lors de l'extraction du texte : {e}"

# Fonction pour interroger OpenAI avec une base de connaissances, l'historique, et du texte complémentaire
def query_openai_with_context(knowledge_base_text, conversation_history, user_input, supplemental_text=""):
    openai.api_key = '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'
    try:
        messages = [
            {"role": "system", "content": "Vous êtes un assistant virtuel pour une mutuelle utilisant une base de connaissances issue de plusieurs documents. Si vous ne trouvez pas la réponse adéquate, formulez poliment une réponse. Vous devez parler comme si vous parliez à une personne humaine. Egalement l'idéale serait de demander à la personne si elle n'est pas encore adhérente chez nous et si non alors lui proposer un contrat en fonction de ses besoins. Pour ce faire, il faudra que vous détectiez les besoins de la personne et que vous lui proposiez la formule qui lui convient le mieux."},
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
directory_path = Path("./contexte")

# Charger la base de connaissances depuis le dossier
knowledge_base = load_knowledge_base_from_directory(directory_path)
if knowledge_base:
    st.success("Base de connaissances chargée avec succès.")
else:
    st.error("Erreur lors du chargement des documents dans le dossier.")

# Initialiser l'historique de la conversation dans la session Streamlit
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

# Affichage des messages sous forme de bulles
for message in st.session_state.conversation_history:
    if message["role"] == "user":
        st.markdown(
            f"""
            <div style='text-align: left; background-color: black; color: white; padding: 10px; 
            border-radius: 10px; margin-bottom: 10px; max-width: 60%;'>
                <b>Vous :</b> {message['content']}
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif message["role"] == "assistant":
        st.markdown(
            f"""
            <div style='text-align: left; background-color: white; color: black; padding: 10px; 
            border-radius: 10px; margin-bottom: 10px; max-width: 60%; margin-left: auto;'>
                <b>Assistant :</b> {message['content']}
            </div>
            """,
            unsafe_allow_html=True,
        )

# Section pour poser une question (champ en bas de la page)
st.write("---")
user_input = st.text_area(
    "Votre message",
    placeholder="Écrivez ici votre message...",
    label_visibility="collapsed",
    height=60,
)

# Charger un fichier PDF pour un complément contextuel
uploaded_pdf = st.file_uploader("Téléchargez un fichier PDF pour complémenter votre question", type=["pdf"])

supplemental_text = ""
if uploaded_pdf:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_pdf.write(uploaded_pdf.getbuffer())
        supplemental_text = extract_text_from_pdf_with_fitz(temp_pdf.name)

if st.button("Envoyer"):
    if not knowledge_base:
        st.warning("La base de connaissances n'a pas été chargée correctement.")
    elif not user_input.strip():
        st.warning("Veuillez entrer une question avant d'envoyer.")
    else:
        response = query_openai_with_context(knowledge_base, st.session_state.conversation_history, user_input, supplemental_text)
        # response = query_openai_with_context(knowledge_base, st.session_state.conversation_history, user_input)

        if response:
            st.session_state.conversation_history.append({"role": "user", "content": user_input})
            st.session_state.conversation_history.append({"role": "assistant", "content": response})
        st.experimental_rerun()
