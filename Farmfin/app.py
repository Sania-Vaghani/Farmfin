from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import mysql.connector
import os
from datetime import datetime
import requests
from geopy.geocoders import Nominatim
import json
from sqlalchemy import text

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/agri_loan_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
# Database Models
class BankEmployee(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(100))
    bank_name = db.Column(db.String(50), nullable=False)
    branch = db.Column(db.String(100))
    role = db.Column(db.String(20), default='bank_employee')

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'farmer'
    aadhar = db.Column(db.String(12), unique=True)
    mobile = db.Column(db.String(10))
    name = db.Column(db.String(100))

class Bank(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    schemes = db.relationship('LoanScheme', backref='bank', lazy=True)

class LoanScheme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    min_amount = db.Column(db.Float)
    max_amount = db.Column(db.Float)
    interest_rate = db.Column(db.Float)
    tenure_months = db.Column(db.Integer)
    processing_fee = db.Column(db.Float)

class Saatbaar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    form_number = db.Column(db.String(20), unique=True, nullable=False)
    location = db.Column(db.String(200))
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    land_area = db.Column(db.Float)
    encumbrances = db.Column(db.String(200))
    litigation_status = db.Column(db.String(50))
    irrigation_source = db.Column(db.String(100))
    soil_type = db.Column(db.String(100))
    crops_grown = db.Column(db.String(200))
    revenue = db.Column(db.Float)

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'))
    scheme_id = db.Column(db.Integer, db.ForeignKey('loan_scheme.id'))
    amount = db.Column(db.Float)
    status = db.Column(db.String(20))  # 'pending', 'approved', 'rejected'
    credit_score = db.Column(db.Float)
    applied_date = db.Column(db.DateTime, default=datetime.utcnow)
    processed_date = db.Column(db.DateTime)
    farmer = db.relationship('User', backref='loans')
    bank = db.relationship('Bank', backref='loans')
    scheme = db.relationship('LoanScheme', backref='loans')

@login_manager.user_loader
def load_user(user_id):
    # Try to load as bank employee first
    user = BankEmployee.query.get(int(user_id))
    if user:
        return user
    # If not found, try to load as regular user (farmer)
    user = User.query.get(int(user_id))
    if user and user.role == 'farmer':
        return user
    return None

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/farmer/signup', methods=['GET', 'POST'])
def farmer_signup():
    if request.method == 'POST':
        name = request.form.get('name')
        aadhar = request.form.get('aadhar')
        mobile = request.form.get('mobile')
        password = request.form.get('password')
        
        print(f"Attempting to register farmer: {name}, mobile: {mobile}")  # Debug log
        
        # Check if user already exists
        if User.query.filter_by(aadhar=aadhar).first():
            flash('Aadhar number already registered', 'danger')
            return redirect(url_for('farmer_signup'))
        
        if User.query.filter_by(mobile=mobile).first():
            flash('Mobile number already registered', 'danger')
            return redirect(url_for('farmer_signup'))
        
        # Create username from mobile number
        username = f"farmer_{mobile}"
        
        # Create new user with plain password
        new_user = User(
            username=username,
            password_hash=password,  # Using password instead of password_hash
            role='farmer',
            aadhar=aadhar,
            mobile=mobile,
            name=name
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            print(f"Successfully registered farmer: {name}")  # Debug log
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('farmer_login'))
        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {str(e)}")  # Debug log
            flash('Registration failed. Please try again.', 'danger')
            return redirect(url_for('farmer_signup'))
            
    return render_template('farmer_signup.html')

@app.route('/farmer/login', methods=['GET', 'POST'])
def farmer_login():
    if request.method == 'POST':
        mobile = request.form.get('mobile')
        password = request.form.get('password')
        
        # Check if user exists and is a farmer
        user = User.query.filter_by(mobile=mobile, role='farmer').first()
        
        if not user:
            flash('No account found with this mobile number. Please register first.', 'danger')
            return redirect(url_for('farmer_login'))
        
        if user.password_hash != password:  # Compare plain passwords
            flash('Incorrect password. Please try again.', 'danger')
            return redirect(url_for('farmer_login'))
        
        login_user(user)
        flash('Login successful!', 'success')
        return redirect(url_for('farmer_dashboard'))
            
    return render_template('farmer_login.html')

@app.route('/bank/register', methods=['GET', 'POST'])
def bank_register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        bank_name = request.form.get('bank_name')
        branch = request.form.get('branch')
        
        # Check if username already exists
        if BankEmployee.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('bank_register'))
        
        # Create new bank employee
        new_employee = BankEmployee(
            username=username,
            password_hash=password,  # Store plain password as requested
            name=name,
            bank_name=bank_name,
            branch=branch
        )
        
        try:
            db.session.add(new_employee)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('bank_login'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'danger')
            return redirect(url_for('bank_register'))
    
    # Get list of banks for dropdown
    banks = Bank.query.all()
    return render_template('bank_register.html', banks=banks)

@app.route('/bank/login', methods=['GET', 'POST'])
def bank_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = BankEmployee.query.filter_by(username=username).first()
        
        if user and user.password_hash == password:
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('bank_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
            return redirect(url_for('bank_login'))
            
    return render_template('bank_login.html')

@app.route('/farmer/dashboard', methods=['GET', 'POST'])
@login_required
def farmer_dashboard():
    # Check if user is logged in and is a farmer
    if not isinstance(current_user, User) or current_user.role != 'farmer':
        flash('Access denied. Please login as a farmer.', 'danger')
        return redirect(url_for('farmer_login'))
    
    if request.method == 'POST':
        form_number = request.form.get('form_number')
        if form_number:
            # Update user's username with form number
            current_user.username = form_number
            try:
                db.session.commit()
                flash('Form number updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash('Failed to update form number. Please try again.', 'danger')
    
    # Get farmer's saatbaar data
    saatbaar_data = Saatbaar.query.filter_by(form_number=current_user.username).first()
    
    # Get farmer's loan applications
    loans = Loan.query.filter_by(farmer_id=current_user.id).all()
    
    # Calculate credit score if saatbaar data exists
    credit_score = None
    if saatbaar_data:
        credit_score = calculate_credit_score(saatbaar_data)
    
    # Sample data for recommended crops (replace with actual API data)
    recommended_crops = [
        {
            'name': 'Wheat',
            'market_price': 2500,
            'description': 'Best suited for your soil type and climate'
        },
        {
            'name': 'Cotton',
            'market_price': 6000,
            'description': 'High-value crop with good market demand'
        }
    ]
    
    # Sample weather forecast data (replace with actual API data)
    weather_forecast = [
        {
            'date': '2024-03-24',
            'max_temp': 32,
            'min_temp': 20,
            'rainfall': 0
        },
        {
            'date': '2024-03-25',
            'max_temp': 30,
            'min_temp': 18,
            'rainfall': 5
        }
    ]
    
    return render_template('farmer_dashboard.html', 
                         saatbaar_data=saatbaar_data, 
                         loans=loans,
                         credit_score=credit_score,
                         recommended_crops=recommended_crops,
                         weather_forecast=weather_forecast)

@app.route('/bank/dashboard')
@login_required
def bank_dashboard():
    if not isinstance(current_user, BankEmployee):
        flash('Access denied. Please login as a bank employee.', 'danger')
        return redirect(url_for('index'))
    
    # Get bank details
    bank = Bank.query.filter_by(name=current_user.bank_name).first()
    if not bank:
        flash('Bank details not found.', 'danger')
        return redirect(url_for('bank_login'))
    
    # Get all loan applications for this bank
    pending_loans = Loan.query.filter_by(bank_id=bank.id, status='pending').all()
    approved_loans = Loan.query.filter_by(bank_id=bank.id, status='approved').all()
    rejected_loans = Loan.query.filter_by(bank_id=bank.id, status='rejected').all()
    
    return render_template('bank_dashboard.html', 
                         pending_loans=pending_loans,
                         approved_loans=approved_loans,
                         rejected_loans=rejected_loans,
                         bank_name=current_user.bank_name)

@app.route('/farmer/apply_loan', methods=['GET', 'POST'])
@login_required
def apply_loan():
    if current_user.role != 'farmer':
        flash('Access denied. Please login as a farmer.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        
        # Get saatbaar data for credit score calculation
        saatbaar_data = Saatbaar.query.filter_by(form_number=current_user.username).first()
        if not saatbaar_data:
            flash('Please complete your saatbaar registration first.', 'danger')
            return redirect(url_for('farmer_dashboard'))
        
        # Calculate credit score
        credit_score = calculate_credit_score(saatbaar_data)
        
        # Create new loan application
        new_loan = Loan(
            farmer_id=current_user.id,
            amount=amount,
            status='pending',
            credit_score=credit_score
        )
        
        try:
            db.session.add(new_loan)
            db.session.commit()
            flash('Loan application submitted successfully!', 'success')
            return redirect(url_for('farmer_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to submit loan application. Please try again.', 'danger')
            return redirect(url_for('apply_loan'))
    
    return render_template('apply_loan.html')

@app.route('/bank/process_loan/<int:loan_id>', methods=['POST'])
@login_required
def process_loan(loan_id):
    if current_user.role != 'bank_employee':
        flash('Access denied. Please login as a bank employee.', 'danger')
        return redirect(url_for('index'))
    
    loan = Loan.query.get_or_404(loan_id)
    action = request.form.get('action')
    
    if action == 'approve':
        loan.status = 'approved'
        loan.processed_date = datetime.utcnow()
        flash('Loan approved successfully!', 'success')
    elif action == 'reject':
        loan.status = 'rejected'
        loan.processed_date = datetime.utcnow()
        flash('Loan rejected.', 'info')
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash('Failed to process loan. Please try again.', 'danger')
    
    return redirect(url_for('bank_dashboard'))

@app.route('/farmer/saatbaar', methods=['GET', 'POST'])
@login_required
def saatbaar_registration():
    if current_user.role != 'farmer':
        flash('Access denied. Please login as a farmer.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        form_number = request.form.get('form_number')
        location = request.form.get('location')
        longitude = float(request.form.get('longitude'))
        latitude = float(request.form.get('latitude'))
        land_area = float(request.form.get('land_area'))
        encumbrances = request.form.get('encumbrances')
        litigation_status = request.form.get('litigation_status')
        irrigation_source = request.form.get('irrigation_source')
        soil_type = request.form.get('soil_type')
        crops_grown = request.form.get('crops_grown')
        revenue = float(request.form.get('revenue'))
        
        # Create new saatbaar entry
        new_saatbaar = Saatbaar(
            form_number=form_number,
            location=location,
            longitude=longitude,
            latitude=latitude,
            land_area=land_area,
            encumbrances=encumbrances,
            litigation_status=litigation_status,
            irrigation_source=irrigation_source,
            soil_type=soil_type,
            crops_grown=crops_grown,
            revenue=revenue
        )
        
        try:
            db.session.add(new_saatbaar)
            db.session.commit()
            flash('Saatbaar registration completed successfully!', 'success')
            return redirect(url_for('farmer_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to complete saatbaar registration. Please try again.', 'danger')
            return redirect(url_for('saatbaar_registration'))
    
    return render_template('saatbaar_registration.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

def calculate_credit_score(saatbaar_data):
    score = 0
    
    # Land Area (25%)
    if saatbaar_data.land_area > 5:
        score += 25
    elif saatbaar_data.land_area > 2:
        score += 15
    else:
        score += 10
    
    # Encumbrances (20%)
    if saatbaar_data.encumbrances == 'None':
        score += 20
    elif saatbaar_data.encumbrances == 'Low':
        score += 15
    else:
        score += 5
    
    # Litigation Status (15%)
    if saatbaar_data.litigation_status == 'None':
        score += 15
    elif saatbaar_data.litigation_status == 'Pending':
        score += 8
    else:
        score += 3
    
    # Irrigation Source (15%)
    if saatbaar_data.irrigation_source in ['Canal', 'Borewell']:
        score += 15
    elif saatbaar_data.irrigation_source == 'Mixed':
        score += 10
    else:
        score += 5
    
    # Soil Type (10%)
    if saatbaar_data.soil_type in ['Black', 'Loamy']:
        score += 10
    elif saatbaar_data.soil_type == 'Red':
        score += 7
    else:
        score += 3
    
    # Crops Grown (10%)
    high_value_crops = ['Wheat', 'Sugarcane', 'Cotton']
    crops = saatbaar_data.crops_grown.split(',')
    if any(crop.strip() in high_value_crops for crop in crops):
        score += 10
    else:
        score += 5
    
    return score

# Drop all tables and recreate them
def reset_database():
    with app.app_context():
        # Create a new connection without database
        engine = db.create_engine('mysql://root:@localhost/')
        
        # Drop database if exists
        with engine.connect() as conn:
            conn.execute(text('DROP DATABASE IF EXISTS agri_loan_db'))
            conn.execute(text('CREATE DATABASE agri_loan_db'))
            conn.commit()
        
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")
        
        # Initialize bank data after creating tables
        initialize_banks()
        print("Bank data initialized successfully!")

@app.route('/farmer/view_applications')
@login_required
def view_applications():
    if current_user.role != 'farmer':
        flash('Access denied. Please login as a farmer.', 'danger')
        return redirect(url_for('index'))
    
    # Get all loan applications for the current farmer
    applications = Loan.query.filter_by(farmer_id=current_user.id).all()
    return render_template('view_applications.html', applications=applications)

@app.route('/farmer/view_active_loans')
@login_required
def view_active_loans():
    if current_user.role != 'farmer':
        flash('Access denied. Please login as a farmer.', 'danger')
        return redirect(url_for('index'))
    
    # Get approved loans for the current farmer
    active_loans = Loan.query.filter_by(farmer_id=current_user.id, status='approved').all()
    return render_template('view_active_loans.html', active_loans=active_loans)

# Add function to initialize bank data
def initialize_banks():
    banks = [
        {
            'name': 'HDFC Bank',
            'schemes': [
                {
                    'name': 'Kisan Credit Card',
                    'description': 'Special scheme for farmers with competitive interest rates',
                    'min_amount': 50000,
                    'max_amount': 1000000,
                    'interest_rate': 7.5,
                    'tenure_months': 36,
                    'processing_fee': 1000
                },
                {
                    'name': 'Agricultural Term Loan',
                    'description': 'Long-term loan for agricultural purposes',
                    'min_amount': 100000,
                    'max_amount': 2000000,
                    'interest_rate': 8.0,
                    'tenure_months': 60,
                    'processing_fee': 2000
                }
            ]
        },
        {
            'name': 'SBI',
            'schemes': [
                {
                    'name': 'Kisan Credit Card',
                    'description': 'Government-backed scheme for farmers',
                    'min_amount': 10000,
                    'max_amount': 300000,
                    'interest_rate': 4.0,
                    'tenure_months': 36,
                    'processing_fee': 500
                }
            ]
        },
        {
            'name': 'Bank of Baroda',
            'schemes': [
                {
                    'name': 'Baroda Kisan Credit Card',
                    'description': 'Specialized scheme for agricultural needs',
                    'min_amount': 25000,
                    'max_amount': 500000,
                    'interest_rate': 6.5,
                    'tenure_months': 36,
                    'processing_fee': 750
                }
            ]
        },
        {
            'name': 'ICICI Bank',
            'schemes': [
                {
                    'name': 'Farm Plus',
                    'description': 'Comprehensive agricultural loan scheme',
                    'min_amount': 50000,
                    'max_amount': 1500000,
                    'interest_rate': 7.0,
                    'tenure_months': 48,
                    'processing_fee': 1500
                }
            ]
        },
        {
            'name': 'Axis Bank',
            'schemes': [
                {
                    'name': 'Kisan Plus',
                    'description': 'Flexible loan scheme for farmers',
                    'min_amount': 25000,
                    'max_amount': 1000000,
                    'interest_rate': 7.25,
                    'tenure_months': 36,
                    'processing_fee': 1000
                }
            ]
        }
    ]
    
    for bank_data in banks:
        bank = Bank(name=bank_data['name'])
        db.session.add(bank)
        db.session.flush()  # Get the bank ID
        
        for scheme_data in bank_data['schemes']:
            scheme = LoanScheme(
                bank_id=bank.id,
                **scheme_data
            )
            db.session.add(scheme)
    
    try:
        db.session.commit()
        print("Bank data initialized successfully!")
    except Exception as e:
        db.session.rollback()
        print(f"Error initializing bank data: {str(e)}")

@app.route('/loan/<int:loan_id>')
@login_required
def view_loan_details(loan_id):
    if not isinstance(current_user, BankEmployee):
        flash('Access denied. Please login as a bank employee.', 'danger')
        return redirect(url_for('index'))
    
    loan = Loan.query.get_or_404(loan_id)
    
    # Check if the loan belongs to the bank employee's bank
    if loan.bank_id != Bank.query.filter_by(name=current_user.bank_name).first().id:
        flash('Access denied. This loan belongs to a different bank.', 'danger')
        return redirect(url_for('bank_dashboard'))
    
    return render_template('view_loan_details.html', loan=loan)

@app.route('/loan/<int:loan_id>/process', methods=['POST'])
@login_required
def process_loan_details(loan_id):
    if not isinstance(current_user, BankEmployee):
        flash('Access denied. Please login as a bank employee.', 'danger')
        return redirect(url_for('index'))
    
    loan = Loan.query.get_or_404(loan_id)
    
    # Check if the loan belongs to the bank employee's bank
    if loan.bank_id != Bank.query.filter_by(name=current_user.bank_name).first().id:
        flash('Access denied. This loan belongs to a different bank.', 'danger')
        return redirect(url_for('bank_dashboard'))
    
    # Check if the loan is still pending
    if loan.status != 'pending':
        flash('This loan has already been processed.', 'warning')
        return redirect(url_for('view_loan_details', loan_id=loan_id))
    
    action = request.form.get('action')
    remarks = request.form.get('remarks')
    
    if action == 'approve':
        loan.status = 'approved'
        loan.processed_date = datetime.utcnow()
        loan.remarks = remarks
        
        # Create bank account for the farmer if it doesn't exist
        bank_account = BankAccount.query.filter_by(farmer_id=loan.farmer_id).first()
        if not bank_account:
            bank_account = BankAccount(
                farmer_id=loan.farmer_id,
                account_number=f"ACC{loan.farmer_id:06d}",
                balance=0
            )
            db.session.add(bank_account)
        
        # Add loan amount to the account
        bank_account.balance += loan.amount
        
        flash('Loan approved successfully!', 'success')
    elif action == 'reject':
        loan.status = 'rejected'
        loan.processed_date = datetime.utcnow()
        loan.remarks = remarks
        flash('Loan rejected.', 'info')
    else:
        flash('Invalid action.', 'danger')
        return redirect(url_for('view_loan_details', loan_id=loan_id))
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash('Error processing loan. Please try again.', 'danger')
    
    return redirect(url_for('view_loan_details', loan_id=loan_id))

if __name__ == '__main__':
    # Only create tables if they don't exist
    with app.app_context():
        db.create_all()
        # Initialize bank data only if no banks exist
        if not Bank.query.first():
            initialize_banks()
    app.run(debug=True) 
