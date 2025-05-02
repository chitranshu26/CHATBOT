from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
import sqlite3
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from travel_fares import travel_fares

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
    conn.commit()
    conn.close()

init_db()

# Email sending function
def send_email(to, origin, destination, date, order_id):
    try:
        sender_email = "waymate01@gmail.com"
        app_password = "kadpuvhqfyypfaua"

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
            <p><strong>Order ID:</strong> {order_id}</p>
            <p>Thank you for booking with us!</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, to, msg.as_string())

        print(f"✅ Email sent to {to}")
    except Exception as e:
        print(f"❌ Email sending failed: {e}")

# Fare finder logic
def find_fare(origin, destination, mode, travel_class):
    for state in travel_fares.values():
        for from_city, destinations in state.items():
            if from_city.lower() == origin.lower():
                for to_city, modes in destinations.items():
                    if to_city.lower() == destination.lower():
                        try:
                            return modes[mode.lower()][travel_class]
                        except KeyError:
                            return None
    return None

# Flask routes
@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message')
    response = ""

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
        response = "👋 Hello! Let's book your ticket. Where are you traveling from?"
        session['step'] = 'from'
    elif step == 'from':
        session['from'] = user_msg
        response = "Great! Where are you traveling to? (e.g., Madurai)"
        session['step'] = 'to'
    elif step == 'to':
        session['to'] = user_msg
        response = "When are you planning to travel? (YYYY-MM-DD)"
        session['step'] = 'date'
    elif step == 'date':
        session['date'] = user_msg
        response = "Which mode do you want to travel by? (train, bus, flight)"
        session['step'] = 'mode'
    elif step == 'mode':
        session['mode'] = user_msg.lower()
        response = "Please choose class type (e.g., Sleeper, 3AC, Economy, Business):"
        session['step'] = 'class'
    elif step == 'class':
        session['class'] = user_msg
        response = "Please provide your email address."
        session['step'] = 'email'
    elif step == 'email':
        session['email'] = user_msg
        fare = find_fare(session['from'], session['to'], session['mode'], session['class'])
        fare_text = f"Fare: ₹{fare}" if fare is not None else "Fare: ₹Not found"
        response = (
            f"You are booking a {session['mode']} ticket ({session['class']}) from {session['from']} to {session['to']} "
            f"on {session['date']} {fare_text}. Confirmation will be sent to {session['email']}. Confirm? (yes/no)"
        )
        session['fare'] = fare
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

            send_email(session['email'], session['from'], session['to'], session['date'], mock_order_id)

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
