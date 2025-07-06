Online Restaurant (Educational Project)
This is an educational web application for an Asian food restaurant built using Flask. The project demonstrates the full cycle of menu management: user registration and login, viewing dishes, adding new menu items (available only to the administrator), and displaying item images.



Technologies Used
• Python 3
• Flask
• SQLAlchemy
• PostgreSQL
• Flask-Login
• HTML/CSS
• Jinja2

Features
• User registration and authentication
• CSRF protection for forms
• Viewing available menu items with images
• Admin panel for adding new dishes (accessible only for user with nickname Admin)
• Image uploads for dishes to the static/menu/ directory
• Basic input validation



How to Run
1. Clone the repository:
git clone https://github.com/your-username/online-restaurant.git
cd online-restaurant

2. Create and activate a virtual environment:
python -m venv .venv
.venv\Scripts\activate   (on Windows)
source .venv/bin/activate   (on Linux/macOS)

3. Install dependencies:
pip install -r requirements.txt

4. Create a PostgreSQL database:
CREATE DATABASE online_restaurant;

5. Configure the connection string in online_restaurant_db.py:
engine = create_engine("postgresql+psycopg2://username:password@localhost:5432/online_restaurant")

6. Generate the database tables:
python online_restaurant_db.py

7. Run the Flask app:
python online_restaurant.py



Admin Access
To access the admin panel (/add_position), create an account with the nickname Admin during registration. Only this user can add new menu items.


Project Structure
online-restaurant/
├── static/
│   ├── menu/                # dish images
│   └── css/style.css        # styling
├── templates/
│   ├── home.html
│   ├── login.html
│   ├── register.html
│   ├── add_position.html
│   └── base.html
├── online_restaurant.py     # main Flask app
├── online_restaurant_db.py  # SQLAlchemy models
├── requirements.txt
└── README.md


Notes:
This is an educational project. For production use, it is recommended to implement:
1. Role-based access control
2. File validation and XSS protection
3. ORM migrations (e.g., Alembic)
4. Responsive design for mobile support
