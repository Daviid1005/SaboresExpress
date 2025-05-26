# Importación de módulos necesarios para la aplicación Flask
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from authlib.integrations.flask_client import OAuth
import os
from werkzeug.utils import secure_filename
import shutil

# Creación de la instancia de la aplicación Flask
app = Flask(__name__)
# Configuración de la clave secreta para sesiones, generada aleatoriamente
app.secret_key = os.urandom(24)
# Configuración de la URI de la base de datos PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:root@localhost:5432/sabores_express'
# Desactivar el seguimiento de modificaciones para mejorar el rendimiento
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de la carpeta para subir imágenes
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Extensiones de archivo permitidas para las imágenes
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Creación de la carpeta de subidas si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Inicialización de SQLAlchemy para la gestión de la base de datos
db = SQLAlchemy(app)
# Inicialización de Flask-Migrate para manejar migraciones de la base de datos
migrate = Migrate(app, db)

# Configuración de OAuth para autenticación con Google
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id='TU_CLIENT_ID',  # ID del cliente de Google OAuth
    client_secret='TU_CLIENT_SECRET',  # Secreto del cliente de Google OAuth
    access_token_url='https://oauth2.googleapis.com/token',  # URL para obtener el token de acceso
    authorize_url='https://accounts.google.com/o/oauth2/auth',  # URL para autorización
    api_base_url='https://www.googleapis.com/oauth2/v1/',  # URL base para la API de Google
    client_kwargs={'scope': 'openid profile email'},  # Ámbitos de la autenticación
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs'  # URI para las claves públicas de Google
)

# Definición del modelo Usuario para la base de datos
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)  # ID único del usuario
    nombre = db.Column(db.String(100), nullable=False)  # Nombre del usuario
    email = db.Column(db.String(100), unique=True, nullable=False)  # Correo único del usuario
    password = db.Column(db.String(100))  # Contraseña del usuario (puede ser nula para usuarios de Google)

# Definición del modelo Restaurante para la base de datos
class Restaurante(db.Model):
    __tablename__ = 'restaurantes'
    id = db.Column(db.Integer, primary_key=True)  # ID único del restaurante
    nombre = db.Column(db.String(100), nullable=False)  # Nombre del restaurante
    descripcion = db.Column(db.Text)  # Descripción del restaurante
    categoria = db.Column(db.String(100), nullable=False)  # Categoría del restaurante
    imagen = db.Column(db.String(255), nullable=True)  # Ruta de la imagen del restaurante
    menus = db.relationship('Menu', backref='restaurante')  # Relación con los menús
    pedidos = db.relationship('Pedido', backref='restaurante')  # Relación con los pedidos

# Definición del modelo Menu para la base de datos
class Menu(db.Model):
    __tablename__ = 'menus'
    id = db.Column(db.Integer, primary_key=True)  # ID único del menú
    restaurante_id = db.Column(db.Integer, db.ForeignKey('restaurantes.id'))  # ID del restaurante asociado
    nombre = db.Column(db.String(100), nullable=False)  # Nombre del menú
    descripcion = db.Column(db.Text)  # Descripción del menú
    precio = db.Column(db.Float, nullable=False)  # Precio del menú
    categoria = db.Column(db.String(100), nullable=False)  # Categoría del menú
    imagen = db.Column(db.String(255), nullable=True)  # Ruta de la imagen del menú

# Definición del modelo Pedido para la base de datos
class Pedido(db.Model):
    __tablename__ = 'pedidos'
    id = db.Column(db.Integer, primary_key=True)  # ID único del pedido
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))  # ID del usuario asociado
    restaurante_id = db.Column(db.Integer, db.ForeignKey('restaurantes.id'))  # ID del restaurante asociado
    fecha = db.Column(db.DateTime, server_default=db.func.now())  # Fecha de creación del pedido
    total = db.Column(db.Float)  # Total del pedido
    metodo_pago = db.Column(db.String(50))  # Método de pago
    metodo_pago_detalle = db.Column(db.Text)  # Detalles del método de pago
    direccion_entrega = db.Column(db.Text)  # Dirección de entrega
    numero_celular = db.Column(db.String(20))  # Número de celular
    nombre_cliente = db.Column(db.String(100))  # Nombre del cliente
    tipo_entrega = db.Column(db.String(50))  # Tipo de entrega (domicilio o reserva)
    hora_reserva = db.Column(db.String(10))  # Hora de la reserva
    fecha_reserva = db.Column(db.String(10))  # Fecha de la reserva
    estado = db.Column(db.String(50), default='pendiente')  # Estado del pedido
    usuario = db.relationship('Usuario', backref='pedidos')  # Relación con el usuario
    items = db.relationship('ItemPedido', backref='pedido')  # Relación con los ítems del pedido

# Definición del modelo ItemPedido para la base de datos
class ItemPedido(db.Model):
    __tablename__ = 'items_pedido'
    id = db.Column(db.Integer, primary_key=True)  # ID único del ítem del pedido
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'))  # ID del pedido asociado
    menu_id = db.Column(db.Integer, db.ForeignKey('menus.id'))  # ID del menú asociado
    cantidad = db.Column(db.Integer, nullable=False)  # Cantidad de ítems
    precio = db.Column(db.Float, nullable=False)  # Precio del ítem
    menu = db.relationship('Menu', backref='items_pedido')  # Relación con el menú

# Función para verificar si la extensión del archivo es permitida
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Función para copiar una imagen desde una ruta local a la carpeta de subidas
def copy_image_from_path(source_path, destination_dir):
    if not os.path.exists(source_path):
        return None
    filename = secure_filename(os.path.basename(source_path))  # Obtener nombre seguro del archivo
    destination_path = os.path.join(destination_dir, filename)  # Ruta de destino
    shutil.copy2(source_path, destination_path)  # Copiar archivo
    return os.path.join('uploads', filename)  # Retornar ruta relativa

# Ruta principal: redirige a restaurantes si hay sesión activa, o a login si no
@app.route('/')
def index():
    if 'user_id' in session or 'guest' in session:
        return redirect(url_for('restaurantes'))
    return redirect(url_for('login'))

# Ruta para el inicio de sesión
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']  # Obtener correo del formulario
        password = request.form['password']  # Obtener contraseña del formulario
        is_admin = email.endswith('@admin.saboresexpress.com')  # Verificar si es administrador
        is_client = email.endswith('@gmail.com')  # Verificar si es cliente
        if not (is_admin or is_client):
            flash('Debes usar un correo @gmail.com para clientes o @admin.saboresexpress.com para administradores.')
            return redirect(url_for('login'))
        usuario = Usuario.query.filter_by(email=email, password=password).first()  # Buscar usuario
        if usuario:
            if is_admin:
                session['admin_id'] = usuario.id  # Guardar ID de administrador en la sesión
                flash('Inicio de sesión de administrador exitoso.')
                return redirect(url_for('admin'))
            else:
                session['user_id'] = usuario.id  # Guardar ID de usuario en la sesión
                session.pop('guest', None)  # Eliminar modo invitado
                flash('Inicio de sesión exitoso.')
                return redirect(url_for('restaurantes'))
        flash('Correo o contraseña incorrectos.')
    return render_template('login.html')

# Ruta para el registro de usuarios
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']  # Obtener nombre del formulario
        email = request.form['email']  # Obtener correo del formulario
        password = request.form['password']  # Obtener contraseña del formulario
        is_admin = email.endswith('@admin.saboresexpress.com')  # Verificar si es administrador
        is_client = email.endswith('@gmail.com')  # Verificar si es cliente
        if not (is_admin or is_client):
            flash('Debes usar un correo @gmail.com para clientes o @admin.saboresexpress.com para administradores.')
            return redirect(url_for('registro'))
        if Usuario.query.filter_by(email=email).first():
            flash('El correo ya está registrado.')
            return redirect(url_for('registro'))
        usuario = Usuario(nombre=nombre, email=email, password=password)  # Crear nuevo usuario
        db.session.add(usuario)
        db.session.commit()
        flash('Registro exitoso. Por favor, inicia sesión.')
        return redirect(url_for('login'))
    return render_template('registro.html')

# Ruta para iniciar sesión con Google
@app.route('/login/google')
def login_google():
    redirect_uri = url_for('authorize', _external=True)  # Obtener URI de redirección
    return google.authorize_redirect(redirect_uri)  # Redirigir a Google para autenticación

# Ruta para manejar la autorización de Google
@app.route('/authorize')
def authorize():
    try:
        token = google.authorize_access_token()  # Obtener token de acceso
        user_info = google.parse_id_token(token, nonce=None)  # Obtener información del usuario
        email = user_info['email']
        nombre = user_info['name']
        if email.endswith('@admin.saboresexpress.com'):
            flash('Los administradores deben usar la página de inicio de sesión.')
            return redirect(url_for('login'))
        if not email.endswith('@gmail.com'):
            flash('Los clientes deben usar un correo @gmail.com.')
            return redirect(url_for('login'))
        usuario = Usuario.query.filter_by(email=email).first()
        if not usuario:
            usuario = Usuario(nombre=nombre, email=email, password='')  # Crear usuario si no existe
            db.session.add(usuario)
            db.session.commit()
        session['user_id'] = usuario.id  # Guardar ID de usuario en la sesión
        session.pop('guest', None)  # Eliminar modo invitado
        flash('Inicio de sesión con Google exitoso.')
        return redirect(url_for('restaurantes'))
    except Exception as e:
        flash(f'Error al autenticar con Google: {str(e)}')
        return redirect(url_for('login'))

# Ruta para entrar como invitado
@app.route('/guest')
def guest():
    session['guest'] = True  # Establecer modo invitado
    flash('Has entrado como invitado.')
    return redirect(url_for('restaurantes'))

# Ruta para cerrar sesión
@app.route('/logout')
def logout():
    session.pop('user_id', None)  # Eliminar ID de usuario
    session.pop('admin_id', None)  # Eliminar ID de administrador
    session.pop('guest', None)  # Eliminar modo invitado
    session.pop('carrito', None)  # Eliminar carrito
    flash('Sesión cerrada.')
    return redirect(url_for('login'))

# Ruta para mostrar los restaurantes
@app.route('/restaurantes')
def restaurantes():
    if 'user_id' not in session and 'guest' not in session:
        return redirect(url_for('login'))
    busqueda = request.args.get('busqueda', '')  # Obtener término de búsqueda
    if busqueda:
        restaurantes = Restaurante.query.filter(Restaurante.nombre.ilike(f'%{busqueda}%')).all()  # Filtrar por nombre
    else:
        restaurantes = Restaurante.query.all()  # Obtener todos los restaurantes
    # Obtener los 3 restaurantes más populares basados en el número de pedidos
    restaurantes_populares = db.session.query(Restaurante, db.func.count(Pedido.id))\
        .join(Pedido, isouter=True)\
        .group_by(Restaurante.id)\
        .order_by(db.func.count(Pedido.id).desc())\
        .limit(3)\
        .all()
    return render_template('restaurantes.html', restaurantes=restaurantes, busqueda=busqueda, restaurantes_populares=restaurantes_populares)

# Ruta para mostrar el menú de un restaurante
@app.route('/menu/<int:restaurante_id>')
def menu(restaurante_id):
    if 'user_id' not in session and 'guest' not in session:
        return redirect(url_for('login'))
    restaurante = Restaurante.query.get_or_404(restaurante_id)  # Obtener restaurante o devolver 404
    busqueda = request.args.get('busqueda', '')  # Obtener término de búsqueda
    if busqueda:
        menus = Menu.query.filter_by(restaurante_id=restaurante_id)\
            .filter(Menu.nombre.ilike(f'%{busqueda}%'))\
            .all()  # Filtrar menús por nombre
    else:
        menus = Menu.query.filter_by(restaurante_id=restaurante_id).all()  # Obtener todos los menús
    # Obtener los 3 menús más populares basados en los ítems pedidos
    menus_populares = db.session.query(Menu, db.func.count(ItemPedido.id), Restaurante)\
        .join(ItemPedido, isouter=True)\
        .join(Restaurante, Menu.restaurante_id == Restaurante.id)\
        .group_by(Menu.id, Restaurante.id)\
        .order_by(db.func.count(ItemPedido.id).desc())\
        .limit(3)\
        .all()
    if 'carrito' not in session:
        session['carrito'] = {}  # Inicializar carrito si no existe
    carrito = session['carrito'].get(str(restaurante_id), [])  # Obtener carrito del restaurante
    total = sum(item['subtotal'] for item in carrito)  # Calcular total del carrito
    return render_template('menu.html', restaurante=restaurante, menus=menus, busqueda=busqueda, menus_populares=menus_populares, carrito_items=carrito, total=total)

# Ruta para agregar ítems al carrito
@app.route('/agregar_carrito/<int:restaurante_id>/<int:menu_id>', methods=['POST'])
def agregar_carrito(restaurante_id, menu_id):
    if 'user_id' not in session and 'guest' not in session:
        return redirect(url_for('login'))
    if 'guest' in session:
        flash('Los invitados no pueden agregar ítems al carrito. Por favor, inicia sesión.')
        return redirect(url_for('menu', restaurante_id=restaurante_id))
    menu = Menu.query.get_or_404(menu_id)  # Obtener menú o devolver 404
    cantidad = int(request.form['cantidad'])  # Obtener cantidad del formulario
    if 'carrito' not in session:
        session['carrito'] = {}  # Inicializar carrito si no existe
    if str(restaurante_id) not in session['carrito']:
        session['carrito'][str(restaurante_id)] = []  # Inicializar carrito para el restaurante
    carrito = session['carrito'][str(restaurante_id)]
    item = next((i for i in carrito if i['menu_id'] == menu_id), None)  # Buscar ítem en el carrito
    if item:
        item['cantidad'] += cantidad  # Aumentar cantidad si el ítem ya está
        item['subtotal'] = item['cantidad'] * menu.precio  # Actualizar subtotal
    else:
        carrito.append({
            'menu_id': menu_id,
            'nombre': menu.nombre,
            'cantidad': cantidad,
            'precio': menu.precio,
            'subtotal': cantidad * menu.precio
        })  # Agregar nuevo ítem al carrito
    session['carrito'][str(restaurante_id)] = carrito
    session.modified = True  # Marcar la sesión como modificada
    flash('Ítem añadido al carrito.')
    return redirect(url_for('menu', restaurante_id=restaurante_id))

# Ruta para eliminar ítems del carrito
@app.route('/eliminar_carrito/<int:restaurante_id>/<int:menu_id>', methods=['POST'])
def eliminar_carrito(restaurante_id, menu_id):
    if 'user_id' not in session and 'guest' not in session:
        return redirect(url_for('login'))
    if 'guest' in session:
        flash('Los invitados no pueden modificar el carrito. Por favor, inicia sesión.')
        return redirect(url_for('menu', restaurante_id=restaurante_id))
    if 'carrito' not in session or str(restaurante_id) not in session['carrito']:
        flash('El carrito está vacío.')
        return redirect(url_for('menu', restaurante_id=restaurante_id))
    carrito = session['carrito'][str(restaurante_id)]
    session['carrito'][str(restaurante_id)] = [item for item in carrito if item['menu_id'] != menu_id]  # Eliminar ítem
    if not session['carrito'][str(restaurante_id)]:
        session['carrito'].pop(str(restaurante_id), None)  # Eliminar carrito si está vacío
    session.modified = True  # Marcar la sesión como modificada
    flash('Ítem eliminado del carrito.')
    return redirect(url_for('menu', restaurante_id=restaurante_id))

# Ruta para seleccionar método de pago
@app.route('/seleccionar_pago', methods=['POST'])
def seleccionar_pago():
    if 'user_id' not in session and 'guest' not in session:
        return redirect(url_for('login'))
    if 'guest' in session:
        flash('Los invitados no pueden seleccionar método de pago. Por favor, inicia sesión.')
        return redirect(url_for('restaurantes'))
    metodo_pago = request.form.get('metodo_pago')  # Obtener método de pago
    if metodo_pago not in ['tarjeta', 'banca_movil', 'transferencia']:
        flash('Método de pago inválido.')
        return redirect(url_for('restaurantes'))
    if metodo_pago == 'tarjeta':
        numero_tarjeta = request.form.get('numero_tarjeta')
        fecha_vencimiento = request.form.get('fecha_vencimiento')
        cvv = request.form.get('cvv')
        if not (numero_tarjeta and fecha_vencimiento and cvv):
            flash('Por favor completa todos los datos de la tarjeta.')
            return redirect(url_for('restaurantes'))
        session['metodo_pago_detalle'] = f"Número de Tarjeta: {numero_tarjeta}, Fecha de Vencimiento: {fecha_vencimiento}, CVV: {cvv}"
    elif metodo_pago == 'banca_movil':
        numero_celular = request.form.get('numero_celular')
        nombre_titular = request.form.get('nombre_titular')
        if not (numero_celular and nombre_titular):
            flash('Por favor completa todos los datos de banca móvil.')
            return redirect(url_for('restaurantes'))
        session['metodo_pago_detalle'] = f"Número de Celular: {numero_celular}, Nombre del Titular: {nombre_titular}"
    elif metodo_pago == 'transferencia':
        numero_cuenta = request.form.get('numero_cuenta')
        nombre_titular = request.form.get('nombre_titular')
        if not (numero_cuenta and nombre_titular):
            flash('Por favor completa todos los datos de la transferencia.')
            return redirect(url_for('restaurantes'))
        session['metodo_pago_detalle'] = f"Número de Cuenta: {numero_cuenta}, Nombre del Titular: {nombre_titular}"
    session['metodo_pago'] = metodo_pago
    flash(f'Método de pago seleccionado: {metodo_pago}')
    return redirect(url_for('restaurantes'))

# Ruta para confirmar un pedido
@app.route('/confirmar_pedido/<int:restaurante_id>', methods=['POST'])
def confirmar_pedido(restaurante_id):
    if 'user_id' not in session and 'guest' not in session:
        return redirect(url_for('login'))
    if 'guest' in session:
        flash('Los invitados no pueden confirmar pedidos. Por favor, inicia sesión.')
        return redirect(url_for('menu', restaurante_id=restaurante_id))
    if 'carrito' not in session or str(restaurante_id) not in session['carrito']:
        flash('El carrito está vacío.')
        return redirect(url_for('menu', restaurante_id=restaurante_id))
    metodo_pago = session.get('metodo_pago')  # Obtener método de pago de la sesión
    metodo_pago_detalle = session.get('metodo_pago_detalle')  # Obtener detalles del método de pago
    if not metodo_pago:
        flash('Por favor selecciona un método de pago.')
        return redirect(url_for('menu', restaurante_id=restaurante_id))
    tipo_entrega = request.form['tipo_entrega']  # Obtener tipo de entrega
    if tipo_entrega not in ['domicilio', 'reserva']:
        flash('Tipo de entrega inválido.')
        return redirect(url_for('menu', restaurante_id=restaurante_id))
    nombre_cliente = request.form.get('nombre_cliente')
    if not nombre_cliente:
        flash('El nombre del cliente es obligatorio.')
        return redirect(url_for('menu', restaurante_id=restaurante_id))
    if tipo_entrega == 'domicilio':
        direccion = request.form.get('direccion')
        numero_celular = request.form.get('numero_celular')
        if not (direccion and numero_celular):
            flash('Por favor ingresa todos los datos para la entrega a domicilio.')
            return redirect(url_for('menu', restaurante_id=restaurante_id))
        hora_reserva = None
        fecha_reserva = None
    else:
        hora_reserva = request.form.get('hora_reserva')
        fecha_reserva = request.form.get('fecha_reserva')
        if not (hora_reserva and fecha_reserva):
            flash('Por favor ingresa todos los datos para la reserva.')
            return redirect(url_for('menu', restaurante_id=restaurante_id))
        direccion = None
        numero_celular = None
    carrito = session['carrito'][str(restaurante_id)]
    total = sum(item['subtotal'] for item in carrito)  # Calcular total
    pedido = Pedido(
        usuario_id=session['user_id'],
        restaurante_id=restaurante_id,
        total=total,
        metodo_pago=metodo_pago,
        metodo_pago_detalle=metodo_pago_detalle,
        direccion_entrega=direccion,
        numero_celular=numero_celular,
        nombre_cliente=nombre_cliente,
        tipo_entrega=tipo_entrega,
        hora_reserva=hora_reserva,
        fecha_reserva=fecha_reserva
    )  # Crear nuevo pedido
    db.session.add(pedido)
    db.session.flush()
    for item in carrito:
        item_pedido = ItemPedido(
            pedido_id=pedido.id,
            menu_id=item['menu_id'],
            cantidad=item['cantidad'],
            precio=item['precio']
        )  # Crear ítems del pedido
        db.session.add(item_pedido)
    db.session.commit()
    restaurante = Restaurante.query.get(restaurante_id)
    items_pedido = ItemPedido.query.filter_by(pedido_id=pedido.id).all()
    session['carrito'] = {}  # Vaciar carrito
    session.modified = True
    flash('Pedido confirmado exitosamente.')
    return render_template('recibo.html', pedido=pedido, restaurante=restaurante, items_pedido=items_pedido)

# Ruta para el panel de administración
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        if 'restaurante' in request.form:
            nombre = request.form['nombre']
            descripcion = request.form['descripcion']
            categoria = request.form['categoria']
            imagen_file = request.files.get('imagen')
            
            imagen_path = None
            if imagen_file and allowed_file(imagen_file.filename):
                filename = secure_filename(imagen_file.filename)
                imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                imagen_file.save(imagen_path)  # Guardar imagen
                imagen_path = imagen_path.replace('static/', '')
            else:
                local_image_path = 'C:/Users/ASUS/Pictures/imagen.jpg'
                imagen_path = copy_image_from_path(local_image_path, app.config['UPLOAD_FOLDER'])
            
            restaurante = Restaurante(
                nombre=nombre,
                descripcion=descripcion,
                categoria=categoria,
                imagen=imagen_path if imagen_path else 'uploads/default.jpg'
            )  # Crear nuevo restaurante
            db.session.add(restaurante)
            db.session.commit()
            flash('Restaurante añadido.')
        elif 'menu' in request.form:
            restaurante_id = request.form['restaurante_id']
            nombre = request.form['nombre']
            descripcion = request.form['descripcion']
            precio = float(request.form['precio'])
            categoria = request.form['categoria']
            imagen_file = request.files.get('imagen')
            
            imagen_path = None
            if imagen_file and allowed_file(imagen_file.filename):
                filename = secure_filename(imagen_file.filename)
                imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                imagen_file.save(imagen_path)
                imagen_path = imagen_path.replace('static/', '')
            else:
                local_image_path = 'C:/Users/ASUS/Pictures/imagen_menu.jpg'
                imagen_path = copy_image_from_path(local_image_path, app.config['UPLOAD_FOLDER'])
            
            menu = Menu(
                restaurante_id=restaurante_id,
                nombre=nombre,
                descripcion=descripcion,
                precio=precio,
                categoria=categoria,
                imagen=imagen_path if imagen_path else 'uploads/default.jpg'
            )  # Crear nuevo menú
            db.session.add(menu)
            db.session.commit()
            flash('Menú añadido.')
    restaurantes = Restaurante.query.all()
    menus = Menu.query.all()
    return render_template('admin.html', restaurantes=restaurantes, menus=menus)

# Ruta para eliminar un restaurante
@app.route('/eliminar_restaurante/<int:restaurante_id>', methods=['POST'])
def eliminar_restaurante(restaurante_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    restaurante = Restaurante.query.get_or_404(restaurante_id)  # Obtener restaurante o devolver 404
    db.session.delete(restaurante)
    db.session.commit()
    flash('Restaurante eliminado exitosamente.')
    return redirect(url_for('admin'))

# Ruta para eliminar un menú
@app.route('/eliminar_menu/<int:menu_id>', methods=['POST'])
def eliminar_menu(menu_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    menu = Menu.query.get_or_404(menu_id)  # Obtener menú o devolver 404
    db.session.delete(menu)
    db.session.commit()
    flash('Menú eliminado exitosamente.')
    return redirect(url_for('admin'))

# Ruta para actualizar un restaurante
@app.route('/actualizar_restaurante/<int:restaurante_id>', methods=['GET', 'POST'])
def actualizar_restaurante(restaurante_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    restaurante = Restaurante.query.get_or_404(restaurante_id)  # Obtener restaurante o devolver 404
    if request.method == 'POST':
        restaurante.nombre = request.form['nombre']
        restaurante.descripcion = request.form['descripcion']
        restaurante.categoria = request.form['categoria']
        imagen_file = request.files.get('imagen')
        
        if imagen_file and allowed_file(imagen_file.filename):
            filename = secure_filename(imagen_file.filename)
            imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            imagen_file.save(imagen_path)
            restaurante.imagen = imagen_path.replace('static/', '')  # Actualizar imagen
        
        db.session.commit()
        flash('Restaurante actualizado exitosamente.')
        return redirect(url_for('admin'))
    
    return render_template('actualizar_restaurante.html', restaurante=restaurante)

# Ruta para actualizar un menú
@app.route('/actualizar_menu/<int:menu_id>', methods=['GET', 'POST'])
def actualizar_menu(menu_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    menu = Menu.query.get_or_404(menu_id)  # Obtener menú o devolver 404
    restaurantes = Restaurante.query.all()  # Obtener todos los restaurantes
    if request.method == 'POST':
        menu.restaurante_id = request.form['restaurante_id']
        menu.nombre = request.form['nombre']
        menu.descripcion = request.form['descripcion']
        menu.precio = float(request.form['precio'])
        menu.categoria = request.form['categoria']
        imagen_file = request.files.get('imagen')
        
        if imagen_file and allowed_file(imagen_file.filename):
            filename = secure_filename(imagen_file.filename)
            imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            imagen_file.save(imagen_path)
            menu.imagen = imagen_path.replace('static/', '')  # Actualizar imagen
        
        db.session.commit()
        flash('Menú actualizado exitosamente.')
        return redirect(url_for('admin'))
    
    return render_template('actualizar_menu.html', menu=menu, restaurantes=restaurantes)

# Contexto de la aplicación para inicializar la base de datos y poblar datos iniciales
with app.app_context():
    db.create_all()  # Crear todas las tablas definidas
    if not Restaurante.query.first():  # Verificar si no hay restaurantes
        restaurante_image_path = 'C:/Users/ASUS/Pictures/restaurante.jpg'  # Ruta de imagen predeterminada para restaurantes
        menu_image_path = 'C:/Users/ASUS/Pictures/menu.jpg'  # Ruta de imagen predeterminada para menús
        
        # Lista de restaurantes iniciales
        restaurantes = [
            Restaurante(
                nombre='Wabi Sabi Sushi Bar',
                descripcion='Restaurante especializado en sushi y cocina japonesa auténtica',
                categoria='Sushi',
                imagen='uploads/wabisabisushibar.jpg'
            ),
            Restaurante(
                nombre='PamDay',
                descripcion='Sushi fresco y auténtico con un toque moderno',
                categoria='Sushi',
                imagen=copy_image_from_path(restaurante_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pamday.jpg'
            )
        ]
        
        # Agregar más restaurantes
        restaurantes.extend([
            Restaurante(
                nombre='Pollo Broaster La Brasil',
                descripcion='Especialistas en pollo broaster crujiente',
                categoria='Pollo',
                imagen=copy_image_from_path(restaurante_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pollobrosterlabrasil.jpg'
            ),
            Restaurante(
                nombre='Kroky',
                descripcion='Pollo broaster con un toque único',
                categoria='Pollo',
                imagen=copy_image_from_path(restaurante_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/kroky.jpg'
            )
        ])
        
        restaurantes.extend([
            Restaurante(
                nombre="Q'Riko!",
                descripcion='Sabores auténticos de la cocina china',
                categoria='Casa China',
                imagen=copy_image_from_path(restaurante_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/qriko.jpg'
            ),
            Restaurante(
                nombre="FORTUNA'Z",
                descripcion='Tradición china en cada plato',
                categoria='Casa China',
                imagen=copy_image_from_path(restaurante_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/fortunaz.jpg'
            ),
            Restaurante(
                nombre='Casa China Restaurante',
                descripcion='Un clásico de la comida china',
                categoria='Casa China',
                imagen=copy_image_from_path(restaurante_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/casachinarestaurante.jpg'
            )
        ])
        
        restaurantes.extend([
            Restaurante(
                nombre='Alitas y algo más',
                descripcion='Alitas y opciones rápidas para todos los gustos',
                categoria='Comidas Rápidas',
                imagen=copy_image_from_path(restaurante_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/alitasyalgomas.jpg'
            ),
            Restaurante(
                nombre='Chervo Pizza',
                descripcion='Pizzas rápidas y deliciosas',
                categoria='Comidas Rápidas',
                imagen=copy_image_from_path(restaurante_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/chervopizza.jpg'
            ),
            Restaurante(
                nombre='Pizzeria LUWAK',
                descripcion='Pizzas artesanales para llevar',
                categoria='Comidas Rápidas',
                imagen=copy_image_from_path(restaurante_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pizerialuwak.jpg'
            ),
            Restaurante(
                nombre='Pizza Express',
                descripcion='Entrega rápida de pizzas frescas',
                categoria='Comidas Rápidas',
                imagen=copy_image_from_path(restaurante_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pizzaexpress.jpg'
            )
        ])
        
        db.session.bulk_save_objects(restaurantes)  # Guardar restaurantes en la base de datos
        db.session.commit()

        # Menús para Wabi Sabi Sushi Bar
        menus_wabi = [
            Menu(
                restaurante_id=1,
                nombre='Edamame',
                descripcion='Vainas de soja al vapor',
                precio=4.50,
                categoria='Entradas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Edamame.jpeg'
            ),
            Menu(
                restaurante_id=1,
                nombre='Vegetales Tempura',
                descripcion='Mix de vegetales de tempura, rebosados en tempura, acompañados de salsa ponzu',
                precio=5.00,
                categoria='Entradas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/VegetalesTempura.jpeg'
            ),
            Menu(
                restaurante_id=1,
                nombre='Guozas de Cerdo',
                descripcion='Tradicionales empanadillas japonesas rellenas de cerdo, cebolla, jengibre y col',
                precio=5.00,
                categoria='Entradas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/GuozasdeCerdo.jpeg'
            ),
            Menu(
                restaurante_id=1,
                nombre='Okonomiyaki de Cerdo',
                descripcion='Tradicional tortilla japonesa cocida a la plancha rellena de cerdo y vegetales con una cobertura de salsa TonKatsu, mayonesa y katsuobushi',
                precio=7.50,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/OkonomiyakideCerdo.jpeg'
            ),
            Menu(
                restaurante_id=1,
                nombre='Karaage',
                descripcion='Pollo frito estilo japonés, guarnición de arroz furikake',
                precio=9.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Karaage.jpeg'
            ),
            Menu(
                restaurante_id=1,
                nombre='Ramen Vegetariano',
                descripcion='Sopa a base de fondo de vegetales y hongos shitake. Ajitama, huevo cocido marinado, maíz dulce, tofu al banco y vegetales de temporada',
                precio=9.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/RamenVegetariano.jpeg'
            )
        ]
        db.session.bulk_save_objects(menus_wabi)
        db.session.commit()

        # Menús para PamDay
        menus_pamday = [
            Menu(
                restaurante_id=2,
                nombre='Tokio Sushi',
                descripcion='12 bocados de sushi, 1 tipo de rollito a elección acompañados con vegetales y s17.50',
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Kappuru.jpeg'
            ),
            Menu(
                restaurante_id=2,
                nombre='Kita Midori',
                descripcion='Camarón furai, queso crema, vegetales tempura, cubierto de aguacate caramelizado',
                precio=8.00,
                categoria='Rollitos',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/KitaMidori.jpeg'
            ),
            Menu(
                restaurante_id=2,
                nombre='Ramen',
                descripcion='Una perfecta combinación de sabores, viene acompañado por panceta, naruto (cangrejo), cebollín, champiñones, zanahoria y huevo cocido marinado en una salsa especial',
                precio=5.50,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Ramen.jpeg'
            ),
            Menu(
                restaurante_id=2,
                nombre='Sushi Dog',
                descripcion='Un rollo crocante, frito totalmente cubierto de panko y relleno de pollo especial bbq, lechuga y aguacate cubierto con una mayonesa especial y queso cheddar semipicante',
                precio=6.75,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/SushiDog.jpeg'
            ),
            Menu(
                restaurante_id=2,
                nombre='Infusión Maracuyá',
                descripcion='Bebida refrescante a base de maracuyá',
                precio=1.50,
                categoria='Bebidas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/InfusiónMaracuyá.jpeg'
            )
        ]
        db.session.bulk_save_objects(menus_pamday)
        db.session.commit()

        # Menús para Pollo Broaster La Brasil
        menus_pollobrasil = [
            Menu(
                restaurante_id=3,
                nombre='Papas fritas + Presa de pollo',
                descripcion='Porción de papas fritas acompañada de una presa de pollo',
                precio=1.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/papas + presa.png'
            ),
            Menu(
                restaurante_id=3,
                nombre='Arroz + Papas fritas + Presa de pollo',
                descripcion='Combinación de arroz, papas fritas y una presa de pollo',
                precio=1.30,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/arroz + papas +presa.jpeg'
            ),
            Menu(
                restaurante_id=3,
                nombre='Arroz + Papas fritas + Pechuga',
                descripcion='Combinación de arroz, papas fritas y una pechuga de pollo',
                precio=1.50,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/arroz + papas + pechuga.jpeg'
            ),
            Menu(
                restaurante_id=3,
                nombre='Papas fritas + 2 Presas de pollo',
                descripcion='Porción de papas fritas con dos presas de pollo',
                precio=2.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/papas + 2 presas.jpeg'
            ),
            Menu(
                restaurante_id=3,
                nombre='Choripapa',
                descripcion='Papas fritas con chorizo',
                precio=1.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/choripapa.jpeg'
            ),
            Menu(
                restaurante_id=3,
                nombre='Salchipapa',
                descripcion='Papas fritas con salchicha',
                precio=0.70,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/salchipapa.jpeg'
            )
        ]
        db.session.bulk_save_objects(menus_pollobrasil)
        db.session.commit()

        # Menús para Kroky
        menus_kroky = [
            Menu(
                restaurante_id=4,
                nombre='1/2 Porción: 1 Presa + Papas',
                descripcion='Media porción con una presa de pollo y papas fritas',
                precio=2.35,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/1-2Porción1Presa+Papas.jpeg'
            ),
            Menu(
                restaurante_id=4,
                nombre='1 Porción: 2 Presas + Papas',
                descripcion='Porción completa con dos presas de pollo y papas fritas',
                precio=3.90,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/1Porción2 Presas+Papas.jpeg'
            ),
            Menu(
                restaurante_id=4,
                nombre='1/2 Pollo: 4 Presas + Papas',
                descripcion='Media pollo con cuatro presas y papas fritas',
                precio=8.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/1-2Pollo4Presas+Papas.jpeg'
            ),
            Menu(
                restaurante_id=4,
                nombre='1 Pollo: 8 Presas + Papas',
                descripcion='Pollo entero con ocho presas y papas fritas',
                precio=15.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/1Pollo8Presas+Papas.jpeg'
            ),
            Menu(
                restaurante_id=4,
                nombre='Hamburguesa',
                descripcion='Hamburguesa clásica',
                precio=2.50,
                categoria='Comidas Rápidas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Hamburguesa.jpeg'
            ),
            Menu(
                restaurante_id=4,
                nombre='Salchipapa',
                descripcion='Papas fritas con salchicha',
                precio=2.00,
                categoria='Comidas Rápidas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Salchipapa.jpeg'
            )
        ]
        db.session.bulk_save_objects(menus_kroky)
        db.session.commit()

        # Menús para Q'Riko!
        menus_qriko = [
            Menu(
                restaurante_id=5,
                nombre='Chaufa de Pollo',
                descripcion='Arroz frito con pollo, verduras y salsa de soja',
                precio=2.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/chaufa pollo.jpeg'
            ),
            Menu(
                restaurante_id=5,
                nombre='Chaufa de Carne',
                descripcion='Arroz frito con carne, verduras y salsa de soja',
                precio=2.20,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/chaulafan de carne.jpeg'
            ),
            Menu(
                restaurante_id=5,
                nombre='Chaufa Mixto',
                descripcion='Arroz frito con pollo, carne, verduras y salsa de soja',
                precio=2.50,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/chaulafan de mixto.jpeg'
            ),
            Menu(
                restaurante_id=5,
                nombre='Pollo Chi jau kai',
                descripcion='Pollo apanado con salsa agridulce y verduras',
                precio=2.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pollo chi.jpeg'
            ),
            Menu(
                restaurante_id=5,
                nombre='Tallarín Saltado de Pollo',
                descripcion='Tallarines salteados con pollo y verduras',
                precio=2.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/tallarin salteado de pollo.jpeg'
            ),
            Menu(
                restaurante_id=5,
                nombre='Tallarín Saltado Mixto',
                descripcion='Tallarines salteados con pollo, carne y verduras',
                precio=2.50,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/tallarin salteado mixto.jpeg'
            )
        ]
        db.session.bulk_save_objects(menus_qriko)
        db.session.commit()

        # Menús para FORTUNA'Z
        menus_fortunaz = [
            Menu(
                restaurante_id=6,
                nombre='Chaufa de Pollo',
                descripcion='Arroz frito con pollo, verduras y salsa de soja',
                precio=2.50,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/chaufa pollo 2.jpeg'
            ),
            Menu(
                restaurante_id=6,
                nombre='Taypa Especial',
                descripcion='Combinación de carnes y verduras salteadas en salsa especial',
                precio=8.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/taypa.jpeg'
            ),
            Menu(
                restaurante_id=6,
                nombre='Pollo Tipakay',
                descripcion='Pollo apanado con salsa agridulce y acompañamiento',
                precio=2.50,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/tipakay.jpeg'
            ),
            Menu(
                restaurante_id=6,
                nombre='Aeropuerto Especial',
                descripcion='Arroz chaufa con tallarines, pollo, carne y verduras',
                precio=4.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/aeropuerto especial.jpeg'
            )
        ]
        db.session.bulk_save_objects(menus_fortunaz)
        db.session.commit()

        # Menús para Casa China Restaurante
        menus_casachina = [
            Menu(
                restaurante_id=7,
                nombre='Chaufa de Pollo',
                descripcion='Arroz frito con pollo, verduras y salsa de soja',
                precio=2.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/chaulafan de pollo.jpeg'
            ),
            Menu(
                restaurante_id=7,
                nombre='Pollo Chi Jau Kai',
                descripcion='Pollo apanado con salsa agridulce y verduras',
                precio=2.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pollo chi2.jpeg'
            ),
            Menu(
                restaurante_id=7,
                nombre='Chaufa de Pollo',
                descripcion='Arroz frito con pollo, verduras y salsa de soja',
                precio=2.50,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/chaufa pollo.jpeg'
            ),
            Menu(
                restaurante_id=7,
                nombre='Taypa Especial',
                descripcion='Combinación de carnes y verduras salteadas en salsa especial',
                precio=8.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/taypa.jpeg'
            ),
            Menu(
                restaurante_id=7,
                nombre='Pollo Tipakay',
                descripcion='Pollo apanado con salsa agridulce y acompañamiento',
                precio=2.50,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/tipakay.jpeg'
            ),
            Menu(
                restaurante_id=7,
                nombre='Aeropuerto Especial',
                descripcion='Arroz chaufa con tallarines, pollo, carne y verduras',
                precio=4.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/aeropuerto especial.jpeg'
            )
        ]
        db.session.bulk_save_objects(menus_casachina)
        db.session.commit()

        # Menús para Alitas y algo más
        menus_alitas = [
            Menu(
                restaurante_id=8,
                nombre='Alitas BBQ (6 unidades)',
                descripcion='Alitas de pollo con salsa BBQ, acompañadas de papas fritas',
                precio=4.50,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Alitas BBQ (6 unidades).jpeg'
            ),
            Menu(
                restaurante_id=8,
                nombre='Alitas Picantes (6 unidades)',
                descripcion='Alitas de pollo con salsa picante, acompañadas de papas fritas',
                precio=4.50,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Alitas Picantes (6 unidades).jpeg'
            ),
            Menu(
                restaurante_id=8,
                nombre='Hamburguesa Clásica',
                descripcion='Hamburguesa con carne, lechuga, tomate y salsa especial',
                precio=3.00,
                categoria='Comidas Rápidas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Hamburguesa Clásica.jpeg'
            ),
            Menu(
                restaurante_id=8,
                nombre='Salchipapa Grande',
                descripcion='Papas fritas con salchicha y salsas',
                precio=2.50,
                categoria='Comidas Rápidas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Salchipapa Grande.jpeg'
            ),
            Menu(
                restaurante_id=8,
                nombre='Combo Familiar (12 alitas)',
                descripcion='12 alitas (mezcla de BBQ y picantes) con papas fritas grandes',
                precio=8.00,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Combo Familiar (12 alitas).jpeg'
            ),
            Menu(
                restaurante_id=8,
                nombre='Nuggets de Pollo (8 unidades)',
                descripcion='Nuggets de pollo crujientes con salsa a elección',
                precio=3.50,
                categoria='Platos Fuertes',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Nuggets de Pollo (8 unidades).jpeg'
            )
        ]
        db.session.bulk_save_objects(menus_alitas)
        db.session.commit()

        # Menús para Chervo Pizza
        menus_chervo = [
            Menu(
                restaurante_id=9,
                nombre='Pizza Hawaiana (Mediana)',
                descripcion='Pizza con jamón, piña, queso mozzarella y salsa de tomate',
                precio=6.00,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Pizza Hawaiana (Mediana).jpeg'
            ),
            Menu(
                restaurante_id=9,
                nombre='Pizza Pepperoni (Mediana)',
                descripcion='Pizza con pepperoni, queso mozzarella y salsa de tomate',
                precio=6.50,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pizza peperoni.jpeg'
            ),
            Menu(
                restaurante_id=9,
                nombre='Pizza Vegetariana (Mediana)',
                descripcion='Pizza con vegetales frescos, queso mozzarella y salsa de tomate',
                precio=5.50,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pizza vegetariana.jpeg'
            ),
            Menu(
                restaurante_id=9,
                nombre='Pizza Suprema (Grande)',
                descripcion='Pizza con pepperoni, jamón, champiñones, pimientos y queso',
                precio=9.00,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Pizza Suprema (Grande).jpeg'
            ),
            Menu(
                restaurante_id=9,
                nombre='Pizza Cuatro Quesos (Mediana)',
                descripcion='Pizza con mozzarella, cheddar, parmesano y gorgonzola',
                precio=7.00,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Pizza Cuatro Quesos (Mediana).jpeg'
            ),
            Menu(
                restaurante_id=9,
                nombre='Pizza Margarita (Pequeña)',
                descripcion='Pizza clásica con tomate, mozzarella y albahaca',
                precio=4.00,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Pizza Margarita (Pequeña).jpeg'
            )
        ]
        db.session.bulk_save_objects(menus_chervo)
        db.session.commit()

        # Menús para Pizzeria LUWAK
        menus_luwak = [
            Menu(
                restaurante_id=10,
                nombre='Pizza Clásica de Jamón (Mediana)',
                descripcion='Pizza con jamón, queso mozzarella y salsa de tomate',
                precio=5.50,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pizza jamon.jpeg'
            ),
            Menu(
                restaurante_id=10,
                nombre='Pizza de Pepperoni (Mediana)',
                descripcion='Pizza con pepperoni, queso mozzarella y salsa de tomate',
                precio=6.00,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pizza peperoni.jpeg'
            ),
            Menu(
                restaurante_id=10,
                nombre='Pizza Vegetariana (Grande)',
                descripcion='Pizza con vegetales frescos, queso y salsa de tomate',
                precio=8.00,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pizza vegetariana.jpeg'
            ),
            Menu(
                restaurante_id=10,
                nombre='Pizza de Pollo BBQ (Mediana)',
                descripcion='Pizza con pollo, salsa BBQ, queso y cebolla',
                precio=6.50,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pizza bbq.jpeg'
            ),
            Menu(
                restaurante_id=10,
                nombre='Pizza de Champiñones (Pequeña)',
                descripcion='Pizza con champiñones, queso mozzarella y salsa de tomate',
                precio=4.50,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pizza champiñones.jpeg'
            ),
            Menu(
                restaurante_id=10,
                nombre='Pizza Mixta (Grande)',
                descripcion='Pizza con jamón, pepperoni, vegetales y queso',
                precio=9.50,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pizza mixta.jpeg'
            )
        ]
        db.session.bulk_save_objects(menus_luwak)
        db.session.commit()

        # Menús para Pizza Express
        menus_pizzaexpress = [
            Menu(
                restaurante_id=11,
                nombre='Pizza de Jamón y Queso (Mediana)',
                descripcion='Pizza con jamón, queso mozzarella y salsa de tomate',
                precio=5.00,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pizza jamon.jpeg'
            ),
            Menu(
                restaurante_id=11,
                nombre='Pizza de Pepperoni (Grande)',
                descripcion='Pizza con pepperoni, queso mozzarella y salsa de tomate',
                precio=8.50,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/pizza peperoni.jpeg'
            ),
            Menu(
                restaurante_id=11,
                nombre='Pizza Hawaiana (Pequeña)',
                descripcion='Pizza con jamón, piña, queso y salsa de tomate',
                precio=4.00,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Pizza Hawaiana (Pequeña).jpeg'
            ),
            Menu(
                restaurante_id=11,
                nombre='Pizza de Pollo y Champiñones (Mediana)',
                descripcion='Pizza con pollo, champiñones, queso y salsa de tomate',
                precio=6.50,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Pizza de Pollo y Champiñones (Mediana).jpeg'
            ),
            Menu(
                restaurante_id=11,
                nombre='Pizza Cuatro Estaciones (Grande)',
                descripcion='Pizza con jamón, champiñones, alcachofas y aceitunas',
                precio=9.00,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Pizza Cuatro Estaciones (Grande).jpeg'
            ),
            Menu(
                restaurante_id=11,
                nombre='Pizza Margarita (Mediana)',
                descripcion='Pizza clásica con tomate, mozzarella y albahaca',
                precio=5.00,
                categoria='Pizzas',
                imagen=copy_image_from_path(menu_image_path, app.config['UPLOAD_FOLDER']) or 'uploads/Pizza Margarita (Mediana).jpeg'
            )
        ]
        db.session.bulk_save_objects(menus_pizzaexpress)
        db.session.commit()

    # Crear usuario administrador por defecto si no existe
    if not Usuario.query.filter_by(email='admin@admin.saboresexpress.com').first():
        admin = Usuario(nombre='Administrador', email='admin@admin.saboresexpress.com', password='admin123')
        db.session.add(admin)
        db.session.commit()

# Iniciar la aplicación en modo debug
if __name__ == '__main__':
    app.run(debug=True)