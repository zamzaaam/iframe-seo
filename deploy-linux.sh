#!/bin/bash

# Script de déploiement pour serveur Linux
echo "🚀 Déploiement de l'application iframe-seo sur Linux..."

# Vérification des prérequis
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé. Installation requise."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose n'est pas installé. Installation requise."
    exit 1
fi

# Création des répertoires nécessaires
echo "📁 Création des répertoires..."
mkdir -p data logs

# Attribution des permissions appropriées
echo "🔒 Configuration des permissions..."
chmod 755 data logs

# Construction et lancement
echo "🏗️ Construction de l'image Docker..."
docker-compose build

echo "🚀 Lancement de l'application..."
docker-compose up -d

# Vérification du déploiement
echo "⏳ Vérification du déploiement..."
sleep 10

if docker-compose ps | grep -q "Up"; then
    echo "✅ Application déployée avec succès!"
    echo "🌐 Accessible sur: http://localhost:8501"
    echo ""
    echo "📋 Commandes utiles:"
    echo "  - Voir les logs: docker-compose logs -f"
    echo "  - Arrêter: docker-compose down"
    echo "  - Redémarrer: docker-compose restart"
    echo "  - Reconstruire: docker-compose up --build -d"
else
    echo "❌ Échec du déploiement!"
    echo "📋 Vérifier les logs: docker-compose logs"
    exit 1
fi
