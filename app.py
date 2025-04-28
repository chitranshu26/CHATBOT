from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
import sqlite3
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

DB_PATH = "bookings.db"

# Initialize the database
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        origin TEXT,
        destination TEXT,
        date TEXT,
        created_at TEXT,
        order_id TEXT
    )''')
    # Add order_id column if not exists
    c.execute("PRAGMA table_info(bookings)")
    columns = [col[1] for col in c.fetchall()]
    if "order_id" not in columns:
        c.execute("ALTER TABLE bookings ADD COLUMN order_id TEXT")
    conn.commit()
    conn.close()

init_db()

# Email sending function
def send_email(to, origin, destination, date):
    try:
        sender_email = "waymate01@gmail.com"  # Your Gmail email
        app_password = "kadpuvhqfyypfaua"  # Your generated app password

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your Ticket Confirmation"
        msg["From"] = sender_email
        msg["To"] = to

        html_content = f"""
        <html>
        <body>
            <h2>🎫 Travel Ticket Confirmation</h2>
            <p><strong>From:</strong> {origin}</p>
            <p><strong>To:</strong> {destination}</p>
            <p><strong>Date:</strong> {date}</p>
            <p>Thank you for booking with us!</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)  # Log in with the correct email and app password
            server.sendmail(sender_email, to, msg.as_string())

        print(f"✅ Email sent to {to}")
    except Exception as e:
        print(f"❌ Email sending failed: {e}")

# Flask routes
@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message')
    response = ""

    # Handle order checking
    if user_msg.lower().startswith("check order"):
        try:
            order_id = user_msg.split(" ")[-1].strip()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT user, origin, destination, date, created_at FROM bookings WHERE order_id = ?", (order_id,))
            data = c.fetchone()
            conn.close()
            if data:
                response = (
                    f"🎫 Ticket Details for Order ID `{order_id}`:\n"
                    f"👤 Email: {data[0]}\n"
                    f"🧳 From: {data[1]}\n"
                    f"📍 To: {data[2]}\n"
                    f"📅 Date: {data[3]}\n"
                    f"🕓 Booked on: {data[4]}"
                )
            else:
                response = "⚠️ No ticket found for that Order ID."
        except Exception as e:
            response = "⚠️ Could not process the order ID. Please try again."
        return jsonify({"reply": response})

    step = session.get('step', 'start')

    if step == 'start':
        response = "Welcome to TravelBot! Where are you traveling from?"
        session['step'] = 'from'
    elif step == 'from':
        session['from'] = user_msg
        response = "Great! Where are you traveling to?"
        session['step'] = 'to'
    elif step == 'to':
        session['to'] = user_msg
        response = "When are you planning to travel? (YYYY-MM-DD)"
        session['step'] = 'date'
    elif step == 'date':
        session['date'] = user_msg
        response = "Please provide your email address."
        session['step'] = 'email'
    elif step == 'email':
        session['email'] = user_msg
        response = (f"You are booking a ticket from {session['from']} to {session['to']} on {session['date']}\n"
                    f"We will send confirmation to {session['email']}.\nConfirm? (yes/no)")
        session['step'] = 'confirm'
    elif step == 'confirm':
        if user_msg.lower() == "yes":
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            mock_order_id = f"RAZORPAY_MOCK_{int(datetime.now().timestamp())}"
            session['order_id'] = mock_order_id
            c.execute("INSERT INTO bookings (user, origin, destination, date, created_at, order_id) VALUES (?, ?, ?, ?, ?, ?)",
                      (session['email'], session['from'], session['to'], session['date'], datetime.now().isoformat(), mock_order_id))
            conn.commit()
            conn.close()

            send_email(session['email'], session['from'], session['to'], session['date'])

            response = (
                f"✅ Booking confirmed and email sent!\n"
                f"🆔 Order ID: {mock_order_id}\n"
                "💳 [Click here to pay](<a href='/external-payment' target='_blank'>Razorpay</a>)\n\n"
                "✈️ Want to book another ticket? Just type **hi**!\n"
                "📄 Want to check ticket? Type: **check order ORDER_ID**"
            )
            session['step'] = 'done'
        else:
            response = "❌ Booking cancelled. Type **hi** to start over."
            session['step'] = 'start'
    elif step == 'done':
        response = "👋 Let's book your next ticket! Where are you traveling from?"
        session['step'] = 'from'

    return jsonify({"reply": response})

if __name__ == '__main__':
    app.run(debug=True)
