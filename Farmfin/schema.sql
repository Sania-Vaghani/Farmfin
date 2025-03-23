-- Create database
CREATE DATABASE IF NOT EXISTS agri_loan_db;
USE agri_loan_db;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(120) NOT NULL,
    role ENUM('farmer', 'bank_employee') NOT NULL,
    aadhar VARCHAR(12) UNIQUE,
    mobile VARCHAR(10),
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Saatbaar (7/11) table
CREATE TABLE IF NOT EXISTS saatbaar (
    id INT AUTO_INCREMENT PRIMARY KEY,
    form_number VARCHAR(20) UNIQUE NOT NULL,
    location VARCHAR(200),
    longitude FLOAT,
    latitude FLOAT,
    land_area FLOAT,
    encumbrances VARCHAR(200),
    litigation_status VARCHAR(50),
    irrigation_source VARCHAR(100),
    soil_type VARCHAR(100),
    crops_grown VARCHAR(200),
    revenue FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Loans table
CREATE TABLE IF NOT EXISTS loans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    farmer_id INT NOT NULL,
    form_number VARCHAR(20) NOT NULL,
    amount FLOAT NOT NULL,
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    credit_score FLOAT,
    applied_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_date TIMESTAMP NULL,
    FOREIGN KEY (farmer_id) REFERENCES users(id),
    FOREIGN KEY (form_number) REFERENCES saatbaar(form_number)
);

-- Bank accounts table
CREATE TABLE IF NOT EXISTS bank_accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    farmer_id INT NOT NULL,
    account_number VARCHAR(20) UNIQUE NOT NULL,
    balance FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farmer_id) REFERENCES users(id)
);

-- Insert sample bank employee
INSERT INTO users (username, password_hash, role, name) 
VALUES ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyDAZ1YxXxqXeG', 'bank_employee', 'Admin User');

-- Insert sample saatbaar data
INSERT INTO saatbaar (form_number, location, longitude, latitude, land_area, encumbrances, litigation_status, irrigation_source, soil_type, crops_grown, revenue)
VALUES 
('SAAT001', 'Village A, District X', 75.123456, 12.345678, 5.5, 'None', 'None', 'Canal', 'Black', 'Wheat,Sugarcane', 150000),
('SAAT002', 'Village B, District Y', 75.234567, 12.456789, 3.2, 'Low', 'Pending', 'Borewell', 'Loamy', 'Cotton', 120000),
('SAAT003', 'Village C, District Z', 75.345678, 12.567890, 2.8, 'High', 'Disputed', 'Rainfed', 'Red', 'Rice', 80000); 