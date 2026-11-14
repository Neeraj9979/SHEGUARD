import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()


def get_db():

    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )


def create_tables():

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            phone VARCHAR(20),
            sms_enabled BOOLEAN DEFAULT FALSE,
            tracking_enabled BOOLEAN DEFAULT FALSE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            contact_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id)
                ON DELETE CASCADE,
            contact_name VARCHAR(100) NOT NULL,
            phone VARCHAR(20) NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sos_alerts (
            alert_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id)
                ON DELETE CASCADE,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            alert_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(30) DEFAULT 'ACTIVE'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS location_history (
            location_id BIGSERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id)
                ON DELETE CASCADE,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_location_user_time
        ON location_history(user_id, recorded_at DESC)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS risk_analysis (
            analysis_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id)
                ON DELETE CASCADE,
            risk_level VARCHAR(30),
            risk_score FLOAT,
            analysis_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sms_logs (
            sms_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id)
                ON DELETE CASCADE,
            contact_id INTEGER REFERENCES emergency_contacts(contact_id)
                ON DELETE SET NULL,
            alert_id INTEGER REFERENCES sos_alerts(alert_id)
                ON DELETE SET NULL,
            phone VARCHAR(20),
            message_sid VARCHAR(100),
            status VARCHAR(50),
            error_message TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Upgrade existing databases created using the earlier version.
    cur.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS sms_enabled
        BOOLEAN DEFAULT FALSE
    """)

    cur.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS tracking_enabled
        BOOLEAN DEFAULT FALSE
    """)

    con.commit()

    cur.close()
    con.close()

    print("All database tables created successfully!")