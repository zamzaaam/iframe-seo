class Config:
    MAX_WORKERS = 10
    TIMEOUT = 5
    CHUNK_SIZE = 50
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    TEST_MODE = False
    TEST_SIZE = None
    
    # Paramètres de sécurité
    MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10 MB
    FALLBACK_SEARCH = False               # Désactivé - Respecte strictement le chemin DOM spécifié
    ALLOWED_DOMAINS = []                  # Domaines autorisés, vide = tous
    BLOCKED_DOMAINS = [                   # Domaines explicitement bloqués
        'localhost', '127.0.0.1', '0.0.0.0',
        '192.168.', '10.', '172.16.', '169.254.'
    ]
    LOG_LEVEL = 'INFO'                    # Niveau de logging
    SECURE_HEADERS = True                 # Utiliser des en-têtes HTTP sécurisés
    SANITIZE_OUTPUT = True                # Sanitiser les sorties HTML
    
    # Paramètres de rate limiting
    RATE_LIMIT = True                     # Activer la limitation de requêtes
    RATE_LIMIT_SECONDS = 1                # Intervalle minimal entre requêtes (secondes)
    MAX_REQUESTS_PER_DOMAIN = 10          # Nombre maximal de requêtes par domaine
    
    # Paramètres de timeout spécifiques
    CONNECT_TIMEOUT = 3                   # Timeout de connexion
    READ_TIMEOUT = 5                      # Timeout de lecture
    
    @classmethod
    def update(cls, **kwargs):
        for key, value in kwargs.items():
            setattr(cls, key, value)
            
    @classmethod
    def get_timeouts(cls):
        """Retourne les timeouts sous forme de tuple pour requests."""
        return (cls.CONNECT_TIMEOUT, cls.READ_TIMEOUT)