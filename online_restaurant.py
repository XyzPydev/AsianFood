from flask import Flask, render_template, request, redirect, url_for, flash, session

from flask_login import login_required, current_user, login_user, logout_user  # pip install flask-login

from online_restaurant_db import Session, Users, Menu, Orders, Reservation
from flask_login import LoginManager
from datetime import datetime

from geopy.distance import geodesic

import os
import uuid

import secrets

app = Flask(__name__)

FILES_PATH = 'static/menu'

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['MAX_FORM_MEMORY_SIZE'] = 1024 * 1024  # 1MB
app.config['MAX_FORM_PARTS'] = 500

app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'

app.config['SECRET_KEY'] = '#cv)3v7w$*s3fk;5c!@y0?:?№3"9)#'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

MARGANETS_COORDS = (47.6392, 34.6302)  # координати ресторану, за потреби зміни
KYIV_RADIUS_KM = 50  # допустима зона доставки/бронювання

TABLE_NUM = {
    "1-2": 5,
    "3-4": 3,
    "4+": 2
}

@login_manager.user_loader
def load_user(user_id):
    with Session() as session:
        user = session.query(Users).filter_by(id=user_id).first()
        if user:
            return user


@app.after_request
def apply_csp(response):
    nonce = secrets.token_urlsafe(16)
    csp = (
        f"default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        f"style-src 'self'; "
        f"frame-ancestors 'none'; "
        f"base-uri 'self'; "
        f"form-action 'self'"
    )
    response.headers["Content-Security-Policy"] = csp
    response.set_cookie('nonce', nonce)
    return response


@app.route("/")
@app.route("/home")
def home():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)

    with Session() as db:
        menu = db.query(Menu).filter_by(active=True).all()
    return render_template('home.html', menu=menu)



@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403
        nickname = request.form['nickname']
        email = request.form['email']
        password = request.form['password']

        with Session() as cursor:
            if cursor.query(Users).filter_by(email=email).first() or cursor.query(Users).filter_by(
                    nickname=nickname).first():
                flash('Користувач з таким email або нікнеймом вже існує!', 'danger')
                return render_template('register.html', csrf_token=session["csrf_token"])

            new_user = Users(nickname=nickname, email=email)
            new_user.set_password(password)
            cursor.add(new_user)
            cursor.commit()
            cursor.refresh(new_user)
            login_user(new_user)
            return redirect(url_for('home'))
    return render_template('register.html', csrf_token=session["csrf_token"])


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        nickname = request.form['nickname']
        password = request.form['password']

        with Session() as cursor:
            user = cursor.query(Users).filter_by(nickname=nickname).first()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for('home'))

            flash('Неправильний nickname або пароль!', 'danger')

    return render_template('login.html', csrf_token=session["csrf_token"])


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route("/add_position", methods=['GET', 'POST'])
@login_required
def add_position():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.method == "POST":
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        name = request.form['name']
        file = request.files.get('img')
        ingredients = request.form['ingredients']
        description = request.form['description']
        price = request.form['price']
        weight = request.form['weight']

        if not file or not file.filename:
            flash('Файл не вибрано або завантаження не вдалося', 'danger')
            return redirect(request.url)

        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        output_path = os.path.join('static/menu', unique_filename)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'wb') as f:
            f.write(file.read())

        with Session() as cursor:
            new_position = Menu(
                name=name,
                ingredients=ingredients,
                description=description,
                price=int(price),
                weight=f"{weight} г",
                file_name=unique_filename,
                active=True
            )
            cursor.add(new_position)
            cursor.commit()

        flash('Позицію додано успішно!', 'success')
        return redirect(url_for('add_position'))

    return render_template('add_position.html', csrf_token=session["csrf_token"])


@app.route("/add_to_cart/<int:menu_id>")
@login_required
def add_to_cart(menu_id):
    cart = session.get("cart", {})
    cart[str(menu_id)] = cart.get(str(menu_id), 0) + 1
    session["cart"] = cart
    flash("Страву додано до кошика.")
    return redirect(url_for("home"))



@app.route("/cart")
@login_required
def cart():
    cart = session.get("cart", {})
    menu_items = []
    total_price = 0

    with Session() as db:
        for item_id, quantity in cart.items():
            item = db.query(Menu).get(int(item_id))
            if item:
                item.total = item.price * quantity
                item.quantity = quantity
                menu_items.append(item)
                total_price += item.total

    return render_template("cart.html", items=menu_items, total=total_price, csrf_token=session["csrf_token"])

@app.route("/place_order", methods=["POST"])
@login_required
def place_order():
    if request.form.get("csrf_token") != session["csrf_token"]:
        return "Запит заблоковано!", 403

    cart = session.get("cart", {})
    if not cart:
        flash("Кошик порожній.")
        return redirect(url_for("cart"))

    with Session() as db:
        new_order = Orders(
            order_list=cart,
            order_time=datetime.utcnow(),
            user_id=current_user.id
        )
        db.add(new_order)
        db.commit()

    session["cart"] = {}  # очищаємо кошик
    flash("Замовлення оформлено успішно!")
    return redirect(url_for("home"))

@app.route('/menu_check', methods=['GET', 'POST'])
@login_required
def menu_check():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.method == 'POST':
        if request.form.get("csrf_token") != session['csrf_token']:
            return "Запит заблоковано!", 403

        position_id = request.form['pos_id']
        with Session() as cursor:
            position_obj = cursor.query(Menu).filter_by(id=position_id).first()
            if 'change_status' in request.form:
                position_obj.active = not position_obj.active
            elif 'delete_position' in request.form:
                cursor.delete(position_obj)
            cursor.commit()

    with Session() as cursor:
        all_positions = cursor.query(Menu).all()

    return render_template('check_menu.html', all_positions=all_positions, csrf_token=session["csrf_token"])

@app.route('/all_users')
@login_required
def all_users():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    with Session() as cursor:
        all_users = cursor.query(Users).with_entities(Users.id, Users.nickname, Users.email).all()
    return render_template('all_users.html', all_users=all_users)

#@app.route('/change_password', methods=['GET', 'POST'])
#@login_required
def change_password():
    if request.method == 'POST':
        if request.form.get("csrf_token") != session.get("csrf_token"):
            return "Запит заблоковано!", 403

        current_pwd = request.form['current_password']
        new_pwd = request.form['new_password']

        with Session() as cursor:
            user = cursor.query(Users).filter_by(id=current_user.id).first()
            if not user or not user.check_password(current_pwd):
                flash("Неправильний поточний пароль", "danger")
                return redirect(url_for('change_password'))

            user.set_password(new_pwd)
            cursor.commit()
            flash("Пароль успішно змінено", "success")
            return redirect(url_for('home'))

    return render_template('change_password.html', csrf_token=session["csrf_token"])

@app.route("/my_orders")
@login_required
def my_orders():
    with Session() as cursor:
        orders = cursor.query(Orders).filter_by(user_id=current_user.id).order_by(Orders.order_time.desc()).all()
        menu_items = {item.id: item.name for item in cursor.query(Menu).all()}

        order_data = []
        for order in orders:
            readable_items = []
            for item_id, count in order.order_list.items():
                name = menu_items.get(int(item_id), f"Блюдо #{item_id}")
                readable_items.append(f"{name} × {count}")
            order_data.append({
                "id": order.id,
                "items": readable_items,
                "time": order.order_time.strftime("%d.%m.%Y о %H:%M")
            })

    return render_template("my_orders.html", orders=order_data)

@app.route("/my_order/<int:id>")
@login_required
def my_order(id):
    with Session() as cursor:
        us_order = cursor.query(Orders).filter_by(id=id, user_id=current_user.id).first()
        if not us_order:
            flash("Замовлення не знайдено", "danger")
            return redirect(url_for('my_orders'))

        total_price = 0
        items = []
        for item_id, count in us_order.order_list.items():
            item = cursor.query(Menu).filter_by(id=int(item_id)).first()
            if item:
                total_price += int(item.price) * int(count)
                items.append(f"{item.name} × {count}")
            else:
                items.append(f"Видалена позиція #{item_id} × {count}")

    return render_template('my_order.html', order=us_order, total_price=total_price, items=items)



@app.route("/cancel_order/<int:id>", methods=["POST"])
@login_required
def cancel_order(id):
    with Session() as cursor:
        order = cursor.query(Orders).filter_by(id=id, user_id=current_user.id).first()
        if not order:
            flash("Замовлення не знайдено або ви не маєте доступу", "danger")
            return redirect(url_for('my_orders'))

        cursor.delete(order)
        cursor.commit()
        flash("Замовлення успішно скасовано", "success")
    return redirect(url_for('my_orders'))


@app.route('/reserved', methods=['GET', 'POST'])
@login_required
def reserved():
    if request.method == "POST":
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        table_type = request.form['table_type']
        reserved_time_start = request.form['time']
        user_latitude = request.form['latitude']
        user_longitude = request.form['longitude']

        if not user_longitude or not user_latitude:
            return 'Ви не надали інформацію про своє місцезнаходження'

        user_cords = (float(user_latitude), float(user_longitude))
        distance = geodesic(MARGANETS_COORDS, user_cords).km
        if distance > KYIV_RADIUS_KM:
            return "Ви знаходитеся в зоні, недоступній для бронювання"

        with Session() as cursor:
            reserved_check = cursor.query(Reservation).filter_by(type_table=table_type).count()
            user_reserved_check = cursor.query(Reservation).filter_by(user_id=current_user.id).first()

            message = f'Бронь на {reserved_time_start} столика на {table_type} людини успішно створено!'
            if reserved_check < TABLE_NUM.get(table_type) and not user_reserved_check:
                new_reserved = Reservation(type_table=table_type, time_start=reserved_time_start, user_id=current_user.id)
                cursor.add(new_reserved)
                cursor.commit()
            elif user_reserved_check:
                message = 'Можна мати лише одну активну бронь'
            else:
                message = 'На жаль, бронь такого типу стола наразі неможлива'
            return render_template('reserved.html', message=message, csrf_token=session["csrf_token"])
    return render_template('reserved.html', csrf_token=session["csrf_token"])

@app.route('/reservations_check', methods=['GET', 'POST'])
@login_required
def reservations_check():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.method == "POST":
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        reserv_id = request.form['reserv_id']
        with Session() as cursor:
            reservation = cursor.query(Reservation).filter_by(id=reserv_id).first()
            if reservation:
                cursor.delete(reservation)
                cursor.commit()

    with Session() as cursor:
        all_reservations = cursor.query(Reservation).all()
        return render_template('reservations_check.html', all_reservations=all_reservations, csrf_token=session["csrf_token"])




if __name__ == "__main__":
    app.run(debug=True, port=80)