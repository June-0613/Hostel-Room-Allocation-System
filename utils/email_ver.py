# utils/email_ver.py
from flask import url_for, current_app
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Message
from flask import current_app

def generate_verification_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])

def confirm_verification_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
    except Exception:
        return False
    return email

def send_verification_email(to, token):
    verify_url = f"http://localhost:5000/verify?token={token}"
    msg = Message(
        "Verify Your Email",
        recipients=[to],
        sender=current_app.config['MAIL_DEFAULT_SENDER']  # safe fallback
    )
    msg.body = f"Click the link to verify your account: {verify_url}"
    current_app.extensions['mail'].send(msg)


def send_allocation_email(to, student_name, room_number):
    subject = "Hostel Room Allocation Successful"
    msg = Message(
        subject,
        recipients=[to],
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    # You can use HTML or plain text; here’s a simple plain text example
    msg.body = f"""
Hi {student_name},

Congratulations! Your hostel room allocation has been successfully processed.

You have been allocated to room: {room_number}.

If you have any questions, please contact the hostel administration.

Best regards,
Hostel Management Team
"""
    current_app.extensions['mail'].send(msg)

def send_change_request_email(to, student_name, old_room, new_room, approved=True):
    subject = "Room Change Request " + ("Approved" if approved else "Rejected")
    msg = Message(
        subject,
        recipients=[to],
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    
    if approved:
        body = f"""
Hi {student_name},

Your request to change rooms has been approved.

Your new room is: {new_room}.
Your previous room was: {old_room}.

Please contact the hostel administration if you have questions.

Best regards,
Hostel Management Team
"""
    else:
        body = f"""
Hi {student_name},

We regret to inform you that your request to change rooms from {old_room} to {new_room} has been rejected.

For further details, please contact the hostel administration.

Best regards,
Hostel Management Team
"""
    msg.body = body
    current_app.extensions['mail'].send(msg)
