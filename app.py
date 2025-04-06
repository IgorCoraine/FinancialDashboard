from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
import calendar

# Initialize Flask application
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # for session management

# Database connection functions
def get_db_connection():
    """Create and return a database connection with row factory"""
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_user_id(username):
    """Get user ID from username"""
    conn = get_db_connection()
    user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user['id'] if user else None

# Route handlers
@app.route('/')
def home():
    """Redirect to dashboard from home page"""
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    """Display the main dashboard with budget information"""
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
    """Manage expense categories"""
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
    """Update an existing category"""
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
    """Delete a category"""
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
    """Manage salary entries"""
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
    """Delete a salary entry"""
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
    """Handle user login"""
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
    """Handle user registration"""
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
    """Handle user logout"""
    # Clear the session to log out the user
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/expenses', methods=['GET', 'POST'])
def expenses():
    """Manage expenses"""
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
    """Delete an expense"""
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
    """Display financial charts"""
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

@app.route('/investments', methods=['GET', 'POST'])
def investments():
    """Manage investments"""
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
    
    # Get all investment categories
    investment_categories = conn.execute('SELECT * FROM investment_categories').fetchall()
    
    # Handle form submission for adding a new investment
    if request.method == 'POST':
        action = request.form.get('action', 'add_investment')
        
        if action == 'add_investment':
            name = request.form['name']
            category_id = request.form['category_id']
            maturity_date = request.form.get('maturity_date', '')
            liquidity = request.form['liquidity']
            institution = request.form['institution']
            initial_amount = float(request.form['initial_amount'])
            transaction_date = request.form['transaction_date']
            
            # Insert the investment
            cursor = conn.execute(
                '''INSERT INTO investments 
                   (name, category_id, maturity_date, liquidity, institution) 
                   VALUES (?, ?, ?, ?, ?)''',
                (name, category_id, maturity_date, liquidity, institution)
            )
            investment_id = cursor.lastrowid
            
            # Insert the initial transaction
            conn.execute(
                '''INSERT INTO investment_transactions 
                   (investment_id, amount, transaction_type, date) 
                   VALUES (?, ?, ?, ?)''',
                (investment_id, initial_amount, 'deposit', transaction_date)
            )
            conn.commit()
            
            flash('Investment added successfully', 'success')
        
        elif action == 'add_transaction':
            investment_id = request.form['investment_id']
            amount = float(request.form['amount'])
            transaction_type = request.form['transaction_type']
            transaction_date = request.form['transaction_date']
            profit_amount = request.form.get('profit_amount', None)
            
            if profit_amount:
                profit_amount = float(profit_amount)
            
            conn.execute(
                '''INSERT INTO investment_transactions 
                   (investment_id, amount, transaction_type, date, profit_amount) 
                   VALUES (?, ?, ?, ?, ?)''',
                (investment_id, amount, transaction_type, transaction_date, profit_amount)
            )
            conn.commit()
            
            flash('Transaction added successfully', 'success')
        
        elif action == 'add_category':
            category_name = request.form['category_name']
            
            conn.execute(
                'INSERT INTO investment_categories (name) VALUES (?)',
                (category_name,)
            )
            conn.commit()
            
            flash('Investment category added successfully', 'success')
        
        return redirect(url_for('investments', month=selected_month, year=selected_year))
    
    # Get all investments with their current balance
    investments_data = conn.execute(
        '''SELECT i.id, i.name, i.category_id, i.maturity_date, i.liquidity, i.institution, 
                  ic.name as category_name,
                  (SELECT SUM(CASE WHEN transaction_type = 'deposit' THEN amount 
                                   WHEN transaction_type = 'withdrawal' THEN -amount 
                                   ELSE 0 END) 
                   FROM investment_transactions 
                   WHERE investment_id = i.id) as current_balance,
                  (SELECT SUM(profit_amount) 
                   FROM investment_transactions 
                   WHERE investment_id = i.id AND profit_amount IS NOT NULL) as total_profit
           FROM investments i
           JOIN investment_categories ic ON i.category_id = ic.id
           ORDER BY i.name'''
    ).fetchall()
    
    # Calculate total investments and profits
    total_invested = 0
    total_profit = 0
    total_current_value = 0
    
    for inv in investments_data:
        if inv['current_balance']:
            total_invested += inv['current_balance']
        if inv['total_profit']:
            total_profit += inv['total_profit']
    
    total_current_value = total_invested + total_profit
    
    # Calculate profit percentage
    gross_profit_percentage = (total_profit / total_invested * 100) if total_invested > 0 else 0
    
    # Get monthly profit data for the last 12 months
    monthly_labels = []
    monthly_investment_totals = []
    monthly_gross_profits = []
    monthly_net_profits = []

    # Start from current month and go back 11 months
    for i in range(12):
        # Calculate the correct month and year
        # For current month, i = 0
        # For 11 months ago, i = 11
        month = selected_month - i
        year = selected_year
        
        # Adjust the year if month is negative or zero
        while month <= 0:
            month += 12
            year -= 1
        
        # Format date strings for SQL queries
        month_start = f"{year}-{month:02d}-01"
        
        # Calculate the next month for the end of period
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1
        
        month_end = f"{next_year}-{next_month:02d}-01"
        
        # Get month name for labels
        month_name = f"{calendar.month_name[month]} {year}"
        monthly_labels.insert(0, month_name)
        
        # Get total investment value at the end of the month
        month_total = conn.execute(
            '''SELECT SUM(CASE WHEN transaction_type = 'deposit' THEN amount 
                              WHEN transaction_type = 'withdrawal' THEN -amount 
                              ELSE 0 END) as total
               FROM investment_transactions 
               WHERE date < ?''',
            (month_end,)
        ).fetchone()
        
        # Get profit for the month
        month_profit = conn.execute(
            '''SELECT SUM(profit_amount) as total
               FROM investment_transactions 
               WHERE date >= ? AND date < ? AND profit_amount IS NOT NULL''',
            (month_start, month_end)
        ).fetchone()
        
        monthly_investment_totals.insert(0, month_total['total'] if month_total['total'] else 0)
        
        profit_amount = month_profit['total'] if month_profit['total'] else 0
        monthly_gross_profits.insert(0, profit_amount)
        
        # Assuming 15% tax on profits for net calculation
        monthly_net_profits.insert(0, profit_amount * 0.85)
    
    # Get data for category pie chart
    category_totals = {}
    
    for inv in investments_data:
        category_name = inv['category_name']
        if category_name not in category_totals:
            category_totals[category_name] = 0
        
        if inv['current_balance']:
            category_totals[category_name] += inv['current_balance']
    
    category_labels = list(category_totals.keys())
    category_data = list(category_totals.values())
    
    # Get last month's profit percentage
    last_month_start = month_start
    last_month_end = month_end
    
    last_month_investment_value = conn.execute(
        '''SELECT SUM(CASE WHEN transaction_type = 'deposit' THEN amount 
                          WHEN transaction_type = 'withdrawal' THEN -amount 
                          ELSE 0 END) as total
           FROM investment_transactions 
           WHERE date < ?''',
        (last_month_start,)
    ).fetchone()
    
    last_month_profit = conn.execute(
        '''SELECT SUM(profit_amount) as total
           FROM investment_transactions 
           WHERE date >= ? AND date < ? AND profit_amount IS NOT NULL''',
        (last_month_start, last_month_end)
    ).fetchone()
    
    last_month_investment = last_month_investment_value['total'] if last_month_investment_value['total'] else 0
    last_month_profit_amount = last_month_profit['total'] if last_month_profit['total'] else 0
    
    last_month_gross_profit_percentage = (last_month_profit_amount / last_month_investment * 100) if last_month_investment > 0 else 0
    last_month_net_profit_percentage = last_month_gross_profit_percentage * 0.85  # Assuming 15% tax
    
    # Get transactions for each investment
    investment_transactions = {}
    
    for inv in investments_data:
        transactions = conn.execute(
            '''SELECT * FROM investment_transactions 
               WHERE investment_id = ? 
               ORDER BY date DESC''',
            (inv['id'],)
        ).fetchall()
        
        investment_transactions[inv['id']] = transactions
    
    conn.close()
    
    return render_template(
        'investments.html',
        investment_categories=investment_categories,
        investments=investments_data,
        investment_transactions=investment_transactions,
        total_invested=total_invested,
        total_profit=total_profit,
        total_current_value=total_current_value,
        gross_profit_percentage=gross_profit_percentage,
        net_profit_percentage=gross_profit_percentage * 0.85,  # Assuming 15% tax
        last_month_gross_profit_percentage=last_month_gross_profit_percentage,
        last_month_net_profit_percentage=last_month_net_profit_percentage,
        month_name=month_name,
        current_year=current_date.year,
        selected_month=selected_month,
        selected_year=selected_year,
        calendar_months=calendar_months,
        monthly_labels=monthly_labels,
        monthly_investment_totals=monthly_investment_totals,
        monthly_gross_profits=monthly_gross_profits,
        monthly_net_profits=monthly_net_profits,
        category_labels=category_labels,
        category_data=category_data
    )

@app.route('/investments/delete/<int:id>', methods=['POST'])
def delete_investment(id):
    """Delete an investment and its transactions"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    conn = get_db_connection()
    
    # First delete all transactions for this investment
    conn.execute('DELETE FROM investment_transactions WHERE investment_id = ?', (id,))
    
    # Then delete the investment
    conn.execute('DELETE FROM investments WHERE id = ?', (id,))
    
    conn.commit()
    conn.close()
    
    flash('Investment deleted successfully', 'success')
    return redirect(url_for('investments'))

@app.route('/investments/delete_transaction/<int:id>', methods=['POST'])
def delete_investment_transaction(id):
    """Delete an investment transaction"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    conn = get_db_connection()
    conn.execute('DELETE FROM investment_transactions WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Transaction deleted successfully', 'success')
    return redirect(url_for('investments'))

@app.route('/investment_categories', methods=['GET', 'POST'])
def investment_categories():
    """Manage investment categories"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    if request.method == 'POST':
        name = request.form['name']
        
        conn = get_db_connection()
        conn.execute('INSERT INTO investment_categories (name) VALUES (?)', (name,))
        conn.commit()
        conn.close()
        
        flash('Investment category added successfully', 'success')
        return redirect(url_for('investment_categories'))
    
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM investment_categories').fetchall()
    conn.close()
    
    return render_template('investment_categories.html', categories=categories)

@app.route('/investment_categories/delete/<int:id>', methods=['POST'])
def delete_investment_category(id):
    """Delete an investment category if not in use"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    conn = get_db_connection()
    
    # Check if category is in use
    investments = conn.execute('SELECT COUNT(*) as count FROM investments WHERE category_id = ?', (id,)).fetchone()
    
    if investments['count'] > 0:
        flash('Cannot delete category that is in use', 'danger')
    else:
        conn.execute('DELETE FROM investment_categories WHERE id = ?', (id,))
        conn.commit()
        flash('Investment category deleted successfully', 'success')
    
    conn.close()
    
    return redirect(url_for('investment_categories'))

@app.route('/goals', methods=['GET', 'POST'])
def goals():
    """Manage financial goals"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    conn = get_db_connection()
    
    # Handle form submission for adding a new goal
    if request.method == 'POST':
        action = request.form.get('action', 'add_goal')
        
        if action == 'add_goal':
            name = request.form['name']
            target_amount = float(request.form['target_amount'])
            current_amount = float(request.form.get('current_amount', 0))
            
            conn.execute(
                'INSERT INTO goals (name, target_amount, current_amount) VALUES (?, ?, ?)',
                (name, target_amount, current_amount)
            )
            conn.commit()
            
            flash('Goal added successfully', 'success')
            return redirect(url_for('goals'))
    
    # Get all goals
    goals = conn.execute('SELECT * FROM goals ORDER BY date_created DESC').fetchall()
    
    # Calculate progress percentage for each goal
    goals_with_progress = []
    for goal in goals:
        progress = (goal['current_amount'] / goal['target_amount'] * 100) if goal['target_amount'] > 0 else 0
        goals_with_progress.append({
            'id': goal['id'],
            'name': goal['name'],
            'target_amount': goal['target_amount'],
            'current_amount': goal['current_amount'],
            'date_created': goal['date_created'],
            'progress': progress,
            'remaining': goal['target_amount'] - goal['current_amount']
        })
    
    conn.close()
    
    return render_template('goals.html', goals=goals_with_progress)

@app.route('/goals/update/<int:id>', methods=['POST'])
def update_goal(id):
    """Update a financial goal"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    name = request.form.get('name')
    target_amount = request.form.get('target_amount')
    current_amount = request.form.get('current_amount')
    
    update_fields = []
    params = []
    
    if name:
        update_fields.append('name = ?')
        params.append(name)
    
    if target_amount:
        update_fields.append('target_amount = ?')
        params.append(float(target_amount))
    
    if current_amount:
        update_fields.append('current_amount = ?')
        params.append(float(current_amount))
    
    if update_fields:
        conn = get_db_connection()
        query = f"UPDATE goals SET {', '.join(update_fields)} WHERE id = ?"
        params.append(id)
        conn.execute(query, params)
        conn.commit()
        conn.close()
        
        flash('Goal updated successfully', 'success')
    
    return redirect(url_for('goals'))

@app.route('/goals/delete/<int:id>', methods=['POST'])
def delete_goal(id):
    """Delete a financial goal"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = get_user_id(session['username'])
    
    conn = get_db_connection()
    conn.execute('DELETE FROM goals WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Goal deleted successfully', 'success')
    return redirect(url_for('goals'))

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    """Handle password change"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        # Verify that new password and confirmation match
        if new_password != confirm_password:
            flash('A nova senha e a confirmação não coincidem', 'danger')
            return redirect(url_for('change_password'))
        
        # Get user from database
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', 
                           (session['username'],)).fetchone()
        
        # Verify current password
        if not check_password_hash(user['password'], current_password):
            conn.close()
            flash('Senha atual incorreta', 'danger')
            return redirect(url_for('change_password'))
        
        # Hash the new password
        hashed_password = generate_password_hash(new_password)
        
        # Update password in database
        conn.execute('UPDATE users SET password = ? WHERE username = ?', 
                    (hashed_password, session['username']))
        conn.commit()
        conn.close()
        
        flash('Senha alterada com sucesso', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('change_password.html')

# Run the application
if __name__ == '__main__':
    app.run(debug=True)
