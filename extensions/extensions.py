from flask import Flask, request, jsonify
import pymysql
import os
from dotenv import load_dotenv
from flask_mail import Mail, Message
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)

CORS(app, origins="*")

def get_db_connection():
    try:
        print("Trying to connect to MYSQL database")
        connection = pymysql.connect(
            host= "148.113.201.195",
            user= "admin",
            password="Pityboy@22",
            database=os.getenv("DB_NAME", "watchup"),
            port=int(os.getenv("DB_PORT", 3306)),
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        print(f"Database connection failed: {str(e)}")
        return None

# ✅ Flask-Mail configuration
app.config['MAIL_SERVER'] = os.getenv("SMTP_HOST")
app.config['MAIL_PORT'] = int(os.getenv("SMTP_PORT", 587))
app.config['MAIL_USE_TLS'] = os.getenv("SMTP_SECURE", "false").lower() != "true"
app.config['MAIL_USE_SSL'] = os.getenv("SMTP_SECURE", "false").lower() == "true"
app.config['MAIL_USERNAME'] = os.getenv("SMTP_USER")
app.config['MAIL_PASSWORD'] = os.getenv("SMTP_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = ("RippleBids", os.getenv("SMTP_FROM", os.getenv("SMTP_USER")))

# Initialize Flask-Mail
mail = Mail(app)

