from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import calendar

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # for session management

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_user_id(username):
    conn = get_db_connection()
    user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user['id'] if user else None

@app.route('/')
def home():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    # Check if user is logged in
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in
    
    user_id = get_user_id(session['username'])
    
    # Get categories
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    
    # Get current month and year
    current_date = datetime.now()
    current_month = current_date.month
    current_year = current_date.year
    month_name = calendar.month_name[current_month]
    
    # Get total salary for current month
    month_start = f"{current_year}-{current_month:02d}-01"
    if current_month == 12:
        next_month_year = current_year + 1
        next_month = 1
    else:
        next_month_year = current_year
        next_month = current_month + 1
    month_end = f"{next_month_year}-{next_month:02d}-01"
    
    monthly_salary = conn.execute(
        'SELECT SUM(amount) as total FROM salaries WHERE date >= ? AND date < ?', 
        (month_start, month_end)
    ).fetchone()
    
    # Get all salaries for the current month
    monthly_salaries = conn.execute(
        'SELECT * FROM salaries WHERE date >= ? AND date < ? ORDER BY date DESC', 
        (month_start, month_end)
    ).fetchall()
    
    conn.close()
    
    # Calculate budget for each category
    budget_data = []
    if monthly_salary and monthly_salary['total']:
        total_salary = monthly_salary['total']
        for category in categories:
            budget_amount = total_salary * (category['percentage'] / 100)
            budget_data.append({
                'name': category['name'],
                'percentage': category['percentage'],
                'budget': budget_amount
            })
            
    return render_template('dashboard.html', 
                          username=session['username'], 
                          categories=categories, 
                          monthly_salary=monthly_salary,
                          monthly_salaries=monthly_salaries,
                          month_name=month_name,
                          current_year=current_year,
                          budget_data=budget_data)

@app.route('/categories', methods=['GET', 'POST'])
def categories():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    if request.method == 'POST':
        name = request.form['name']
        percentage = float(request.form['percentage'])
        
        conn = get_db_connection()
        conn.execute('INSERT INTO categories (name, percentage) VALUES (?, ?)',
                    (name, percentage))
        conn.commit()
        conn.close()
        
        flash('Category added successfully', 'success')
        return redirect(url_for('categories'))
    
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    conn.close()
    
    return render_template('categories.html', categories=categories)

@app.route('/categories/update/<int:id>', methods=['POST'])
def update_category(id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    # Get the new percentage from the form
    percentage = float(request.form['percentage'])
    
    conn = get_db_connection()
    conn.execute('UPDATE categories SET percentage = ? WHERE id = ?', 
                (percentage, id))
    conn.commit()
    conn.close()
    
    flash('Category updated successfully', 'success')
    return redirect(url_for('categories'))

@app.route('/categories/delete/<int:id>', methods=['POST'])
def delete_category(id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])

    conn = get_db_connection()
    conn.execute('DELETE FROM categories WHERE id = ?', (id, user_id))
    conn.commit()
    conn.close()
    
    flash('Category deleted successfully', 'success')
    return redirect(url_for('categories'))

@app.route('/salary', methods=['GET', 'POST'])
def salary():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    # Get current month and year
    current_date = datetime.now()
    current_month = current_date.month
    current_year = current_date.year
    month_name = calendar.month_name[current_month]
    
    # Get total salary for current month
    month_start = f"{current_year}-{current_month:02d}-01"
    if current_month == 12:
        next_month_year = current_year + 1
        next_month = 1
    else:
        next_month_year = current_year
        next_month = current_month + 1
    month_end = f"{next_month_year}-{next_month:02d}-01"
    
    conn = get_db_connection()
    monthly_salary = conn.execute(
        'SELECT SUM(amount) as total FROM salaries WHERE date >= ? AND date < ?', 
        (month_start, month_end)
    ).fetchone()
    
    # Get all salaries for the current month
    monthly_salaries = conn.execute(
        'SELECT * FROM salaries WHERE date >= ? AND date < ? ORDER BY date DESC', 
        (month_start, month_end)
    ).fetchall()
    
    if request.method == 'POST':
        amount = float(request.form['amount'])
        date = datetime.now().strftime("%Y-%m-%d")
        
        conn.execute('INSERT INTO salaries (amount, date) VALUES (?, ?)',
                    (amount, date))
        conn.commit()
        
        flash('Salary added successfully', 'success')
        return redirect(url_for('salary'))
    
    conn.close()
    
    return render_template('salary.html', 
                          month_name=month_name,
                          current_year=current_year,
                          monthly_salary=monthly_salary,
                          monthly_salaries=monthly_salaries)

@app.route('/salary/delete/<int:id>', methods=['POST'])
def delete_salary(id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])

    conn = get_db_connection()
    conn.execute('DELETE FROM salaries WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Salary entry deleted successfully', 'success')
    return redirect(url_for('salary'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):  # Verify password hash
            # Store user data in session
            session['username'] = username
            return redirect(url_for('dashboard'))  # Redirect to dashboard after login
        else:
            flash('Invalid username or password', 'danger')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Hash the password before storing it in the database
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
        conn.commit()
        conn.close()

        flash('Registration successful, please log in', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    # Clear the session to log out the user
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
