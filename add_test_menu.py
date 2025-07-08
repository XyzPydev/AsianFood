from online_restaurant_db import Session, Menu

# Додати страву в бд
with Session() as session:
    if not session.query(Menu).filter_by(name="Sushi").first():
        new_item = Menu(
            name="Sushi",
            weight="250 г",
            ingredients="рис, норі, лосось, сир філадельфія",
            description="Класичні суші з лососем та сиром",
            price=120,
            active=True,
            file_name="sushi.jpg"
        )
        session.add(new_item)
        session.commit()
        print("Страва 'Sushi' додана")
    else:
        print("Страва 'Sushi' вже існує")
