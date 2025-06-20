# Iframe SEO Docker Setup

## Déploiement sur serveur Linux (Production)

### 🚀 Déploiement automatique

```bash
# Rendre le script exécutable
chmod +x deploy-linux.sh

# Lancer le déploiement
./deploy-linux.sh
```

### 📋 Déploiement manuel

```bash
# Créer les répertoires nécessaires
mkdir -p data logs
chmod 755 data logs

# Construire et lancer
docker-compose up -d

# Vérifier le statut
docker-compose ps
```

## 💻 Développement local (Windows/Mac/Linux)

### Méthode 1: Docker Compose (Recommandée)

```bash
# Construire et lancer l'application
docker-compose up -d

# Voir les logs
docker-compose logs -f

# Arrêter l'application
docker-compose down
```

### Méthode 2: Docker classique

```bash
# Construire l'image
docker build -t iframe-seo-app .

# Lancer le conteneur
docker run -p 8501:8501 iframe-seo-app

# Ou en arrière-plan
docker run -d -p 8501:8501 --name iframe-seo iframe-seo-app
```

## 🌐 Accès à l'application

Une fois lancée, votre application Streamlit sera disponible à :
**http://localhost:8501**

## 📊 Monitoring et Logs

```bash
# Voir les logs en temps réel
docker-compose logs -f

# Logs spécifiques à l'application
docker-compose logs iframe-seo

# Vérifier l'état de santé
docker-compose ps
curl http://localhost:8501/_stcore/health
```

## Commandes utiles

```bash
# Voir les conteneurs en cours
docker ps

# Arrêter un conteneur
docker stop iframe-seo

# Supprimer un conteneur
docker rm iframe-seo

# Voir les logs d'un conteneur
docker logs iframe-seo

# Reconstruire l'image (après modifications)
docker-compose up --build
```

## Configuration

- Port par défaut : 8501
- Le dossier `data/` est monté en volume pour persister les données
- L'application redémarre automatiquement en cas d'erreur

## Dépannage

Si vous avez des erreurs de permissions :
```bash
# Reconstruire l'image
docker-compose build --no-cache
```

Si le port 8501 est déjà utilisé :
```bash
# Modifier le port dans docker-compose.yml
ports:
  - "8502:8501"  # Utilise le port 8502 à la place
```
