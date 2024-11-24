import os

class Config:
    # Configuración básica
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave_secreta_para_flask'
    
    # Configuración de MongoDB
    MONGO_URI = "mongodb://localhost:27017/blog_db"

    # Configuración para carga de imágenes
    UPLOAD_FOLDER = os.path.join('static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # Otros parámetros
    DEBUG = True
    TESTING = False
