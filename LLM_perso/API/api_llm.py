from fastapi import FastAPI, Form
from pydantic import BaseModel
from typing import Union
import json
import random
import uvicorn
from sentence_transformers import SentenceTransformer, util

# Charger les intents depuis un fichier JSON
with open("./base_connaissance.json", "r", encoding="utf-8") as file:
    data = json.load(file)

# Charger un modèle de similarité (SentenceTransformer)
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# Préparer les embeddings pour les patterns
patterns = []
intents_map = []

for intent in data["intents"]:
    for pattern in intent["patterns"]:
        patterns.append(pattern)
        intents_map.append(intent)

# Créer les embeddings pour les patterns
pattern_embeddings = model.encode(patterns, convert_to_tensor=True)

# Initialiser l'application FastAPI
app = FastAPI()

# Définition du modèle de requête
class UserRequest(BaseModel):
    id: Union[str, int]
    message: str

# Fonction pour identifier l'intent le plus proche
def get_best_intent(user_input: str):
    if not patterns:
        return None
    user_embedding = model.encode(user_input, convert_to_tensor=True)
    similarity_scores = util.pytorch_cos_sim(user_embedding, pattern_embeddings)
    best_match_idx = similarity_scores.argmax().item()
    best_match_score = similarity_scores[0][best_match_idx].item()
    
    threshold = 0.9  # Seuil de similarité minimal
    if best_match_score < threshold:
        return None
    return intents_map[best_match_idx]

# Fonction principale pour générer une réponse
def generate_response(user_input: str):
    intent = get_best_intent(user_input)
    if intent is None:
        with open("./stock_quest.txt", "a", encoding="utf-8") as file:
            file.write(user_input + "\n")
        return "Je ne suis pas certain de la réponse, mais je suis là si vous avez d'autres questions !"
    
    return random.choice(intent["responses"])

# Route FastAPI pour gérer les requêtes via form-data
@app.post("/chat")
def chat(id: Union[str, int] = Form(...), message: str = Form(...)):
    response = generate_response(message)
    return {"id": id, "response": response}

# Lancement du serveur avec uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
