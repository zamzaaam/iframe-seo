class Config:
    MAX_WORKERS = 10
    TIMEOUT = 5
    CHUNK_SIZE = 50
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    TEST_MODE = False
    TEST_SIZE = None

    @classmethod
    def update(cls, **kwargs):
        for key, value in kwargs.items():
            setattr(cls, key, value)
