from flask import Flask, render_template, request, redirect, jsonify
import sqlite3
from textblob import TextBlob
import os
import nltk
nltk.download('punkt')
import datetime
from googletrans import Translator
translator = Translator()

app = Flask(__name__)

DB_PATH = "/tmp/database.db"   # Render-safe DB

# -------------------------
# Create table
# -------------------------
def create_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            name TEXT,
            email TEXT,
            category TEXT,
            description TEXT,
            status TEXT DEFAULT 'Pending',
            department TEXT,
            priority TEXT,
            resolution_time TEXT,
            sentiment TEXT,
            date TEXT,
            image TEXT,
            rating INTEGER,
            feedback TEXT
        )
    """)

    conn.commit()
    conn.close()

create_table()

# -------------------------
# DB connection
# -------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------
# Department Logic
# -------------------------
def assign_department(description):
    text = description.lower()

    mapping = {
        "Water Department": ["water", "leak", "pipe"],
        "Electricity Department": ["electricity", "power"],
        "Roads Department": ["road", "pothole"],
        "Sanitation Department": ["garbage", "waste"],
    }

    for dept, keywords in mapping.items():
        if any(word in text for word in keywords):
            return dept

    return "General Department"


# -------------------------
# ML FUNCTIONS
# -------------------------
def calculate_priority(description):
    text = description.lower()
    blob = TextBlob(description)
    polarity = blob.sentiment.polarity

    score = 0

    if polarity < -0.5:
        score += 3
    elif polarity < -0.2:
        score += 2

    if any(word in text for word in ["urgent", "danger", "accident", "fire"]):
        score += 3

    if any(word in text for word in ["water", "electricity", "leak"]):
        score += 2

    if score >= 5:
        return "High"
    elif score >= 3:
        return "Medium"
    else:
        return "Low"

def predict_resolution_time(priority):
    return {
        "High": "1-2 days",
        "Medium": "2-4 days",
        "Low": "5-7 days"
    }.get(priority, "3-5 days")


def get_sentiment(description):
    blob = TextBlob(description)
    polarity = blob.sentiment.polarity

    if polarity < 0:
        return "Negative"
    elif polarity == 0:
        return "Neutral"
    else:
        return "Positive"
    
def is_duplicate(description):
    conn = get_db_connection()
    rows = conn.execute("SELECT description FROM complaints").fetchall()
    conn.close()

    for row in rows:
        if description.lower() in row["description"].lower():
            return True

    return False

def is_fraud(description):
    text = description.lower()

    if len(text) < 10:
        return True

    spam_words = ["test", "fake", "asdf"]

    if any(word in text for word in spam_words):
        return True

    return False




# -------------------------
# ROUTES
# -------------------------

@app.route('/')
def home():
    return render_template("index.html")


@app.route('/submit_page')
def submit_page():
    return render_template("submit.html")


@app.route('/admin')
def admin_dashboard():
    conn = get_db_connection()
    complaints = conn.execute("SELECT * FROM complaints ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin.html", complaints=complaints)

@app.route('/track')
def track():
    return render_template("track.html")




# -------------------------
# FORM SUBMIT (WEB)
# -------------------------
@app.route('/submit', methods=['POST'])
def submit_complaint():
    try:
        title = request.form['title']
        name = request.form['name']
        email = request.form['email']
        category = request.form['category']
        description = request.form['description']

        image = request.files.get('image')
        image_filename = ""

        if image and image.filename != "":
                image_filename = image.filename
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        description = translate_to_english(description)
        department = assign_department(description)
        priority = calculate_priority(description)
        resolution_time = predict_resolution_time(priority)
        sentiment = get_sentiment(description)
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        if is_duplicate(description):
            return "Duplicate complaint detected!"
        
        if is_fraud(description):
            return "Fraud or invalid complaint!"

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO complaints 
            (title, name, email, category, description, status, department, priority, resolution_time, sentiment, date, image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, name, email, category, description,
            "Pending", department, priority, resolution_time, sentiment, date, image_filename
        ))

        conn.commit()
        conn.close()

        return redirect('/admin')

    except Exception as e:
        return f"Error: {str(e)}"


# -------------------------
# UPDATE STATUS
# -------------------------
@app.route('/update_status/<int:id>', methods=['POST'])
def update_status(id):
    new_status = request.form['status']

    conn = get_db_connection()
    conn.execute(
        "UPDATE complaints SET status = ? WHERE id = ?",
        (new_status, id)
    )
    conn.commit()
    conn.close()

    return redirect('/admin')


# -------------------------
# API ROUTES
# -------------------------

@app.route('/api/submit', methods=['POST'])
def api_submit():
    try:
        data = request.get_json()

        description = data.get('description', '')

        department = assign_department(description)
        priority = calculate_priority(description)
        resolution_time = predict_resolution_time(priority)
        sentiment = get_sentiment(description)

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO complaints 
            (title, name, email, category, description, status, department, priority, resolution_time, sentiment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('title'),
            data.get('name'),
            data.get('email'),
            data.get('category'),
            description,
            "Pending",
            department,
            priority,
            resolution_time,
            sentiment
        ))

        conn.commit()
        conn.close()

        return jsonify({
            "message": "Complaint submitted successfully",
            "department": department,
            "priority": priority,
            "resolution_time": resolution_time,
            "sentiment": sentiment
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/complaints')
def get_complaints():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM complaints ORDER BY id DESC").fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])



def translate_to_english(text):
    try:
        translated = translator.translate(text, dest='en')
        return translated.text
    except:
        return text

@app.route('/feedback/<int:id>', methods=['GET', 'POST'])
def user_feedback(id):

    if request.method == 'POST':
        rating = request.form['rating']
        feedback = request.form['feedback']

        conn = get_db_connection()
        conn.execute(
            "UPDATE complaints SET rating=?, feedback=? WHERE id=?",
            (rating, feedback, id)
        )
        conn.commit()
        conn.close()

        return "Thank you for your feedback!"

    return render_template("feedback.html")


#image folder

UPLOAD_FOLDER = "/tmp/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# -------------------------
# RUN (LOCAL ONLY)
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)