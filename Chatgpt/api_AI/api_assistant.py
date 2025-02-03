from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from docx import Document
import pandas as pd
import PyPDF2
import openai
import fitz  # PyMuPDF
import easyocr
from pathlib import Path
import tempfile
import tiktoken
import uvicorn

app = FastAPI()

# Variable globale pour la base de connaissances
knowledge_base = ""

# Fonction pour charger une base de connaissances depuis différents fichiers
def load_knowledge_base_from_directory(directory_path):
    content = []
    directory = Path(directory_path)
    for file_path in directory.iterdir():
        if file_path.suffix == ".docx":
            content.append(load_text_from_word(file_path))
        elif file_path.suffix == ".pdf":
            content.append(load_text_from_pdf(file_path))
        elif file_path.suffix == ".xlsx":
            content.append(load_text_from_excel(file_path))
    return "\n".join(content)

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

# Fonction pour extraire du texte d'un PDF avec PyMuPDF et EasyOCR
def extract_text_from_pdf_with_fitz(pdf_file):
    try:
        with tempfile.TemporaryDirectory() as image_output_dir:
            pdf = fitz.open(pdf_file)
            image_files = []

            for page_num in range(pdf.page_count):
                page = pdf[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image_path = Path(image_output_dir) / f"page_{page_num + 1}.png"
                pix.save(image_path)
                image_files.append(image_path)

            pdf.close()

            reader = easyocr.Reader(["fr"])
            text_output = []
            for image_path in image_files:
                text = reader.readtext(str(image_path), detail=0, paragraph=True)
                text_output.append(" ".join(text))

            return "\n".join(text_output)
    except Exception as e:
        return f"Erreur lors de l'extraction du texte : {e}"

# Fonction pour compter les tokens
def count_tokens(messages, model="gpt-4o-mini"):
    encoding = tiktoken.encoding_for_model(model)
    total_tokens = 0
    for message in messages:
        total_tokens += len(encoding.encode(message["content"]))
    return total_tokens

# Fonction pour interroger OpenAI avec une base de connaissances et du texte complémentaire
def query_openai_with_context(knowledge_base_text, conversation_history, user_input, supplemental_text=""):
    openai.api_key = 'clé_api'
    try:
        messages = [
            {"role": "system", "content": """Vous êtes un assistant virtuel conçu pour une mutuelle, 
             utilisant une base de connaissances issue de plusieurs documents. Votre rôle principal est de 
             répondre de manière claire et utile aux questions des utilisateurs, en vous basant sur les 
             informations disponibles. Si vous ne trouvez pas la réponse adéquate, formulez une réponse 
             polie et orientez l'utilisateur vers des solutions ou des ressources pertinentes.Lorsque cela 
             est pertinent dans la conversation, détectez les besoins de l'utilisateur pour lui proposer, 
             le cas échéant, une offre d'adhésion à la mutuelle qui correspond le mieux à sa situation. 
             Ne proposez pas systématiquement l'adhésion dès le début, mais privilégiez un moment opportun 
             dans l'échange pour poser la question et adapter votre suggestion en fonction des besoins 
             exprimés. Pour les réponses tu devras etre synthétique pour pas que la personne n'est trop 
             de mot a lire mais tout en gardant les informations pertinantes a la question posée."""},
            {"role": "system", "content": f"Base de connaissances :\n{knowledge_base_text}"}
        ]
        messages.extend(conversation_history)

        if supplemental_text:
            user_input = f"{user_input}\n\nInformations supplémentaires issues du PDF :\n{supplemental_text}"

        messages.append({"role": "user", "content": user_input})

        token_count = count_tokens(messages, model="gpt-4o-mini")
        print(f"Nombre total de tokens envoyés : {token_count}")

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0,
            max_tokens=500
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"Erreur lors de la requête OpenAI : {e}"

# Charger la base de connaissances au démarrage de l'application
@app.on_event("startup")
def load_base_on_startup():
    global knowledge_base
    directory_path = Path("./contexte")
    try:
        knowledge_base = load_knowledge_base_from_directory(directory_path)
        print("Base de connaissances chargée avec succès.")
    except Exception as e:
        print(f"Erreur lors du chargement de la base de connaissances : {e}")

# Endpoint pour poser une question
@app.post("/query")
def query_knowledge_base(
    id: str = Form(...),
    message: str = Form(...),
    supplemental_pdf: UploadFile = File(None),
):
    global knowledge_base
    try:
        if not knowledge_base:
            return JSONResponse(content={"error": "La base de connaissances n'a pas été chargée."}, status_code=500)

        # Charger un PDF complémentaire si fourni
        supplemental_text = ""
        if supplemental_pdf:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                temp_pdf.write(supplemental_pdf.file.read())
                supplemental_text = extract_text_from_pdf_with_fitz(temp_pdf.name)

        # Historique fictif pour l'instant (à améliorer pour une vraie gestion des sessions)
        conversation_history = []

        # Interroger OpenAI
        response = query_openai_with_context(knowledge_base, conversation_history, message, supplemental_text)
        return {"id": id, "response": response}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("api_assistant:app", host="0.0.0.0", port=8000, reload=True)
