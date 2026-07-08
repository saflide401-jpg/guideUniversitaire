
# /Dockerfile

# --- Étape 1 : Choix de l'image de base ---
# Utilise une image Python 3.11 légère (slim) comme fondation
FROM python:3.11-slim-bookworm 

# --- Étape 2 : Définition du répertoire de travail ---
WORKDIR /project

# --- Étape 3 : Installation des dépendances système ---
# Ces paquets sont nécessaires pour compiler psycopg2 (pilote PostgreSQL)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# --- Étape 4 : Installation des dépendances Python ---
# On copie d'abord UNIQUEMENT requirements.txt pour profiter du cache Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installe le navigateur Chromium de Playwright ainsi que ses dépendances système Linux
# (--with-deps remplace l'installation manuelle de Google Chrome + libs qu'exigeait Selenium)
RUN playwright install --with-deps chromium

# --- Étape 5 : Copie du code source ---
# Copie tout le reste du projet dans le conteneur
COPY . .

# --- Étape 6 : Exposition du port ---
# Informe Docker que l'application écoute sur le port 5000
EXPOSE 5000

# --- Étape 7 : Commande de démarrage ---
CMD ["python", "run.py"]