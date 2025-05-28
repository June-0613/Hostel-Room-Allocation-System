from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

app = Flask(__name__)
app.secret_key = 'project'  # Change this

# MySQL Connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="DDkavitha@36",  # your MySQL password
    database="hostel_management"  # your database name
)
cursor = db.cursor(dictionary=True)

# ============================
# Home Page
# ============================
@app.route('/')
def home():
    return render_template('home.html')

# ============================
# Student Signup
# ============================
@app.route('/stu_signup', methods=['GET', 'POST'])
def stu_signup():
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')  # Make sure this matches your form field name
            phone = request.form.get('phone')
            year = request.form.get('year')
            branch = request.form.get('branch')

            # Validate required fields
            if not all([name, email, password, phone, year, branch]):
                flash("All fields are required")
                return redirect('/stu_signup')

            # Hash the password
            hashed_pw = generate_password_hash(password)

            # Insert into database
            cursor.execute("""
                INSERT INTO students (name, email, password, phone, year, branch) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, email, hashed_pw, phone, year, branch))
            db.commit()
            
            flash("Registration successful! Please login.")
            return redirect('/stu_login')
            
        except Exception as e:
            db.rollback()
            flash(f"Registration failed: {str(e)}")
            return redirect('/stu_signup')
    
    return render_template('stu_signup.html')

# ============================
# Student Login
# ============================
@app.route('/stu_login', methods=['GET', 'POST'])
def stu_login():
    if request.method == 'POST':
        try:
            # Get form data safely
            email = request.form.get('email')
            password = request.form.get('password')
            
            # Validate required fields
            if not email or not password:
                flash("Email and password are required")
                return redirect('/stu_login')
            
            # Check if student exists
            cursor.execute("SELECT * FROM students WHERE email=%s", (email,))
            student = cursor.fetchone()
            
            if student and check_password_hash(student['password'], password):
                session['student_id'] = student['id']
                flash("Login successful!")
                return redirect('/stu_dash')
            else:
                flash("Invalid email or password")
                return redirect('/stu_login')
                
        except Exception as e:
            flash("An error occurred during login")
            print(f"Login error: {str(e)}")  # For debugging
            return redirect('/stu_login')
    
    return render_template('stu_login.html')


# ============================
# Student Forgot Password
# ============================
@app.route('/spassword', methods=['GET', 'POST'])
def spassword():
    if request.method == 'POST':
        email = request.form['email']
        new_password = request.form['new_password']
        cursor.execute("UPDATE students SET password=%s WHERE email=%s", (new_password, email))
        db.commit()
        return redirect('stu_login')
    return render_template('spassword.html')

# ============================
# Student Dashboard
# ============================
@app.route('/stu_dash')
def stu_dash():
    if 'student_id' not in session:
        return redirect('/stu_login')

    sid = session['student_id']
    cursor.execute("SELECT s.*, r.room_number FROM students s LEFT JOIN rooms r ON s.room_id = r.id WHERE s.id=%s", (sid,))
    student = cursor.fetchone()
    return render_template('stu_dash.html', student=student)

# ============================
# Admin Signup
# ============================
@app.route('/adm_sign', methods=['GET', 'POST'])
def adm_sign():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        cursor.execute("INSERT INTO admins (name, email, password) VALUES (%s, %s, %s)", (name, email, password))
        db.commit()
        return redirect('/adm_login')
    return render_template('adm_sign.html')

# ============================
# Admin Login
# ============================
@app.route('/adm_login', methods=['GET', 'POST'])
def adm_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor.execute("SELECT * FROM admins WHERE email=%s AND password=%s", (email, password))
        admin = cursor.fetchone()
        if admin:
            session['admin_id'] = admin['id']
            return redirect('/adm_dash')
        else:
            flash("Invalid admin credentials")
    return render_template('adm_login.html')

# ============================
# Admin Forgot Password
# ============================
@app.route('/adm_pw', methods=['GET', 'POST'])
def adm_pw():
    if request.method == 'POST':
        email = request.form['email']
        new_password = request.form['new_password']
        cursor.execute("UPDATE admins SET password=%s WHERE email=%s", (new_password, email))
        db.commit()
        return redirect('/adm_login')
    return render_template('adm_pw.html')

# ============================
# Admin Dashboard
# ============================
@app.route('/adm_dash')
def adm_dash():
    if 'admin_id' not in session:
        return redirect('/adm_login')

    cursor.execute("SELECT COUNT(*) AS available FROM rooms WHERE is_occupied = FALSE")
    available_rooms = cursor.fetchone()['available']

    cursor.execute("SELECT COUNT(*) AS total FROM rooms")
    total_rooms = cursor.fetchone()['total']

    return render_template('adm_dash.html', available_rooms=available_rooms, total_rooms=total_rooms)

# ============================
# Rooms Page
# ============================
@app.route('/rooms')
def rooms():
    cursor.execute("SELECT * FROM rooms")
    rooms = cursor.fetchall()
    return render_template('rooms.html', rooms=rooms)

# ============================
# Feedbacks Page
# ============================
@app.route('/feedbacks', methods=['GET', 'POST'])
def feedbacks():
    if request.method == 'POST':
        name = request.form['name']
        message = request.form['message']
        cursor.execute("INSERT INTO feedbacks (name, message) VALUES (%s, %s)", (name, message))
        db.commit()
        return redirect('/feedbacks')

    cursor.execute("SELECT * FROM feedbacks ORDER BY id DESC")
    feedbacks = cursor.fetchall()
    return render_template('feedbacks.html', feedbacks=feedbacks)

#add admin page
from flask import request, redirect, url_for, flash

@app.route('/add_admin', methods=['POST'])
def add_admin():
    name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']
    password = request.form['password']  # Optional: hash it

    try:
        query = "INSERT INTO admins (name, email, phone, password) VALUES (%s, %s, %s, %s)"
        values = (name, email, phone, password)
        cursor.execute(query, values)
        db.commit()

        flash("Admin added successfully!", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for('admin_dashboard'))




# ============================
# Logout
# ============================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ============================
# Main
# ============================
if __name__ == '__main__':
    app.run(debug=True)
