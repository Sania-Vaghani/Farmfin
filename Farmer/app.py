from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, abort, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
import os
from dotenv import load_dotenv
import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime
import asyncio
import python_weather

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/farmer_credit_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None  # No time limit for CSRF tokens
app.config['WTF_CSRF_CHECK_DEFAULT'] = True  # Enable CSRF protection by default
app.config['WTF_CSRF_SSL_STRICT'] = False  # Disable SSL-only for development
app.config['WTF_CSRF_ENABLED'] = True  # Explicitly enable CSRF protection

# Initialize extensions
db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# Remove custom CSRF handling as we'll use Flask-WTF's built-in protection
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)  # Changed to store plain password
    user_type = db.Column(db.String(20))  # 'farmer' or 'bank'

class FarmData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    location = db.Column(db.String(200))
    land_size = db.Column(db.Float)
    soil_type = db.Column(db.String(50))
    crop_type = db.Column(db.String(50))
    last_yield = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CreditScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer)
    weather_factor = db.Column(db.Float)
    soil_factor = db.Column(db.Float)
    yield_factor = db.Column(db.Float)
    financial_factor = db.Column(db.Float)
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        user_type = request.form.get('user_type')

        if not all([username, email, password, user_type]):
            flash('All fields are required', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))

        user = User(
            username=username,
            email=email,
            password=password,
            user_type=user_type
        )
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please provide both username and password', 'error')
            return redirect(url_for('login'))

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            login_user(user)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page if next_page else url_for('dashboard'))

        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.user_type == 'farmer':
        farm_data = FarmData.query.filter_by(user_id=current_user.id).first()
        credit_score = CreditScore.query.filter_by(user_id=current_user.id).order_by(CreditScore.calculated_at.desc()).first()
        return render_template('farmer_dashboard.html', farm_data=farm_data, credit_score=credit_score)
    else:
        # For bank users, fetch all farmers with their farm data and latest credit scores
        farmers = User.query.filter_by(user_type='farmer').all()
        
        # Create a dictionary to store farmer data
        farmer_data = {}
        
        for farmer in farmers:
            farm_data = FarmData.query.filter_by(user_id=farmer.id).first()
            credit_score = CreditScore.query.filter_by(user_id=farmer.id).order_by(CreditScore.calculated_at.desc()).first()
            
            farmer_data[farmer.id] = {
                'user': farmer,
                'farm_data': farm_data,
                'credit_score': credit_score
            }
        
        return render_template('bank_dashboard.html', farmer_data=farmer_data)

@app.route('/submit-farm-data', methods=['POST'])
@login_required
def submit_farm_data():
    if current_user.user_type != 'farmer':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        data = request.form
        if not all(key in data for key in ['location', 'land_size', 'soil_type', 'crop_type', 'last_yield']):
            return jsonify({'error': 'Missing required fields'}), 400

        # Validate numeric values before creating the object
        try:
            land_size = float(data.get('land_size'))
            last_yield = float(data.get('last_yield'))
            
            if land_size <= 0:
                return jsonify({'error': 'Land size must be greater than 0'}), 400
            if last_yield < 0:
                return jsonify({'error': 'Last yield cannot be negative'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid numeric values provided'}), 400

        farm_data = FarmData(
            user_id=current_user.id,
            location=data.get('location'),
            land_size=land_size,
            soil_type=data.get('soil_type'),
            crop_type=data.get('crop_type'),
            last_yield=last_yield
        )
        
        # Check if user already has farm data
        existing_farm_data = FarmData.query.filter_by(user_id=current_user.id).first()
        if existing_farm_data:
            # Update existing record
            existing_farm_data.location = farm_data.location
            existing_farm_data.land_size = farm_data.land_size
            existing_farm_data.soil_type = farm_data.soil_type
            existing_farm_data.crop_type = farm_data.crop_type
            existing_farm_data.last_yield = farm_data.last_yield
        else:
            # Add new record
            db.session.add(farm_data)
        
        db.session.commit()

        # Trigger credit score calculation
        score = calculate_credit_score(current_user.id)
        if score is None:
            return jsonify({'warning': 'Farm data saved, but credit score calculation failed. Please try again later.'}), 200
        
        return jsonify({'message': 'Farm data submitted successfully'}), 200

    except Exception as e:
        print(f"Error in submit_farm_data: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500

async def get_weather_data(location):
    try:
        async with python_weather.Client() as client:
            weather = await client.get(location)
            return {
                'temperature': weather.current.temperature,
                'humidity': weather.current.humidity,
                'description': weather.current.description
            }
    except Exception as e:
        print(f"Error fetching weather data: {str(e)}")
        return {
            'temperature': 25,  # Default optimal temperature
            'humidity': 60,     # Default humidity
            'description': 'Not available'
        }

def calculate_credit_score(user_id):
    try:
        farm_data = FarmData.query.filter_by(user_id=user_id).first()
        if not farm_data:
            return None

        # Get weather data
        weather_data = asyncio.run(get_weather_data(farm_data.location))
        
        # Calculate factors
        weather_factor = calculate_weather_factor(weather_data)
        soil_factor = calculate_soil_factor(farm_data.soil_type)
        yield_factor = calculate_yield_factor(farm_data.last_yield, farm_data.crop_type)
        financial_factor = calculate_financial_factor(farm_data.land_size)

        # Calculate final score (0-1000)
        final_score = int((weather_factor + soil_factor + yield_factor + financial_factor) / 4 * 1000)

        credit_score = CreditScore(
            user_id=user_id,
            score=final_score,
            weather_factor=weather_factor,
            soil_factor=soil_factor,
            yield_factor=yield_factor,
            financial_factor=financial_factor
        )
        db.session.add(credit_score)
        db.session.commit()

        return final_score
    except Exception as e:
        print(f"Error calculating credit score: {str(e)}")
        db.session.rollback()
        return None

def calculate_weather_factor(weather_data):
    # Simplified weather factor calculation
    optimal_temp = 25  # Celsius
    temp_diff = abs(weather_data['temperature'] - optimal_temp)
    weather_factor = max(0, 1 - (temp_diff / 50))
    return weather_factor

def calculate_soil_factor(soil_type):
    soil_ratings = {
        'loam': 1.0,
        'clay': 0.8,
        'sandy': 0.7,
        'silt': 0.9
    }
    return soil_ratings.get(soil_type.lower(), 0.5)

def calculate_yield_factor(last_yield, crop_type):
    # Simplified yield factor calculation
    crop_benchmarks = {
        'wheat': 3.0,
        'rice': 4.0,
        'corn': 5.0,
        'soybean': 2.5
    }
    benchmark = crop_benchmarks.get(crop_type.lower(), 3.0)
    return min(1.0, last_yield / benchmark)

def calculate_financial_factor(land_size):
    # Simplified financial factor calculation based on land size
    if land_size <= 0:
        return 0
    return min(1.0, land_size / 10)  # Assuming 10 hectares is optimal

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 