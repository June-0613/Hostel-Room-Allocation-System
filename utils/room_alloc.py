import random
from datetime import datetime
from config import get_connection

def allocate_student(student_app, cursor, allocated_room_ids):
    try:
        print("DEBUG >> Application received for allocation:", student_app)

        # Try requested room first
        if student_app.get('requested_room_id'):
            print("DEBUG >> Trying requested room:", student_app['requested_room_id'])
            cursor.execute("""
                SELECT * FROM rooms 
                WHERE room_id = %s AND occupied < capacity
            """, (student_app['requested_room_id'],))
            room = cursor.fetchone()
            print("DEBUG >> Room found for requested_room_id:", room)
            if room:
                return _finalize_allocation(student_app, room, 'Requested', cursor), room['room_number']

        # Try priority allocation
        if student_app.get('room_type'):
            print("DEBUG >> Trying room_type match:", student_app['room_type'])
            cursor.execute("""
                SELECT * FROM rooms 
                WHERE room_type = %s AND occupied < capacity
                ORDER BY occupied ASC
                LIMIT 1
            """, (student_app['room_type'],))
            room = cursor.fetchone()
            print("DEBUG >> Room found for room_type match:", room)
            if room:
                return _finalize_allocation(student_app, room, 'TypeMatch', cursor), room['room_number']

        # Try FCFS allocation
        print("DEBUG >> Trying FCFS allocation")
        cursor.execute("""
            SELECT * FROM rooms 
            WHERE occupied < capacity
            ORDER BY occupied ASC 
            LIMIT 1
        """)
        room = cursor.fetchone()
        print("DEBUG >> Room found for FCFS:", room)
        if room:
            return _finalize_allocation(student_app, room, 'FCFS', cursor), room['room_number']

        # Random allocation fallback
        print("DEBUG >> Trying Random Allocation")
        cursor.execute("""
            SELECT * FROM rooms 
            WHERE occupied < capacity
        """)
        rooms = cursor.fetchall()
        print("DEBUG >> Available rooms for Random:", rooms)

        available_rooms = [r for r in rooms if r['room_id'] not in allocated_room_ids]

        if available_rooms:
            selected_room = random.choice(available_rooms)
            allocated_room_ids.add(selected_room['room_id'])  # Track allocation
            return _finalize_allocation(student_app, selected_room, 'Random', cursor), selected_room['room_number']

        print("DEBUG >> No available rooms after all attempts.")
        return False, None
    except Exception as e:
        print(f"Allocation error: {str(e)}")
        return False, None

from datetime import datetime
from utils.email_ver import send_allocation_email  # adjust import path if needed

def _finalize_allocation(student_app, room, method, cursor):
    try:
        print("DEBUG >> student_app:", student_app)
        print("DEBUG >> room:", room)

        print(f"\n----- FINALIZE ALLOCATION START -----")
        print(f"Allocating student: {student_app['admission_no']}")
        print(f"To room: {room['room_number']} (ID: {room['room_id']}) using method: {method}")
        print(f"Application ID: {student_app.get('application_id')}")

        # Fetch student details (id, email, name) using admission_no
        admission_no = student_app['admission_no']
        cursor.execute("SELECT student_id, email, name FROM students WHERE admission_no = %s", (admission_no,))
        row = cursor.fetchone()
        if not row:
            print(f"ERROR: Student with admission_no {admission_no} not found in students table")
            return False

        student_id = row['student_id']
        student_email = row['email']
        student_name = row['name']

        # Update room occupancy
        cursor.execute("""
            UPDATE rooms 
            SET occupied = occupied + 1 
            WHERE room_id = %s
        """, (room['room_id'],))
        print("Room occupancy updated")

        # Insert allocation record
        cursor.execute("""
            INSERT INTO allocations 
            (student_id, room_id, method, allocated_on) 
            VALUES (%s, %s, %s, %s)
        """, (
            student_id,
            room['room_id'],
            method,
            datetime.now()
        ))
        print("Allocation record inserted")

        # Update application status
        cursor.execute("""
            UPDATE applications 
            SET status = 'approved', 
                remarks = %s 
            WHERE application_id = %s
        """, (
            f'Allocated by {method} to {room["room_number"]}',
            student_app['application_id']
        ))
        print("Application status updated")

        # Delete application after approval (optional, depends on your design)
        cursor.execute("DELETE FROM applications WHERE application_id = %s", (student_app['application_id'],))
        print(f"Application {student_app['application_id']} removed after successful allocation")

        # Send notification email
        send_allocation_email(student_email, student_name, room['room_number'])
        print(f"Allocation notification email sent to {student_email}")

        print("----- FINALIZE ALLOCATION SUCCESS -----\n")
        return True

    except Exception as e:
        print(f"!!!!! FINALIZE ALLOCATION ERROR: {str(e)} !!!!!\n")
        return False



def allocate_rooms():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    allocated_room_ids = set()

    try:
        # Process priority-based allocations
        cursor.execute("""
            SELECT a.*, s.priority, s.preferences
            FROM applications a
            JOIN students s ON a.admission_no = s.admission_no
            WHERE a.status = 'pending'
            ORDER BY s.priority DESC, a.application_time ASC
        """)
        all_applications = cursor.fetchall()

        for app in all_applications:
            if not allocate_student(app, cursor):
                # Update as failed allocation
                cursor.execute("""
                    UPDATE applications 
                    SET status = 'rejected', 
                        remarks = 'Auto-allocation failed' 
                    WHERE application_id = %s
                """, (app['application_id'],))
            
        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"Batch allocation error: {str(e)}")
    finally:
        cursor.close()
        conn.close()