from flask import Flask, render_template, request, redirect, jsonify
import sqlite3
from textblob import TextBlob

app = Flask(__name__)

# -------------------------
# Create table at startup
# -------------------------
def create_table():
    conn = sqlite3.connect("/tmp/database.db")
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
            sentiment TEXT
        )
    """)
    conn.commit()
    conn.close()

create_table()


# -------------------------
# Database connection
# -------------------------
def get_db_connection():
    conn = sqlite3.connect("/tmp/database.db")
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------
# Auto Department Assignment
# -------------------------
def assign_department(description):
    text = description.lower()

    if "water" in text or "leak" in text or "pipe" in text:
        return "Water Department"
    elif "road" in text or "pothole" in text:
        return "Roads Department"
    elif "garbage" in text or "waste" in text:
        return "Sanitation Department"
    elif "electricity" in text or "current" in text:
        return "Electricity Department"
    else:
        return "General Department"


# -------------------------
# ML FUNCTIONS
# -------------------------
def calculate_priority(description):
    text = description.lower()
    blob = TextBlob(description)

    polarity = blob.sentiment.polarity

    if polarity < -0.2:
        return "High"
    elif "water" in text or "electricity" in text or "leak" in text:
        return "Medium"
    else:
        return "Low"


def predict_resolution_time(priority):
    if priority == "High":
        return "1-2 days"
    elif priority == "Medium":
        return "2-4 days"
    else:
        return "5-7 days"


def get_sentiment(description):
    blob = TextBlob(description)
    polarity = blob.sentiment.polarity

    if polarity < 0:
        return "Negative"
    elif polarity == 0:
        return "Neutral"
    else:
        return "Positive"


# -------------------------
# Home Page
# -------------------------
@app.route('/')
def home():
    return render_template("index.html")


# -------------------------
# Submit Complaint (WEB)
# -------------------------
@app.route('/submit', methods=['POST'])
def submit_complaint():
    title = request.form['title']
    name = request.form['name']
    email = request.form['email']
    category = request.form['category']
    description = request.form['description']

    department = assign_department(description)
    priority = calculate_priority(description)
    resolution_time = predict_resolution_time(priority)
    sentiment = get_sentiment(description)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO complaints 
        (title, name, email, category, description, status, department, priority, resolution_time, sentiment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title, name, email, category, description,
        "Pending", department, priority, resolution_time, sentiment
    ))

    conn.commit()
    conn.close()

    return redirect('/')


# -------------------------
# Admin Dashboard
# -------------------------
@app.route('/admin')
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints")
    complaints = cursor.fetchall()

    conn.close()

    return render_template("admin.html", complaints=complaints)


# -------------------------
# Update Status
# -------------------------
@app.route('/update_status/<int:id>', methods=['POST'])
def update_status(id):
    new_status = request.form['status']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE complaints SET status = ? WHERE id = ?",
        (new_status, id)
    )

    conn.commit()
    conn.close()

    return redirect('/admin')


# -------------------------
# API: Submit Complaint
# -------------------------
@app.route('/api/submit', methods=['POST'])
def api_submit():
    data = request.get_json()

    title = data.get('title')
    name = data.get('name')
    email = data.get('email')
    category = data.get('category')
    description = data.get('description')

    department = assign_department(description)
    priority = calculate_priority(description)
    resolution_time = predict_resolution_time(priority)
    sentiment = get_sentiment(description)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO complaints 
        (title, name, email, category, description, status, department, priority, resolution_time, sentiment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title, name, email, category, description,
        "Pending", department, priority, resolution_time, sentiment
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


# -------------------------
# API: Get Complaints
# -------------------------
@app.route('/api/complaints', methods=['GET'])
def get_complaints():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints")
    complaints = cursor.fetchall()

    conn.close()

    result = []
    for row in complaints:
        result.append({
            "id": row["id"],
            "title": row["title"],
            "name": row["name"],
            "email": row["email"],
            "category": row["category"],
            "description": row["description"],
            "status": row["status"],
            "department": row["department"],
            "priority": row["priority"],
            "resolution_time": row["resolution_time"],
            "sentiment": row["sentiment"]
        })

    return jsonify(result)


# -------------------------
# Run App
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)