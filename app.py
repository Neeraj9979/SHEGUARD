from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, jsonify
)

from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from functools import wraps
from dotenv import load_dotenv

from database import get_db, create_tables
from model import predict_risk
from sms_service import send_emergency_sms

import os

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or os.urandom(32).hex()
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv("COOKIE_SECURE", "false").lower() == "true"
)

csrf = CSRFProtect(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)


def login_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return func(*args, **kwargs)

    return wrapper


def current_user_id():
    return session["user_id"]


@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        phone = request.form["phone"].strip()
        password = request.form["password"]

        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return redirect(url_for("register"))

        if not name or not email or not phone:
            flash("All fields are required.")
            return redirect(url_for("register"))

        hashed = generate_password_hash(password)

        sms_enabled = request.form.get("sms_enabled") == "yes"

        con = get_db()
        cur = con.cursor()

        try:

            cur.execute("""
                INSERT INTO users
                (name, email, password, phone, sms_enabled)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                name, email, hashed, phone, sms_enabled
            ))

            con.commit()

            flash("Registration successful!")

            return redirect(url_for("login"))

        except Exception:

            con.rollback()

            flash("Registration failed. Check whether email already exists.")

        finally:

            cur.close()
            con.close()

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        con = get_db()
        cur = con.cursor()

        cur.execute("""
            SELECT user_id, name, password
            FROM users
            WHERE email = %s
        """, (email,))

        user = cur.fetchone()

        cur.close()
        con.close()

        if user and check_password_hash(user[2], password):

            session.clear()

            session["user_id"] = user[0]
            session["name"] = user[1]

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
@login_required
def dashboard():

    con = get_db()
    cur = con.cursor()

    user_id = current_user_id()

    cur.execute("""
        SELECT COUNT(*) FROM sos_alerts
        WHERE user_id = %s
    """, (user_id,))

    alert_count = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM emergency_contacts
        WHERE user_id = %s
    """, (user_id,))

    contact_count = cur.fetchone()[0]

    cur.execute("""
        SELECT risk_level, risk_score
        FROM risk_analysis
        WHERE user_id = %s
        ORDER BY analysis_time DESC
        LIMIT 1
    """, (user_id,))

    latest_risk = cur.fetchone()

    cur.execute("""
        SELECT sms_enabled, tracking_enabled
        FROM users WHERE user_id = %s
    """, (user_id,))

    settings = cur.fetchone()

    cur.execute("""
        SELECT latitude, longitude, recorded_at
        FROM location_history
        WHERE user_id = %s
        ORDER BY recorded_at DESC
        LIMIT 1
    """, (user_id,))

    latest_location = cur.fetchone()

    cur.close()
    con.close()

    return render_template(
        "dashboard.html",
        name=session["name"],
        alert_count=alert_count,
        contact_count=contact_count,
        latest_risk=latest_risk,
        sms_enabled=settings[0],
        tracking_enabled=settings[1],
        latest_location=latest_location
    )


# ---------------- CONTACTS ----------------

@app.route("/contacts", methods=["GET", "POST"])
@login_required
def contacts():

    con = get_db()
    cur = con.cursor()

    if request.method == "POST":

        name = request.form["contact_name"].strip()
        phone = request.form["phone"].strip()

        if not name or not phone:
            flash("Enter contact name and phone number.")
        else:

            cur.execute("""
                INSERT INTO emergency_contacts
                (user_id, contact_name, phone)
                VALUES (%s, %s, %s)
            """, (
                current_user_id(), name, phone
            ))

            con.commit()

            flash("Contact added successfully.")

    cur.execute("""
        SELECT contact_id, contact_name, phone
        FROM emergency_contacts
        WHERE user_id = %s
        ORDER BY contact_id DESC
    """, (current_user_id(),))

    all_contacts = cur.fetchall()

    cur.close()
    con.close()

    return render_template(
        "contacts.html",
        contacts=all_contacts
    )


@app.route("/delete_contact/<int:contact_id>", methods=["POST"])
@login_required
def delete_contact(contact_id):

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        DELETE FROM emergency_contacts
        WHERE contact_id = %s AND user_id = %s
    """, (contact_id, current_user_id()))

    con.commit()

    cur.close()
    con.close()

    flash("Contact deleted.")

    return redirect(url_for("contacts"))


# ---------------- SMS SETTINGS ----------------

@app.route("/sms-settings", methods=["POST"])
@login_required
def sms_settings():

    enabled = request.form.get("sms_enabled") == "yes"

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET sms_enabled = %s
        WHERE user_id = %s
    """, (enabled, current_user_id()))

    con.commit()
    cur.close()
    con.close()

    flash("SMS preferences updated.")

    return redirect(url_for("dashboard"))


# ---------------- SOS ALERT ----------------

@app.route("/sos", methods=["POST"])
@login_required
@limiter.limit("3 per minute")
def sos():

    data = request.get_json(silent=True) or {}

    try:

        lat = float(data.get("latitude"))
        lon = float(data.get("longitude"))

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError()

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "Valid GPS coordinates are required."
        }), 400

    user_id = current_user_id()

    con = get_db()
    cur = con.cursor()

    try:

        cur.execute("""
            INSERT INTO sos_alerts
            (user_id, latitude, longitude)
            VALUES (%s, %s, %s)
            RETURNING alert_id
        """, (user_id, lat, lon))

        alert_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO location_history
            (user_id, latitude, longitude)
            VALUES (%s, %s, %s)
        """, (user_id, lat, lon))

        cur.execute("""
            SELECT name, sms_enabled
            FROM users WHERE user_id = %s
        """, (user_id,))

        user = cur.fetchone()

        cur.execute("""
            SELECT contact_id, contact_name, phone
            FROM emergency_contacts
            WHERE user_id = %s
        """, (user_id,))

        contacts = cur.fetchall()

        con.commit()

    except Exception:

        con.rollback()
        cur.close()
        con.close()
        raise

    sms_results = []

    if user[1]:

        message = (
            f"EMERGENCY ALERT from {user[0]}. "
            f"They may need assistance. "
            f"Last reported location: "
            f"https://www.openstreetmap.org/"
            f"?mlat={lat}&mlon={lon}"
        )

        for contact in contacts:

            result = send_emergency_sms(
                contact[2],
                message
            )

            sms_results.append(result["success"])

            cur.execute("""
                INSERT INTO sms_logs
                (user_id, contact_id, alert_id,
                 phone, message_sid, status, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                contact[0],
                alert_id,
                contact[2],
                result["sid"],
                "SUBMITTED" if result["success"] else "FAILED",
                result["error"]
            ))

        con.commit()

    cur.close()
    con.close()

    return jsonify({
        "success": True,
        "alert_id": alert_id,
        "sms_enabled": bool(user[1]),
        "sms_submitted": sum(sms_results),
        "sms_failed": len(sms_results) - sum(sms_results),
        "message": "SOS alert saved."
    })


# ---------------- TRACKING SETTINGS ----------------

@app.route("/tracking-settings", methods=["POST"])
@login_required
def tracking_settings():

    data = request.get_json(silent=True) or {}

    enabled = data.get("enabled")

    if not isinstance(enabled, bool):

        return jsonify({
            "success": False,
            "message": "Invalid tracking setting."
        }), 400

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET tracking_enabled = %s
        WHERE user_id = %s
    """, (enabled, current_user_id()))

    con.commit()

    cur.close()
    con.close()

    return jsonify({
        "success": True,
        "tracking_enabled": enabled
    })


# ---------------- LIVE LOCATION UPDATE ----------------

@app.route("/update-location", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def update_location():

    data = request.get_json(silent=True) or {}

    try:

        lat = float(data.get("latitude"))
        lon = float(data.get("longitude"))

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError()

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "Invalid GPS coordinates."
        }), 400

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        SELECT tracking_enabled
        FROM users
        WHERE user_id = %s
    """, (current_user_id(),))

    user = cur.fetchone()

    if not user or not user[0]:

        cur.close()
        con.close()

        return jsonify({
            "success": False,
            "message": "Tracking is disabled."
        }), 403

    cur.execute("""
        INSERT INTO location_history
        (user_id, latitude, longitude)
        VALUES (%s, %s, %s)
    """, (current_user_id(), lat, lon))

    con.commit()

    cur.close()
    con.close()

    return jsonify({
        "success": True,
        "message": "Location updated."
    })


# ---------------- ML RISK PREDICTION ----------------

@app.route("/risk", methods=["POST"])
@login_required
def risk():

    followed = request.form.get("followed") == "yes"
    isolated = request.form.get("isolated") == "yes"
    threat = request.form.get("threat") == "yes"
    unsafe = request.form.get("unsafe") == "yes"

    level, score = predict_risk(
        followed,
        isolated,
        threat,
        unsafe
    )

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO risk_analysis
        (user_id, risk_level, risk_score)
        VALUES (%s, %s, %s)
    """, (current_user_id(), level, score))

    con.commit()

    cur.close()
    con.close()

    flash(f"Risk assessment completed: {level}")

    return redirect(url_for("dashboard"))


# ---------------- LOGOUT ----------------

@app.route("/logout", methods=["POST"])
@login_required
def logout():

    session.clear()

    return redirect(url_for("login"))


if __name__ == "__main__":

    create_tables()

    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
