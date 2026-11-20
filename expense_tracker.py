import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from models import User
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy import func, or_
from models import User, Transaction, Budget
from datetime import datetime, date
from collections import defaultdict
from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel



load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or 'ExpenseTracker_Rohan_2026@Secure#9281'

database_url = os.getenv('DATABASE_URL')

if database_url and database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    return redirect(url_for('login'))

# Registration


@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash('All fields are required!', 'error')
            return redirect(url_for('register'))

        if len(password) < 8:
            flash('Password must be at least 8 characters!', 'error')
            return redirect(url_for('register'))

        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            flash('Username or Email already exists!', 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        new_user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# Login


@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session.clear()
            session['user_id'] = user.id
            session['username'] = user.username

            return redirect(url_for('dashboard'))

        flash('Invalid email or password!', 'error')

    return render_template('login.html')





@app.route('/my_profile', methods=['GET', 'POST'])
def my_profile():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get_or_404(session['user_id'])

    if request.method == 'POST':

        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()

        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')

        if not username or not email:
            flash('Username and email are required.', 'error')
            return redirect(url_for('my_profile'))

        # Check duplicate username
        existing_username = User.query.filter(
            User.username == username,
            User.id != user.id
        ).first()

        if existing_username:
            flash('Username already exists.', 'error')
            return redirect(url_for('my_profile'))

        # Check duplicate email
        existing_email = User.query.filter(
            User.email == email,
            User.id != user.id
        ).first()

        if existing_email:
            flash('Email already exists.', 'error')
            return redirect(url_for('my_profile'))

        # Change password if requested
        if new_password:

            if not check_password_hash(user.password, current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('my_profile'))

            if len(new_password) < 8:
                flash('New password must be at least 8 characters.', 'error')
                return redirect(url_for('my_profile'))

            user.password = generate_password_hash(new_password)

        user.username = username
        user.email = email

        db.session.commit()

        flash('Profile updated successfully!', 'success')

        return redirect(url_for('my_profile'))

    return render_template('my_profile.html', user=user)




# Dashboard


@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Calculate Total Income
    total_income = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == user_id,
        func.lower(Transaction.transaction_type) == 'income'
    ).scalar()

    # Calculate Total Expenses
    total_expenses = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == user_id,
        func.lower(Transaction.transaction_type) == 'expense'
    ).scalar()

    # Calculate Balance
    total_balance = total_income - total_expenses

    # Get Recent Transactions
    recent_transactions = Transaction.query.filter_by(
        user_id=user_id
    ).order_by(
        Transaction.date.desc()
    ).limit(5).all()

    return render_template(
        'dashboard.html',
        total_income=total_income,
        total_expenses=total_expenses,
        total_balance=total_balance,
        recent_transactions=recent_transactions
    )


# Add Transaction


@app.route('/add-transaction', methods=['GET', 'POST'])
def add_transaction():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':

        transaction_type = request.form.get('transaction_type', '').strip().lower()
        category = request.form.get('category', '').strip()
        amount = request.form.get('amount', '').strip()
        description = request.form.get('description', '').strip()
        transaction_date = request.form.get('date', '').strip()

        # Validate required fields
        if not transaction_type or not category or not amount:
            flash('Please fill all required fields!', 'error')
            return redirect(url_for('add_transaction'))

        if transaction_type not in ['income', 'expense']:
            flash('Invalid transaction type!', 'error')
            return redirect(url_for('add_transaction'))

        try:
            amount = float(amount)

            if amount <= 0:
                flash('Amount must be greater than zero!', 'error')
                return redirect(url_for('add_transaction'))

            if transaction_date:
                transaction_date = datetime.strptime(
                    transaction_date, '%Y-%m-%d'
                )
            else:
                transaction_date = datetime.utcnow()

        except ValueError:
            flash('Please enter a valid amount and date!', 'error')
            return redirect(url_for('add_transaction'))

        new_transaction = Transaction(
            user_id=session['user_id'],
            transaction_type=transaction_type,
            category=category,
            amount=amount,
            description=description,
            date=transaction_date
        )

        try:
            db.session.add(new_transaction)
            db.session.commit()

            flash('Transaction added successfully!', 'success')
            return redirect(url_for('dashboard'))

        except Exception:
            db.session.rollback()
            flash('Something went wrong. Please try again!', 'error')
            return redirect(url_for('add_transaction'))

    return render_template('add_transaction.html')




@app.route('/import_excel', methods=['GET', 'POST'])
def import_excel():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'GET':
        return render_template('import_excel.html')

    file = request.files.get('excel_file')

    if not file or file.filename == '':
        flash('Please select an Excel file.', 'error')
        return redirect(url_for('import_excel'))

    if not file.filename.lower().endswith(('.xlsx', '.xlsm')):
        flash('Please upload a valid Excel file.', 'error')
        return redirect(url_for('import_excel'))

    try:
        workbook = load_workbook(file, data_only=True)
        sheet = workbook.active

        imported_count = 0

        for row in sheet.iter_rows(min_row=2, values_only=True):

            if not row or len(row) < 3:
                continue

            transaction_type = row[0]
            category = row[1]
            amount = row[2]
            date_value = row[3] if len(row) > 3 else None
            description = row[4] if len(row) > 4 else None

            if not transaction_type or not category or amount is None:
                continue

            transaction_type = str(transaction_type).strip().lower()
            category = str(category).strip()

            if transaction_type not in ['income', 'expense']:
                continue

            # Amount Validation
            try:
                amount = float(amount)

                if amount <= 0:
                    continue

            except (ValueError, TypeError):
                continue

            # Date Conversion
            try:

                if isinstance(date_value, datetime):
                    transaction_date = date_value

                elif isinstance(date_value, date):
                    transaction_date = datetime.combine(
                        date_value, datetime.min.time()
                    )

                elif isinstance(date_value, (int, float)):
                    transaction_date = from_excel(
                        date_value, workbook.epoch
                    )

                    if not isinstance(transaction_date, datetime):
                        continue

                elif date_value is not None and str(date_value).strip():

                    date_string = str(date_value).strip()

                    date_formats = [
                        '%d-%m-%Y',
                        '%d/%m/%Y',
                        '%d-%m-%y',
                        '%d/%m/%y',
                        '%Y-%m-%d',
                        '%Y/%m/%d'
                    ]

                    transaction_date = None

                    for fmt in date_formats:
                        try:
                            transaction_date = datetime.strptime(
                                date_string, fmt
                            )
                            break
                        except ValueError:
                            continue

                    if transaction_date is None:
                        continue

                else:
                    transaction_date = datetime.utcnow()

            except (ValueError, TypeError, OverflowError):
                continue

            # Create Transaction
            new_transaction = Transaction(
                user_id=session['user_id'],
                transaction_type=transaction_type,
                category=category,
                amount=amount,
                description=str(description).strip()[:255]
                if description else '',
                date=transaction_date
            )

            db.session.add(new_transaction)
            imported_count += 1

        if imported_count == 0:

            db.session.rollback()

            flash(
                'No valid transactions found in Excel file.',
                'error'
            )

        else:

            db.session.commit()

            flash(
                f'{imported_count} transactions imported successfully!',
                'success'
            )

        workbook.close()

    except Exception as e:

        db.session.rollback()

        print("Excel Import Error:", e)

        flash(
            'Error importing Excel file.',
            'error'
        )

    return redirect(url_for('my_transactions'))



# @app.route('/import_excel', methods=['POST'])
# def import_excel():

#     if 'user_id' not in session:
#         return redirect(url_for('login'))

#     file = request.files.get('excel_file')

#     if not file or file.filename == '':
#         flash('Please select an Excel file.', 'error')
#         return redirect(url_for('add_transaction'))

#     if not file.filename.lower().endswith(('.xlsx', '.xlsm')):
#         flash('Please upload a valid Excel file.', 'error')
#         return redirect(url_for('add_transaction'))

#     try:
#         workbook = load_workbook(file, data_only=True)
#         sheet = workbook.active

#         imported_count = 0

#         for row in sheet.iter_rows(min_row=2, values_only=True):

#             transaction_type, category, amount, date, description = (
#                 list(row[:5]) + [None] * max(0, 5 - len(row))
#             )[:5]

#             if not all([transaction_type, category, amount]):
#                 continue

#             transaction_type = str(transaction_type).strip().lower()
#             category = str(category).strip()

#             if transaction_type not in ['income', 'expense']:
#                 continue

#             try:
#                 amount = float(amount)
#                 if amount <= 0:
#                     continue
#             except (ValueError, TypeError):
#                 continue

#             if isinstance(date, datetime):
#                 transaction_date = date
#             elif date:
#                 try:
#                     transaction_date = datetime.strptime(
#                         str(date).strip(), '%Y-%m-%d'
#                     )
#                 except ValueError:
#                     continue
#             else:
#                 transaction_date = datetime.utcnow()

#             new_transaction = Transaction(
#                 user_id=session['user_id'],
#                 transaction_type=transaction_type,
#                 category=category,
#                 amount=amount,
#                 description=str(description).strip()[:255] if description else '',
#                 date=transaction_date
#             )

#             db.session.add(new_transaction)
#             imported_count += 1

#         if imported_count == 0:
#             db.session.rollback()
#             flash('No valid transactions found in Excel file.', 'error')
#         else:
#             db.session.commit()
#             flash(
#                 f'{imported_count} transactions imported successfully!',
#                 'success'
#             )

#     except Exception as e:
#         db.session.rollback()
#         print("Excel Import Error:", e)
#         flash('Error importing Excel file.', 'error')

#     return redirect(url_for('my_transactions'))



# My Transactions

@app.route('/my-transactions')
def my_transactions():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Total Transactions
    total_transactions = Transaction.query.filter_by(
        user_id=user_id
    ).count()

    # Total Income
    total_income = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == user_id,
        func.lower(Transaction.transaction_type) == 'income'
    ).scalar()

    # Total Expenses
    total_expenses = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == user_id,
        func.lower(Transaction.transaction_type) == 'expense'
    ).scalar()

    # Search and Filter
    search = request.args.get('search', '').strip()
    transaction_type = request.args.get('type', 'all').lower()

    query = Transaction.query.filter_by(user_id=user_id)

    if transaction_type in ['income', 'expense']:
        query = query.filter(
            func.lower(Transaction.transaction_type) == transaction_type
        )

    if search:
        search_term = f"%{search}%"

        query = query.filter(
            or_(
                Transaction.category.ilike(search_term),
                Transaction.description.ilike(search_term),
                Transaction.transaction_type.ilike(search_term)
            )
        )

    transactions = query.order_by(
        Transaction.date.desc()
    ).all()

    return render_template(
        'my_transactions.html',
        transactions=transactions,
        total_transactions=total_transactions,
        total_income=total_income,
        total_expenses=total_expenses,
        search=search,
        selected_type=transaction_type
    )



# Reports

@app.route('/reports')
def reports():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Get all user transactions
    transactions = Transaction.query.filter_by(
        user_id=user_id
    ).order_by(Transaction.date.asc()).all()

    total_income = 0
    total_expenses = 0

    monthly_data = defaultdict(
        lambda: {'income': 0, 'expense': 0}
    )

    category_data = defaultdict(float)

    # Process Transactions
    for transaction in transactions:

        amount = float(transaction.amount)
        transaction_type = transaction.transaction_type.lower()

        month_key = transaction.date.strftime('%Y-%m')
        month_label = transaction.date.strftime('%b %Y')

        if transaction_type == 'income':

            total_income += amount
            monthly_data[month_key]['income'] += amount

        elif transaction_type == 'expense':

            total_expenses += amount
            monthly_data[month_key]['expense'] += amount

            category_data[transaction.category] += amount

    total_balance = total_income - total_expenses

    # Monthly Chart Data
    monthly_labels = []
    monthly_income = []
    monthly_expenses = []

    for month_key in sorted(monthly_data):

        month_label = datetime.strptime(
            month_key, '%Y-%m'
        ).strftime('%b %Y')

        monthly_labels.append(month_label)

        monthly_income.append(
            round(monthly_data[month_key]['income'], 2)
        )

        monthly_expenses.append(
            round(monthly_data[month_key]['expense'], 2)
        )

    # Category Chart Data
    category_labels = list(category_data.keys())

    category_amounts = [
        round(amount, 2)
        for amount in category_data.values()
    ]

    return render_template(
        'reports.html',
        total_income=total_income,
        total_expenses=total_expenses,
        total_balance=total_balance,
        monthly_labels=monthly_labels,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        category_labels=category_labels,
        category_amounts=category_amounts
    )




# =========================================
# BUDGET MANAGEMENT
# =========================================

@app.route('/budget')
def budget():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    today = datetime.utcnow()
    year = today.year
    month = today.month

    # Get Current Month Budget
    current_budget = Budget.query.filter_by(
        user_id=user_id,
        year=year,
        month=month
    ).first()

    # Calculate Current Month Expenses
    monthly_expenses = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == user_id,
        func.lower(Transaction.transaction_type) == 'expense',
        func.extract('year', Transaction.date) == year,
        func.extract('month', Transaction.date) == month
    ).scalar()

    budget_amount = float(current_budget.amount) if current_budget else 0
    total_expenses = float(monthly_expenses)

    remaining_budget = budget_amount - total_expenses

    if budget_amount > 0:
        budget_percentage = (total_expenses / budget_amount) * 100
    else:
        budget_percentage = 0

    budget_percentage = round(budget_percentage, 2)

    # Budget History
    budget_history = Budget.query.filter_by(
        user_id=user_id
    ).order_by(
        Budget.year.desc(),
        Budget.month.desc()
    ).all()

    return render_template(
        'budget.html',
        current_budget=current_budget,
        budget_amount=budget_amount,
        total_expenses=total_expenses,
        remaining_budget=remaining_budget,
        budget_percentage=budget_percentage,
        budget_history=budget_history
    )


# Set Budget

@app.route('/set-budget', methods=['POST'])
def set_budget():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        amount = float(request.form.get('amount', 0))

        if amount <= 0:
            flash('Budget must be greater than zero!', 'error')
            return redirect(url_for('budget'))

        today = datetime.utcnow()

        existing_budget = Budget.query.filter_by(
            user_id=session['user_id'],
            year=today.year,
            month=today.month
        ).first()

        if existing_budget:
            existing_budget.amount = amount
            flash('Monthly budget updated successfully!', 'success')

        else:
            new_budget = Budget(
                user_id=session['user_id'],
                year=today.year,
                month=today.month,
                amount=amount
            )

            db.session.add(new_budget)
            flash('Monthly budget set successfully!', 'success')

        db.session.commit()

    except ValueError:
        flash('Please enter a valid budget amount!', 'error')

    except Exception:
        db.session.rollback()
        flash('Something went wrong!', 'error')

    return redirect(url_for('budget'))


# Delete Budget

@app.route('/delete-budget/<int:budget_id>', methods=['POST'])
def delete_budget(budget_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    selected_budget = Budget.query.filter_by(
        id=budget_id,
        user_id=session['user_id']
    ).first_or_404()

    db.session.delete(selected_budget)
    db.session.commit()

    flash('Budget deleted successfully!', 'success')

    return redirect(url_for('budget'))




# =========================================
# EDIT TRANSACTION
# =========================================

@app.route('/edit-transaction/<int:transaction_id>', methods=['GET', 'POST'])
def edit_transaction(transaction_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=session['user_id']
    ).first_or_404()

    if request.method == 'POST':

        transaction_type = request.form.get('transaction_type', '').strip().lower()
        category = request.form.get('category', '').strip()
        amount = request.form.get('amount', '').strip()
        description = request.form.get('description', '').strip()
        transaction_date = request.form.get('date', '').strip()

        if not transaction_type or not category or not amount:
            flash('Please fill all required fields!', 'error')
            return redirect(url_for('edit_transaction', transaction_id=transaction.id))

        if transaction_type not in ['income', 'expense']:
            flash('Invalid transaction type!', 'error')
            return redirect(url_for('edit_transaction', transaction_id=transaction.id))

        try:
            amount = float(amount)

            if amount <= 0:
                flash('Amount must be greater than zero!', 'error')
                return redirect(url_for('edit_transaction', transaction_id=transaction.id))

            if transaction_date:
                transaction_date = datetime.strptime(
                    transaction_date, '%Y-%m-%d'
                )

            else:
                transaction_date = transaction.date

            transaction.transaction_type = transaction_type
            transaction.category = category
            transaction.amount = amount
            transaction.description = description
            transaction.date = transaction_date

            db.session.commit()

            flash('Transaction updated successfully!', 'success')
            return redirect(url_for('my_transactions'))

        except ValueError:
            db.session.rollback()
            flash('Please enter valid transaction details!', 'error')

        except Exception:
            db.session.rollback()
            flash('Something went wrong. Please try again!', 'error')

    return render_template(
        'edit_transaction.html',
        transaction=transaction
    )


# =========================================
# DELETE TRANSACTION
# =========================================

@app.route('/delete-transaction/<int:transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=session['user_id']
    ).first_or_404()

    try:
        db.session.delete(transaction)
        db.session.commit()

        flash('Transaction deleted successfully!', 'success')

    except Exception:
        db.session.rollback()
        flash('Unable to delete transaction!', 'error')

    return redirect(url_for('my_transactions'))





@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':

    with app.app_context():
        db.create_all()

    app.run(debug=True, use_reloader=False)
