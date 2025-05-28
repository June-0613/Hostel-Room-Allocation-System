from flask import Flask, render_template, request, redirect, url_for, flash, session
import MySQLdb 
from flask_mail import Message
import csv
import os
from flask_mail import Mail
mail=Mail()
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
from utils import mysql
from functools import wraps
from dotenv import load_dotenv
load_dotenv()
from utils.room_alloc import allocate_rooms
from utils.csv_parser import parse_student_csv, parse_excel_file
from utils.email_ver import (
    generate_verification_token,
    confirm_verification_token,
    send_verification_email
)  # If used

app = Flask(__name__)
app.config.from_object(Config)
mail.init_app(app)
app.secret_key = 'hostel_management@0613'

def verify_db_connection():
    global db
    try:
        db.ping(True)  # reconnect if connection is lost
    except Exception as e:
        print(f"Database connection error: {e}")

db = MySQLdb.connect(
    host="localhost",
    user="root",
    passwd="DDkavitha@36",
    db="hostel_management",
)
cursor = db.cursor()


# ---------- Helpers ----------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print("DEBUG: Session contents:", session)  # Debug print
        if 'admin_id' not in session:
            print("DEBUG: Redirecting to login - no admin_id in session")
            flash('Please login as admin', 'warning')
            return redirect(url_for('adm_login'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('student_login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- Routes ----------
@app.route('/')
def home():
    return render_template('home1.html')

# ---------- Admin ----------
@app.route('/adm_login', methods=['GET', 'POST'])
def adm_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            cursor = db.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT admin_id, username, password_hash FROM admins WHERE username = %s", (username,))
            admin = cursor.fetchone()
            cursor.close()

            if admin and check_password_hash(admin['password_hash'], password):
                session.clear()
                session['admin_username'] = admin['username']
                session['admin_id'] = admin['admin_id']
                session['logged_in'] = True
                session.permanent = True

                print(f"DEBUG: Session after login - {session}")
                return redirect(url_for('adm_dash'))

            flash('Invalid username or password', 'danger')
        except Exception as e:
            print(f"Database error: {e}")
            flash('Login error. Please try again.', 'danger')

        return redirect(url_for('adm_login'))

    return render_template('adm_login.html')

import traceback
@app.route('/adm_dash')
def adm_dash():
    print(f"DEBUG: Checking session - {session}")  # Debug print
    
    # More comprehensive session check
    if 'admin_username'not in session or not session.get('logged_in'):
        flash('Please log in to access the dashboard', 'warning')
        return redirect(url_for('adm_login'))

    try:
        with db.cursor(MySQLdb.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT username, email, phone, created_at 
                FROM admins 
                WHERE admin_id = %s
            """, (session['admin_id'],))
            admin_data = cursor.fetchone()

        if not admin_data:
            flash('Admin account not found', 'danger')
            return redirect(url_for('adm_login'))

        admin = {
            'name': admin_data['username'],
            'email': admin_data['email'],
            'phone': admin_data.get('phone', 'N/A'),
            'last_login': admin_data.get('created_at', 'Not Available')
        }

        return render_template('adm_dash.html', admin=admin)
    except Exception as e:
        print(f"Error in adm_dash: {str(e)}")
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('adm_login'))

@app.route('/adm_logout')
def adm_logout():
    session.pop('admin', None)
    return redirect(url_for('home'))

from itsdangerous import URLSafeTimedSerializer

serializer = URLSafeTimedSerializer(app.secret_key)


def send_admin_reset_email(to_email, token):
    reset_url = url_for('admin_reset_password', token=token, _external=True)
    msg = Message(
        subject="Admin Password Reset",
        recipients=[to_email],
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    msg.body = f"""Hello Admin,

You requested a password reset. Click the link below to reset your password:

{reset_url}

If you didn't request this, please ignore this message.

- Hostel Management System
"""
    current_app.extensions['mail'].send(msg)


@app.route('/admin/forgot-password', methods=['GET', 'POST'])
def admin_forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        cursor = db.cursor()
        cursor.execute("SELECT * FROM admin WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            token = serializer.dumps(email, salt='admin-password-reset')
            send_admin_reset_email(email, token)
            flash('Check your email for a password reset link.', 'success')
        else:
            flash('No account found with that email.', 'error')

        return redirect(url_for('admin_forgot_password'))

    return render_template('adm_pw.html')

@app.route('/admin/reset-password/<token>', methods=['GET', 'POST'])
def admin_reset_password(token):
    try:
        email = serializer.loads(token, salt='admin-password-reset', max_age=3600)
    except Exception:
        flash('The reset link is invalid or has expired.', 'error')
        return redirect(url_for('admin_forgot_password'))

    if request.method == 'POST':
        new_password = request.form['password']
        cursor = db.cursor()
        cursor.execute("UPDATE admin SET password = %s WHERE email = %s", (new_password, email))
        db.commit()
        flash('Your password has been updated successfully!', 'success')
        return redirect(url_for('admin_login'))

    return render_template('admin_reset_password.html')


@app.route('/add_admin', methods=['GET', 'POST'])
@admin_required
def add_admin():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone']
        password = generate_password_hash(request.form['password'])
        cursor = db.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("INSERT INTO admins (username, email, password_hash, created_at) VALUES (%s, %s, %s, %s)",
                       (username, email, password, datetime.datetime.now()))
        db.commit()
        flash("Admin added successfully!", "success")
        return redirect(url_for('adm_dash'))
    return render_template('adm_add.html')

@app.route('/allocate_rooms', methods=['POST'])
@admin_required
def allocate_rooms_route():
    try:
        allocate_rooms()
        flash("Room allocation completed successfully.", "success")
    except Exception as e:
        print("Error:", e)
        flash("An error occurred during room allocation.", "danger")
    return redirect(url_for('adm_rooms'))

@app.route('/adm_rooms')
@admin_required
def adm_rooms():
    try:
        with db.cursor(MySQLdb.cursors.DictCursor) as cursor:
            # Get all rooms with calculated status
            cursor.execute("""
                SELECT 
                    room_id,
                    room_number,
                    capacity,
                    occupied,
                    CASE 
                        WHEN occupied = 0 THEN 'empty'
                        WHEN occupied >= capacity THEN 'full'
                        ELSE 'partial'
                    END AS status
                FROM rooms
                ORDER BY room_number
            """)
            rooms = cursor.fetchall()
            
        return render_template('adm_rooms.html', rooms=rooms)
        
    except Exception as e:
        flash(f"Error loading rooms: {str(e)}", "danger")
        return redirect(url_for('adm_dash'))

@app.route('/adm_rc')
@admin_required
def adm_rc():
    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT cr.*, s.name, s.email FROM change_requests cr 
        JOIN students s ON cr.student_id = s.student_id
        ORDER BY cr.id DESC
    """)
    requests = cursor.fetchall()
    cursor.close()
    return render_template('adm_rc.html', requests=requests)

from utils.email_ver import send_change_request_email
@app.route('/adm_rc_action/<int:request_id>/<action>', methods=['POST'])
@admin_required
def adm_rc_action(request_id, action):
    cursor = db.cursor()
    # Only allow approve or reject
    if action not in ('approve', 'reject'):
        flash('Invalid action', 'danger')
        return redirect(url_for('adm_rc'))

    # Fetch the request to get student info
    cursor.execute("SELECT * FROM change_requests WHERE id=%s", (request_id,))
    req = cursor.fetchone()
    if not req:
        flash('Request not found', 'danger')
        return redirect(url_for('adm_rc'))

    new_status = 'approved' if action == 'approve' else 'rejected'

    try:
        # Update the request status
        cursor.execute("UPDATE change_requests SET status=%s WHERE id=%s", (new_status, request_id))

        if new_status == 'approved':
            # Also update student's room_number to desired_room
            cursor.execute("""
                UPDATE students SET room_number=%s WHERE student_id=%s
            """, (req['desired_room'], req['student_id']))

        db.commit()

        # Send email notification (see below)
        send_change_request_email(
        to=req['email'],
        student_name=req['name'],
        old_room=req['current_room'],
        new_room=req['desired_room'],
        approved=(new_status == 'approved')
        )

        flash(f'Request {new_status} successfully.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating request: {str(e)}', 'danger')

    return redirect(url_for('adm_rc'))


@app.route('/view_students')
@admin_required
def view_students():
    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM students ORDER BY year")
    students = cursor.fetchall()

    grouped_students = {}
    for student in students:
        year = student['year']
        branch = student['branch']

        if year not in grouped_students:
            grouped_students[year] = {}
        if branch not in grouped_students[year]:
            grouped_students[year][branch] = []

        grouped_students[year][branch].append(student)

    return render_template('view_students.html', grouped_students=grouped_students)

from flask import request, redirect, url_for, render_template, flash
from werkzeug.utils import secure_filename
import pandas as pd

@app.route('/adm_upload', methods=['GET', 'POST'])
def adm_upload():
    if request.method == 'POST':
        file = request.files.get('csv_file')
        
        # ✅ Ensure a file is selected
        if not file or file.filename.strip() == '':
            flash('No file selected for uploading.', 'danger')
            return redirect(url_for('adm_upload'))

        filename = secure_filename(file.filename)

        try:
            if filename.endswith('.xlsx') or filename.endswith('.xls'):
                df = pd.read_excel(file)
            elif filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                flash('Invalid file type. Please upload a CSV or Excel file.', 'danger')
                return redirect(url_for('adm_upload'))

            required_columns = {'admission_no', 'name'}
            if not required_columns.issubset(df.columns):
                flash(f'Missing columns! Required: {required_columns}', 'danger')
                return redirect(url_for('adm_upload'))

            # Insert each row into the freshers_list
            inserted_count = 0
            for index, row in df.iterrows():
                admission_no = str(row['admission_no']).strip()
                name = str(row['name']).strip()

                # Optional: avoid duplicates
                cursor.execute("SELECT * FROM freshers_list WHERE admission_no = %s", (admission_no,))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO freshers_list (admission_no, name) VALUES (%s, %s)", (admission_no, name))
                    inserted_count += 1

            db.commit()

            # ✅ Temporary: check if data loaded
            print(df.head())

            flash('File uploaded and processed successfully!', 'success')

        except Exception as e:
            flash(f'Excel processing failed: {str(e)}', 'danger')

        return redirect(url_for('adm_upload'))

    return render_template('adm_upload.html')



@app.route('/adm_upload')
def show_upload_form():
    session['_token'] = os.urandom(16).hex()  # Generate simple token
    return render_template('adm_upload.html', token=session['_token'])

@app.route('/test_upload', methods=['GET', 'POST'])
def test_upload():
    if request.method == 'POST':
        print("\nReceived file:", request.files)
        return "File received! Check your console"
    return '''
    <form method=post enctype=multipart/form-data>
      <input type=file name=csv_file>
      <button>Test Upload</button>
    </form>
    '''

from utils.room_alloc import allocate_student,_finalize_allocation,allocate_rooms

@app.route('/approve_application/<int:application_id>', methods=['POST'])
@admin_required
def approve_application(application_id):
    try:
        cursor = db.cursor(MySQLdb.cursors.DictCursor)

        # Fetch application and student details
        cursor.execute("""
            SELECT a.*, s.priority, s.preferences 
            FROM applications a
            JOIN students s ON a.admission_no = s.admission_no
            WHERE a.application_id = %s
        """, (application_id,))
        application = cursor.fetchone()
        print("DEBUG >> Application fetched from DB:", application)
        if not application:
            flash('Application not found', 'danger')
            return redirect(url_for('adm_applications'))

        allocated_room_ids = set()  # If batching, pass from outside
        success, allocated_room = allocate_student(application, cursor, allocated_room_ids)
        print("DEBUG >> Allocation result:", success, allocated_room)
        flash(f'DEBUG >> Allocation result: success={success}, room={allocated_room}', 'info')

        if success and allocated_room:
            db.commit()
            flash(f'Student allocated successfully to Room {allocated_room}!', 'success')
        else:
            db.rollback()
            cursor.execute("""
                UPDATE applications 
                SET status = 'rejected', 
                    remarks = 'No available rooms' 
                WHERE application_id = %s
            """, (application_id,))
            db.commit()
            flash('No available rooms for allocation', 'warning')

    except Exception as e:
        db.rollback()
        flash(f'Allocation failed: {str(e)}', 'danger')
    finally:
        cursor.close()

    return redirect(url_for('view_applications'))



@app.route('/reject_application/<int:application_id>', methods=['POST'])
def reject_application(application_id):
    cursor = db.cursor(MySQLdb.cursors.DictCursor)

    try:
        # Delete the application record completely
        cursor.execute("DELETE FROM applications WHERE application_id = %s", (application_id,))
        
        db.commit()
        flash('Application has been removed.', 'danger')
    except Exception as e:
        db.rollback()
        print(f"Manual rejection error: {e}")
        flash('An error occurred while removing the application.', 'danger')
    finally:
        cursor.close()

    return redirect(url_for('view_applications'))


@app.route('/adm_applications')
@admin_required
def view_applications():
    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM applications")
    applications = cursor.fetchall()
    cursor.close()
    return render_template('adm_applications.html', applications=applications)

# ---------- Students ----------
# app.py (modify the student signup route)
@app.route('/stu_signup', methods=['GET', 'POST'])
def stu_signup():
    if request.method == 'POST':
        admission_no = request.form.get('admission_no')
        if not admission_no:
            return "Admission number is required", 400
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']  # Get phone
        branch = request.form['branch']  # Get branch
        year = request.form['year']
        password = generate_password_hash(request.form['password'])

        # Check admission number
        cursor.execute("SELECT * FROM freshers_list WHERE admission_no = %s", (admission_no,))
        if not cursor.fetchone():
            flash('Invalid admission number.', 'danger')
            return redirect(url_for('stu_signup'))

        # Insert student
        cursor.execute("""
            INSERT INTO students (admission_no, name, email, phone,password_hash,branch,year)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (admission_no, name, email,phone, password,branch,year))
        db.commit()

        # Send verification email
        token = generate_verification_token(email)
        send_verification_email(email, token)
        flash('Verification email sent! Check your inbox.', 'success')
        return redirect(url_for('stu_ver'))  # Show "check email" page

    return render_template('stu_signup.html')

# app.py (add new route)
from flask import request  # make sure you have this imported

@app.route('/verify')
def verify_email():
    token = request.args.get('token')  # get token from query parameter
    if not token:
        flash('Invalid or expired token.', 'danger')
        return redirect(url_for('stu_signup'))

    email = confirm_verification_token(token)
    if not email:
        flash('Invalid or expired token.', 'danger')
        return redirect(url_for('stu_signup'))

    # Update student's verified status
    cursor.execute("""
        UPDATE students SET verified = 1 WHERE email = %s
    """, (email,))
    db.commit()
    flash('Email verified! You can now log in.', 'success')
    return redirect(url_for('student_login'))  # or wherever your login page is

@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT * FROM students WHERE email=%s", (email,))
        result = cursor.fetchone()

        if result and check_password_hash(result[5], password):  # password_hash is at index 5
            student = {
                'student_id': result[0],
                'admission_no': result[1],
                'name': result[2],
                'email': result[3],
                'phone': result[4],
                'branch': result[10],
                'year': result[9],
                'room_number': None  # Add this if you're joining with room table
            }
            session['student'] = student
            print("Session student set:", session['student'])
            return redirect(url_for('stu_dash'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('stu_login.html')

@app.route('/stu_dash')
@student_required
def stu_dash():
    try:
        # Get student ID from session
        student_id = session['student']['student_id']
        
        # 1. Get basic student info
        cursor = db.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM students WHERE student_id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            flash("Student not found", "danger")
            return redirect(url_for('student_login'))

        # 2. Get room allocation if exists
        cursor.execute("""
            SELECT r.room_number, a.allocated_on, a.status 
            FROM allocations a
            JOIN rooms r ON a.room_id = r.room_id  
            WHERE a.student_id = %s AND a.status = 'active'
            ORDER BY a.allocated_on DESC 
            LIMIT 1
        """, (student_id,))
        allocation = cursor.fetchone()
        
        # Add room info to student data
        if allocation:
            student['room_number'] = allocation['room_number']
            student['allocated_on'] = allocation['allocated_on']
            student['status'] = allocation['status']
        else:
            student['room_number'] = None
            student['allocated_on'] = None
            student['status'] = None

        
        print("Session accessed in stu_dash:", session.get('student'))  # Add this

        return render_template('stu_dash.html', student=student)
        
    except Exception as e:
        print("Error in stu_dash():", str(e))
        flash(f"Error loading dashboard: {str(e)}", "danger")
        return redirect(url_for('student_login'))
    finally:
        cursor.close()

@app.route('/apply_room', methods=['GET', 'POST'])
@student_required
def apply_room():
    cursor = db.cursor()  # Use standard cursor
    
    if request.method == 'POST':
        # Get all form data
        admission_no = session['student']['admission_no']
        name = session['student']['name']
        year = session['student']['year']
        room_type = request.form.get('room_type')
        block_pref = request.form.get('block_pref', '')
        specific_room = request.form.get('specific_room', '')
        roommate_pref = request.form.get('roommate_pref', '')
        special_needs = request.form.get('special_needs', '')
        
        # Build preferences string
        preferences = []
        if block_pref:
            preferences.append(f"block:{block_pref}")
        if specific_room:
            preferences.append(f"room:{specific_room}")
        if roommate_pref:
            preferences.append(f"mate:{roommate_pref}")
        
        preferences_str = ','.join(preferences) if preferences else None
        
        try:
            # Insert application
            cursor.execute("""
                INSERT INTO applications 
                (admission_no, student_name, year, requested_room_id, 
                 room_type, preferences, special_needs, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
            """, (
                admission_no, 
                name, 
                year,
                specific_room if specific_room else None,
                room_type,
                preferences_str,
                special_needs
            ))
            db.commit()
            
            flash('Room application submitted successfully!', 'success')
            
        except Exception as e:
            db.rollback()
            flash(f'Application failed: {str(e)}', 'danger')
    
    # GET request - show available rooms
    try:
        cursor.execute("""
            SELECT * FROM rooms 
            WHERE capacity > occupied
            ORDER BY room_number
        """)
        # Convert results to dictionaries manually
        columns = [col[0] for col in cursor.description]
        available_rooms = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        return render_template('apply_room.html', 
                            available_rooms=available_rooms)
    
    except Exception as e:
        flash(f'Error loading rooms: {str(e)}', 'danger')
        return redirect(url_for('stu_dash'))
    finally:
        cursor.close()

@app.route('/change_room', methods=['GET', 'POST'])
@student_required
def change_room():
    cursor = db.cursor()
    admission_no = session['student']['admission_no']
    
    if request.method == 'POST':
        current_room = request.form['current_room']
        desired_room = request.form['new_room_id']  # match form select name
        reason = request.form.get('reason', '')
        
        try:
            cursor.execute("""
                INSERT INTO change_requests (student_roll, current_room, desired_room, reason) 
                VALUES (%s, %s, %s, %s)
            """, (admission_no, current_room, desired_room, reason))
            db.commit()
            flash('Room change request submitted.', 'success')
            return redirect(url_for('stu_dash'))
        except Exception as e:
            db.rollback()
            flash(f'Error submitting request: {str(e)}', 'danger')
    
    # For GET request, fetch current room and available rooms
    try:
        # Get student's current room (fetch from students table)
        cursor.execute("SELECT room_number FROM students WHERE admission_no=%s", (admission_no,))
        current_room = ' '
        
        # Get available rooms (rooms with available capacity)
        cursor.execute("""
            SELECT 
                room_id AS id, 
                room_number AS number, 
                room_type, 
                (capacity - IFNULL(occupied, 0)) AS available_capacity
            FROM rooms
            WHERE capacity > IFNULL(occupied, 0)
            ORDER BY room_number
        """)
        columns = [col[0] for col in cursor.description]
        available_rooms = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        return render_template('change_room.html', current_room=current_room, available_rooms=available_rooms)
    except Exception as e:
        flash(f'Error loading rooms: {str(e)}', 'danger')
        return redirect(url_for('stu_dash'))
    finally:
        cursor.close()



@app.route('/feedbacks', methods=['GET', 'POST'])
def feedbacks():
    if request.method == 'POST':
        # Get name (from form for guests, from session for logged-in students)
        name = request.form.get('name')
        comment = request.form.get('comment')
        
        if not comment:
            flash('Please enter your feedback', 'danger')
            return redirect(url_for('feedbacks'))
            
        try:
            # For logged-in students
            if 'student' in session:
                cursor.execute("""
                    INSERT INTO feedbacks (student_id, name, feedback_text, submitted_on) 
                    VALUES (%s, %s, %s, %s)
                """, (
                    session['student']['student_id'],
                    session['student']['name'],
                    comment,
                    datetime.datetime.now()
                ))
            else:
                # For guests
                if not name:
                    name = "Anonymous"
                cursor.execute("""
                    INSERT INTO feedbacks (name, feedback_text, submitted_on) 
                    VALUES (%s, %s, %s)
                """, (
                    name,
                    comment,
                    datetime.datetime.now()
                ))
            
            db.commit()
            flash('Thank you for your feedback!', 'success')
            return redirect(url_for('feedbacks'))
            
        except Exception as e:
            db.rollback()
            flash(f'Error submitting feedback: {str(e)}', 'danger')
            return redirect(url_for('feedbacks'))

    # GET request - show feedbacks
    try:
        cursor.execute("""
            SELECT 
                COALESCE(s.name, f.name) as display_name,
                f.feedback_text, 
                f.submitted_on,
                CASE WHEN f.student_id IS NOT NULL THEN 'Student' ELSE 'Guest' END as user_type
            FROM feedbacks f
            LEFT JOIN students s ON f.student_id = s.student_id
            ORDER BY f.submitted_on DESC
        """)
        all_feedbacks = cursor.fetchall()
        
        # Convert to list of dictionaries for easier template access
        feedbacks_list = []
        for fb in all_feedbacks:
            feedbacks_list.append({
                'display_name': fb[0],
                'feedback_text': fb[1],
                'submitted_on': fb[2],
                'user_type': fb[3]
            })
        
        recent_feedbacks = feedbacks_list[:2]
        older_feedbacks = feedbacks_list[2:]
        
        return render_template('feedbacks.html', 
                            recent_feedbacks=recent_feedbacks,
                            older_feedbacks=older_feedbacks)
        
    except Exception as e:
        flash(f'Error loading feedbacks: {str(e)}', 'danger')
        return render_template('feedbacks.html',
                            recent_feedbacks=[],
                            older_feedbacks=[])

@app.route('/stu_ver')
def stu_ver():
    return render_template('stu_ver.html')

@app.route('/stu_edit', methods=['GET', 'POST'])
def stu_edit():
    student = session.get('student')
    if not student:
        flash('Please log in first', 'warning')
        return redirect(url_for('student_login'))

    return render_template('stu_edit.html', student=student)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    # Get updated data from form
    # Since rollno/email are disabled, you'll only get fields that are editable
    phone = request.form.get('phone')
    year = request.form.get('year')
    # If you allow editing other fields, get them here too
    # Get student id or admission no from session to identify which student to update
    student = session.get('student')
    if not student:
        flash('Please login first', 'warning')
        return redirect(url_for('student_login'))

    student_id = student['student_id']

    # Update in database
    cursor.execute("UPDATE students SET phone=%s,year=%s WHERE student_id=%s", (phone,year, student_id))
    db.commit()

    # Update session data too
    student['phone'] = phone
    student['year'] = year
    session['student'] = student

    flash('Profile updated successfully', 'success')

    # Redirect back to edit page (this refreshes the page)
    return redirect(url_for('stu_edit'))

from flask import current_app
def send_password_reset_email(to_email, token):
    reset_url = url_for('reset_password', token=token, _external=True)
    msg = Message(
        subject="Reset Your Password",
        recipients=[to_email],
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    msg.body = f"""
Hello,

To reset your password, please click the link below:

{reset_url}

If you did not request this password reset, please ignore this email.

Thank you,
Your Hostel Management Team
"""
    current_app.extensions['mail'].send(msg)


@app.route('/student/forgot-password', methods=['GET', 'POST'])
def spassword():
    if request.method == 'POST':
        email = request.form['email']
        # Check if student email exists
        cursor.execute("SELECT * FROM students WHERE email=%s", (email,))
        user = cursor.fetchone()
        if user:
            token = generate_verification_token(email)
            send_password_reset_email(email, token)
            flash('Password reset email sent. Please check your inbox.', 'success')
        else:
            flash('Email not found.', 'error')
    return render_template('spassword.html')


@app.route('/student/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = confirm_verification_token(token)
    if not email:
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('spassword'))
    
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('reset_password.html')

        hashed_pw = generate_password_hash(password)
        cursor.execute("UPDATE students SET password_hash=%s WHERE email=%s", (hashed_pw, email))
        db.commit()
        flash('Your password has been updated! Please log in.', 'success')
        return redirect(url_for('student_login'))  # replace with your login route
    
    return render_template('reset_password.html')

@app.route('/verify_success')
def verify_success():
    return render_template('verify_success.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/stu_logout')
def stu_logout():
    session.clear()
    return redirect(url_for('student_login'))


if __name__ == '__main__':
    app.run(debug=True)
