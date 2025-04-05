from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
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
    
    # Get current month and year
    current_date = datetime.now()
    current_month = current_date.month
    current_year = current_date.year
    month_name = calendar.month_name[current_month]
    
    # Get date range for the current month
    month_start = f"{current_year}-{current_month:02d}-01"
    if current_month == 12:
        next_month_year = current_year + 1
        next_month = 1
    else:
        next_month_year = current_year
        next_month = current_month + 1
    month_end = f"{next_month_year}-{next_month:02d}-01"
    
    conn = get_db_connection()
    
    # Get categories
    categories = conn.execute('SELECT * FROM categories').fetchall()
    
    # Get total salary for current month
    monthly_salary = conn.execute(
        'SELECT SUM(amount) as total FROM salaries WHERE date >= ? AND date < ?', 
        (month_start, month_end)
    ).fetchone()
    
    # Get all salaries for the current month
    monthly_salaries = conn.execute(
        'SELECT * FROM salaries WHERE date >= ? AND date < ? ORDER BY date DESC', 
        (month_start, month_end)
    ).fetchall()
    
    # Get total expenses for the current month
    total_expenses_result = conn.execute(
        'SELECT SUM(amount) as total FROM expenses WHERE date >= ? AND date < ?',
        (month_start, month_end)
    ).fetchone()
    
    total_expenses = total_expenses_result['total'] if total_expenses_result['total'] else 0
    
    # Get expenses by category for the current month
    expenses_by_category = conn.execute(
        '''SELECT c.id, c.name, SUM(e.amount) as total 
           FROM expenses e 
           JOIN categories c ON e.category_id = c.id 
           WHERE e.date >= ? AND e.date < ? 
           GROUP BY c.id''',
        (month_start, month_end)
    ).fetchall()
    
    # Create a dictionary to store category expenses
    category_expenses = {}
    for expense in expenses_by_category:
        category_expenses[expense['id']] = expense['total']
    
    # Get recent expenses
    recent_expenses = conn.execute(
        '''SELECT e.*, c.name as category_name 
           FROM expenses e 
           JOIN categories c ON e.category_id = c.id 
           ORDER BY e.date DESC LIMIT 5'''
    ).fetchall()
    
    # Calculate budget for each category
    budget_data = []
    if monthly_salary and monthly_salary['total']:
        total_salary = monthly_salary['total']
        for category in categories:
            budget_amount = total_salary * (category['percentage'] / 100)
            spent = category_expenses.get(category['id'], 0)
            remaining = budget_amount - spent
            usage_percent = (spent / budget_amount * 100) if budget_amount > 0 else 0
            
            budget_data.append({
                'id': category['id'],
                'name': category['name'],
                'percentage': category['percentage'],
                'budget': budget_amount,
                'spent': spent,
                'remaining': remaining,
                'usage_percent': usage_percent
            })
    
    conn.close()
    
    return render_template('dashboard.html', 
                          username=session['username'], 
                          categories=categories, 
                          monthly_salary=monthly_salary,
                          monthly_salaries=monthly_salaries,
                          month_name=month_name,
                          current_year=current_year,
                          budget_data=budget_data,
                          total_expenses=total_expenses,
                          recent_expenses=recent_expenses)

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
    
    # Get current date or selected date from query parameters
    current_date = datetime.now()
    selected_month = int(request.args.get('month', current_date.month))
    selected_year = int(request.args.get('year', current_date.year))
    
    # Get month name and calendar months for dropdown
    month_name = calendar.month_name[selected_month]
    calendar_months = {i: calendar.month_name[i] for i in range(1, 13)}
    
    # Calculate date range for the selected month
    month_start = f"{selected_year}-{selected_month:02d}-01"
    if selected_month == 12:
        next_month_year = selected_year + 1
        next_month = 1
    else:
        next_month_year = selected_year
        next_month = selected_month + 1
    month_end = f"{next_month_year}-{next_month:02d}-01"
    
    conn = get_db_connection()
    
    # Get total salary for selected month
    monthly_salary = conn.execute(
        'SELECT SUM(amount) as total FROM salaries WHERE date >= ? AND date < ?', 
        (month_start, month_end)
    ).fetchone()
    
    # Get all salaries for the selected month
    monthly_salaries = conn.execute(
        'SELECT * FROM salaries WHERE date >= ? AND date < ? ORDER BY date DESC', 
        (month_start, month_end)
    ).fetchall()
    
    if request.method == 'POST':
        amount = float(request.form['amount'])
        date_str = request.form['date']
        date = datetime.strptime(date_str, '%Y-%m-%d')        
        conn.execute('INSERT INTO salaries (amount, date) VALUES (?, ?)',
                    (amount, date))
        conn.commit()
        
        flash('Salary added successfully', 'success')
        return redirect(url_for('salary', month=selected_month, year=selected_year))
    
    conn.close()
    
    return render_template('salary.html', 
                          month_name=month_name,
                          current_year=current_date.year,
                          selected_month=selected_month,
                          selected_year=selected_year,
                          calendar_months=calendar_months,
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

@app.route('/expenses', methods=['GET', 'POST'])
def expenses():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    # Get current date or selected date from query parameters
    current_date = datetime.now()
    selected_month = int(request.args.get('month', current_date.month))
    selected_year = int(request.args.get('year', current_date.year))
    
    # Get month name and calendar months for dropdown
    month_name = calendar.month_name[selected_month]
    calendar_months = {i: calendar.month_name[i] for i in range(1, 13)}
    
    # Calculate date range for the selected month
    month_start = f"{selected_year}-{selected_month:02d}-01"
    if selected_month == 12:
        next_month_year = selected_year + 1
        next_month = 1
    else:
        next_month_year = selected_year
        next_month = selected_month + 1
    month_end = f"{next_month_year}-{next_month:02d}-01"
    
    conn = get_db_connection()
    
    # Get all categories
    categories = conn.execute('SELECT * FROM categories').fetchall()
    
    # Handle form submission for adding a new expense
    if request.method == 'POST':
        category_id = request.form['category_id']
        amount = float(request.form['amount'])
        description = request.form['description']
        date = request.form['date']
        
        conn.execute(
            'INSERT INTO expenses (category_id, amount, description, date) VALUES (?, ?, ?, ?)',
            (category_id, amount, description, date)
        )
        conn.commit()
        
        flash('Expense added successfully', 'success')
        return redirect(url_for('expenses', month=selected_month, year=selected_year))
    
    # Get all expenses for the selected month
    monthly_expenses = conn.execute(
        '''SELECT e.*, c.name as category_name 
           FROM expenses e 
           JOIN categories c ON e.category_id = c.id 
           WHERE e.date >= ? AND e.date < ? 
           ORDER BY e.date DESC''', 
        (month_start, month_end)
    ).fetchall()
    
    # Organize expenses by category
    expenses_by_category = {}
    category_totals = {}
    total_expenses = 0
    
    for expense in monthly_expenses:
        category_name = expense['category_name']
        if category_name not in expenses_by_category:
            expenses_by_category[category_name] = []
            category_totals[category_name] = 0
        
        expenses_by_category[category_name].append(expense)
        category_totals[category_name] += expense['amount']
        total_expenses += expense['amount']
    
    # Get data for the last 12 months for charts
    monthly_labels = []
    monthly_data = []
    
    # Start from 11 months ago
    start_date = datetime(selected_year, selected_month, 1) - timedelta(days=365)
    
    for i in range(12):
        current = start_date + timedelta(days=30*i)
        month_start = f"{current.year}-{current.month:02d}-01"
        
        if current.month == 12:
            next_month_year = current.year + 1
            next_month = 1
        else:
            next_month_year = current.year
            next_month = current.month + 1
        
        month_end = f"{next_month_year}-{next_month:02d}-01"
        
        month_total = conn.execute(
            'SELECT SUM(amount) as total FROM expenses WHERE date >= ? AND date < ?',
            (month_start, month_end)
        ).fetchone()
        
        monthly_labels.append(f"{calendar.month_name[current.month]} {current.year}")
        monthly_data.append(month_total['total'] if month_total['total'] else 0)
    
    # Get data for category pie chart
    category_labels = list(category_totals.keys())
    category_data = list(category_totals.values())
    
    conn.close()
    
    return render_template(
        'expenses.html',
        categories=categories,
        monthly_expenses=monthly_expenses,
        expenses_by_category=expenses_by_category,
        category_totals=category_totals,
        total_expenses=total_expenses,
        month_name=month_name,
        current_year=current_date.year,
        selected_month=selected_month,
        selected_year=selected_year,
        calendar_months=calendar_months,
        monthly_labels=monthly_labels,
        monthly_data=monthly_data,
        category_labels=category_labels,
        category_data=category_data
    )

@app.route('/expenses/delete/<int:id>', methods=['POST'])
def delete_expense(id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    conn = get_db_connection()
    conn.execute('DELETE FROM expenses WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Expense deleted successfully', 'success')
    return redirect(url_for('expenses'))

@app.route('/charts')
def charts():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    # Get current date
    current_date = datetime.now()
    
    conn = get_db_connection()
    
    # Get all categories
    categories = conn.execute('SELECT * FROM categories').fetchall()
    
    # Prepare data for the last 12 months
    month_labels = []
    income_data = []
    expense_data = []
    
    # Prepare data for category expenses
    category_monthly_data = {category['id']: [] for category in categories}
    
    # Define colors for categories
    category_colors = [
        "75, 192, 192, 0.6", "255, 99, 132, 0.6", "255, 205, 86, 0.6", 
        "54, 162, 235, 0.6", "153, 102, 255, 0.6", "255, 159, 64, 0.6",
        "201, 203, 207, 0.6", "255, 99, 71, 0.6", "46, 139, 87, 0.6",
        "106, 90, 205, 0.6", "255, 215, 0, 0.6", "178, 34, 34, 0.6"
    ]
    
    # Start from 11 months ago
    for i in range(12):
        # Calculate month and year
        month_offset = (current_date.month - i - 1) % 12 + 1
        year_offset = current_date.year - ((current_date.month - i - 1) // 12)
        
        # Format date strings for SQL queries
        month_start = f"{year_offset}-{month_offset:02d}-01"
        
        if month_offset == 12:
            next_month_year = year_offset + 1
            next_month = 1
        else:
            next_month_year = year_offset
            next_month = month_offset + 1
            
        month_end = f"{next_month_year}-{next_month:02d}-01"
        
        # Get month name for labels
        month_name = f"{calendar.month_name[month_offset]} {year_offset}"
        month_labels.insert(0, month_name)
        
        # Get total income for the month
        monthly_income = conn.execute(
            'SELECT SUM(amount) as total FROM salaries WHERE date >= ? AND date < ?',
            (month_start, month_end)
        ).fetchone()
        
        income_amount = monthly_income['total'] if monthly_income['total'] else 0
        income_data.insert(0, income_amount)
        
        # Get total expenses for the month
        monthly_expenses = conn.execute(
            'SELECT SUM(amount) as total FROM expenses WHERE date >= ? AND date < ?',
            (month_start, month_end)
        ).fetchone()
        
        expense_amount = monthly_expenses['total'] if monthly_expenses['total'] else 0
        expense_data.insert(0, expense_amount)
        
        # Get expenses by category for the month
        for category in categories:
            category_expense = conn.execute(
                '''SELECT SUM(amount) as total 
                   FROM expenses 
                   WHERE category_id = ? AND date >= ? AND date < ?''',
                (category['id'], month_start, month_end)
            ).fetchone()
            
            category_amount = category_expense['total'] if category_expense['total'] else 0
            category_monthly_data[category['id']].insert(0, category_amount)
    
    # Prepare datasets for stacked bar chart
    category_datasets = []
    for i, category in enumerate(categories):
        category_datasets.append({
            'label': category['name'],
            'data': category_monthly_data[category['id']],
            'backgroundColor': f'rgba({category_colors[i % len(category_colors)]})',
            'borderColor': f'rgba({category_colors[i % len(category_colors)].replace("0.6", "1")})',
            'borderWidth': 1
        })
    
    conn.close()
    
    return render_template(
        'charts.html',
        categories=categories,
        month_labels=month_labels,
        income_data=income_data,
        expense_data=expense_data,
        category_datasets=category_datasets,
        category_monthly_data=category_monthly_data,
        category_colors=category_colors
    )


if __name__ == '__main__':
    app.run(debug=True)
