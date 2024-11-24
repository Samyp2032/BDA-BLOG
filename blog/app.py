from flask import Flask, render_template, request, redirect, url_for
from flask_pymongo import PyMongo
from werkzeug.utils import secure_filename
from datetime import datetime
from textblob import TextBlob
import redis
import os
import json
import time  # Importa el módulo time


import csv

def cargar_posts_desde_csv(filepath):
    """Carga posts desde un archivo CSV y los inserta en MongoDB."""
    with open(filepath, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        # Validar columnas esperadas
        columnas_esperadas = {'ProfileName', 'Text'}
        if not columnas_esperadas.issubset(reader.fieldnames):
            print("Error: El archivo CSV no contiene las columnas necesarias.")
            return

        # Procesar cada fila
        for row in reader:
            autor = row.get('ProfileName')
            contenido = row.get('Text')
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Analizar sentimiento
            analisis = TextBlob(contenido).sentiment
            sentimiento = 'Positivo' if analisis.polarity > 0 else 'Negativo' if analisis.polarity < 0 else 'Neutro'

            # Crear el nuevo post
            nuevo_post = {
                "autor": autor,
                "contenido": contenido,
                "fecha": fecha,
                "imagen": None,
                "sentimiento": sentimiento
            }

            # Insertar en MongoDB
            comentarios_collection.insert_one(nuevo_post)
        print("¡Posts cargados desde el dataset!")

# Configuración de la aplicación Flask
app = Flask(__name__)

# Configuración de MongoDB
app.config["MONGO_URI"] = "mongodb://localhost:27017/blog_db"
mongo = PyMongo(app)
comentarios_collection = mongo.db.comentarios

# Configuración de Redis
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

# Configuración de subida de archivos
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Verificar si el archivo es permitido
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Ruta principal (cargar comentarios)
@app.route('/')
def index():
    # Inicia el cronómetro
    start_time = time.time()
    # Desactivando Redis
    cached_comentarios = redis_client.get('comentarios')

    if cached_comentarios:
        comentarios = json.loads(cached_comentarios)
    else:
        comentarios = list(comentarios_collection.find())
    for comentario in comentarios:
        comentario["_id"] = str(comentario["_id"])  # Convertir ObjectId a string
    
    # Calcula el tiempo transcurrido
    elapsed_time = time.time() - start_time
    print(f"Tiempo de carga: {elapsed_time:.4f} segundos")

    
    redis_client.setex('comentarios', 600, json.dumps(comentarios))
    print("Comentarios cargados desde MongoDB y almacenados en Redis con TTL")
    print(f"Datos almacenados en Redis: {comentarios}")


    return render_template('index.html', comentarios=comentarios)

@app.route('/comentarios', methods=['GET', 'POST'])
def comentarios():
    if request.method == 'POST':
        autor = request.form['autor']
        contenido = request.form['contenido']
        archivo = request.files['imagen'] if 'imagen' in request.files else None

        # Manejar la imagen subida
        imagen_path = None
        if archivo and allowed_file(archivo.filename):
            filename = secure_filename(archivo.filename)
            imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            archivo.save(imagen_path)
            imagen_path = f'uploads/{filename}'

        # Análisis de sentimientos
        analisis = TextBlob(contenido).sentiment
        sentimiento = 'Positivo' if analisis.polarity > 0 else 'Negativo' if analisis.polarity < 0 else 'Neutro'

        # Crear el nuevo comentario
        nuevo_comentario = {
            "autor": autor,
            "contenido": contenido,
            "imagen": imagen_path,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sentimiento": sentimiento
        }

        # Insertar en MongoDB
        comentarios_collection.insert_one(nuevo_comentario)

        # Limpiar caché para que los nuevos comentarios aparezcan
        redis_client.delete('comentarios')

        return redirect(url_for('comentarios'))

    # Método GET: Mostrar los comentarios
    comentarios = list(comentarios_collection.find())
    for comentario in comentarios:
        comentario["_id"] = str(comentario["_id"])  # Convertir ObjectId a string

    return render_template('comentarios.html', comentarios=comentarios)

@app.route('/cargar_dataset', methods=['POST'])
def cargar_dataset():
    """Carga un dataset CSV en MongoDB y actualiza la caché en Redis."""
    archivo = request.files['dataset']
    if archivo and archivo.filename.endswith('.csv'):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(archivo.filename))
        archivo.save(filepath)  # Guardar el archivo en el servidor

        try:
            # Cargar los posts desde el CSV y guardarlos en MongoDB
            cargar_posts_desde_csv(filepath)
            
            # Después de cargar en MongoDB, actualiza la caché en Redis
            comentarios = list(comentarios_collection.find())
            for comentario in comentarios:
                comentario["_id"] = str(comentario["_id"])  # Convertir ObjectId a string
            
            # Guardar los datos en Redis con un TTL de 10 minutos
            redis_client.setex('comentarios', 600, json.dumps(comentarios))
            print("Comentarios actualizados en Redis después de cargar el dataset.")

            mensaje = "¡Dataset cargado exitosamente y datos guardados en Redis!"
        except Exception as e:
            mensaje = f"Error al cargar el dataset: {str(e)}"
        
        return render_template('comentarios.html', mensaje=mensaje)
    return render_template('comentarios.html', mensaje="Archivo no válido. Suba un archivo CSV.")



# Página "Acerca de"
@app.route('/about')
def about():
    return render_template('about.html')


# Página "Contacto"
@app.route('/contact')
def contact():
    return render_template('contact.html')


# Ruta para procesar mensajes de contacto
@app.route('/enviar_mensaje', methods=['POST'])
def enviar_mensaje():
    nombre = request.form['nombre']
    email = request.form['email']
    mensaje = request.form['mensaje']
    # Aquí podrías guardar el mensaje en la base de datos o enviarlo por correo
    print(f"Mensaje recibido de {nombre} ({email}): {mensaje}")
    return redirect(url_for('contact'))

@app.route('/borrar_comentarios', methods=['POST'])
def borrar_comentarios():
    """Borra todos los comentarios de la colección."""
    try:
        comentarios_collection.delete_many({})  # Elimina todos los documentos de la colección
        redis_client.delete('comentarios')  # Limpia la caché en Redis
        return "Todos los comentarios han sido eliminados.", 200
    except Exception as e:
        return f"Error al eliminar comentarios: {str(e)}", 500

@app.route('/limpiar_cache', methods=['POST'])
def limpiar_cache():
    try:
        redis_client.delete('comentarios')  # Borra la caché de comentarios
        return "Caché limpiada exitosamente.", 200
    except Exception as e:
        return f"Error al limpiar la caché: {str(e)}", 500



# Ejecutar la aplicación
if __name__ == '__main__':
    # Crear la carpeta de uploads si no existe
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    app.run(debug=True, host='0.0.0.0', port=5000)
