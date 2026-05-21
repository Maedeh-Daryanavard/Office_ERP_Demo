from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import csv
import io
import smtplib
from email.message import EmailMessage
from flask import Response
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "leave-management-secret"

app.config["STUDENT_IMAGE_FOLDER"] = "static/uploads/students"
app.config["STUDENT_DOCUMENT_FOLDER"] = "static/uploads/documents"

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "png", "jpg", "jpeg"}


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions

def get_db():
    conn = sqlite3.connect("employees.db")
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            date_of_birth TEXT,
            gender TEXT,
            address TEXT,
            course TEXT,
            registration_date TEXT,
            image TEXT,
            education_document TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS student_absences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_name TEXT NOT NULL,
            program_code TEXT NOT NULL UNIQUE,
            duration TEXT,
            fee REAL,
            description TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_name TEXT NOT NULL,
            category TEXT,
            quantity INTEGER NOT NULL DEFAULT 0,
            purchase_date TEXT,
            status TEXT DEFAULT 'Available',
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("office_dashboard.html")

@app.route("/employee-management")
def employee_management():
    return render_template("employee_management.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        department = request.form["department"]

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO employees (name, email, department) VALUES (?, ?, ?)",
                (name, email, department)
            )
            conn.commit()
            flash("Employee registered successfully!", "success")
        except sqlite3.IntegrityError:
            flash("Email already exists!", "danger")
        finally:
            conn.close()

        return redirect(url_for("register"))

    return render_template("register.html")

# @app.route("/employees")
# def employees():
#     conn = get_db()
#     employee_list = conn.execute("SELECT * FROM employees ORDER BY id DESC").fetchall()
#     conn.close()

#     return render_template("employees.html", employees=employee_list)
@app.route("/employees")
def employees():
    search = request.args.get("search", "")

    conn = get_db()

    if search:
        employee_list = conn.execute("""
            SELECT * FROM employees
            WHERE name LIKE ? OR department LIKE ?
            ORDER BY id DESC
        """, (f"%{search}%", f"%{search}%")).fetchall()
    else:
        employee_list = conn.execute(
            "SELECT * FROM employees ORDER BY id DESC"
        ).fetchall()

    conn.close()

    return render_template(
        "employees.html",
        employees=employee_list,
        search=search
    )
@app.route("/edit-employee/<int:id>", methods=["GET", "POST"])
def edit_employee(id):
    conn = get_db()
    employee = conn.execute(
        "SELECT * FROM employees WHERE id = ?", (id,)
    ).fetchone()

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        department = request.form["department"]

        conn.execute("""
            UPDATE employees
            SET name = ?, email = ?, department = ?
            WHERE id = ?
        """, (name, email, department, id))

        conn.commit()
        conn.close()

        flash("Employee updated successfully!", "success")
        return redirect(url_for("employees"))

    conn.close()
    return render_template("edit_employee.html", employee=employee)
@app.route("/delete-employee/<int:id>")
def delete_employee(id):
    conn = get_db()

    conn.execute("DELETE FROM leaves WHERE employee_id = ?", (id,))
    conn.execute("DELETE FROM employees WHERE id = ?", (id,))

    conn.commit()
    conn.close()

    flash("Employee deleted successfully!", "success")
    return redirect(url_for("employees"))

@app.route("/request-leave", methods=["GET", "POST"])
def request_leave():
    conn = get_db()
    employees = conn.execute("SELECT * FROM employees").fetchall()

    if request.method == "POST":
        employee_id = request.form["employee_id"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        reason = request.form["reason"]
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        if end < start:
            flash("End date cannot be before start date!", "danger")
            conn.close()
            return redirect(url_for("request_leave"))


        conn.execute(
            """
            INSERT INTO leaves (employee_id, start_date, end_date, reason)
            VALUES (?, ?, ?, ?)
            """,
            (employee_id, start_date, end_date, reason)
        )
        conn.commit()
        conn.close()

        flash("Leave request submitted!", "success")
        return redirect(url_for("leaves"))

    conn.close()
    return render_template("request_leave.html", employees=employees)


@app.route("/leaves")
def leaves():
    conn = get_db()
    leave_list = conn.execute("""
        SELECT leaves.id, employees.name, employees.department,
               leaves.start_date, leaves.end_date, leaves.reason, leaves.status
        FROM leaves
        JOIN employees ON leaves.employee_id = employees.id
        ORDER BY leaves.id DESC
    """).fetchall()
    conn.close()

    return render_template("leaves.html", leaves=leave_list)


# @app.route("/approve/<int:leave_id>")
# def approve_leave(leave_id):
#     conn = get_db()
#     conn.execute("UPDATE leaves SET status = 'Approved' WHERE id = ?", (leave_id,))
#     conn.commit()
#     conn.close()
#     return redirect(url_for("leaves"))
@app.route("/approve/<int:leave_id>")
def approve_leave(leave_id):
    send_email_choice = request.args.get("send_email", "no")

    conn = get_db()

    leave = conn.execute("""
        SELECT leaves.*, employees.name, employees.email
        FROM leaves
        JOIN employees ON leaves.employee_id = employees.id
        WHERE leaves.id = ?
    """, (leave_id,)).fetchone()

    conn.execute(
        "UPDATE leaves SET status = 'Approved' WHERE id = ?",
        (leave_id,)
    )

    conn.commit()
    conn.close()

    if send_email_choice == "yes":
        send_leave_email(
            leave["email"],
            leave["name"],
            leave["start_date"],
            leave["end_date"],
            "Approved"
        )

    flash("Leave approved successfully!", "success")
    return redirect(url_for("leaves"))

# @app.route("/reject/<int:leave_id>")
# def reject_leave(leave_id):
#     conn = get_db()
#     conn.execute("UPDATE leaves SET status = 'Rejected' WHERE id = ?", (leave_id,))
#     conn.commit()
#     conn.close()
#     return redirect(url_for("leaves"))
@app.route("/reject/<int:leave_id>")
def reject_leave(leave_id):
    send_email_choice = request.args.get("send_email", "no")

    conn = get_db()

    leave = conn.execute("""
        SELECT leaves.*, employees.name, employees.email
        FROM leaves
        JOIN employees ON leaves.employee_id = employees.id
        WHERE leaves.id = ?
    """, (leave_id,)).fetchone()

    conn.execute(
        "UPDATE leaves SET status = 'Rejected' WHERE id = ?",
        (leave_id,)
    )

    conn.commit()
    conn.close()

    if send_email_choice == "yes":
        send_leave_email(
            leave["email"],
            leave["name"],
            leave["start_date"],
            leave["end_date"],
            "Rejected"
        )

    flash("Leave rejected successfully!", "success")
    return redirect(url_for("leaves"))

@app.route("/delete/<int:leave_id>")
def delete_leave(leave_id):
    conn = get_db()
    conn.execute("DELETE FROM leaves WHERE id = ?", (leave_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("leaves"))
@app.route("/report")
def report():
    conn = get_db()

    total_employees = conn.execute(
        "SELECT COUNT(*) FROM employees"
    ).fetchone()[0]

    total_leaves = conn.execute(
        "SELECT COUNT(*) FROM leaves"
    ).fetchone()[0]

    pending_leaves = conn.execute(
        "SELECT COUNT(*) FROM leaves WHERE status = 'Pending'"
    ).fetchone()[0]

    approved_leaves = conn.execute(
        "SELECT COUNT(*) FROM leaves WHERE status = 'Approved'"
    ).fetchone()[0]

    rejected_leaves = conn.execute(
        "SELECT COUNT(*) FROM leaves WHERE status = 'Rejected'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "report.html",
        total_employees=total_employees,
        total_leaves=total_leaves,
        pending_leaves=pending_leaves,
        approved_leaves=approved_leaves,
        rejected_leaves=rejected_leaves
    )

@app.route("/export-employees")
def export_employees():
    conn = get_db()
    employees = conn.execute("SELECT * FROM employees").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["ID", "Name", "Email", "Department"])

    for employee in employees:
        writer.writerow([
            employee["id"],
            employee["name"],
            employee["email"],
            employee["department"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=employees_report.csv"
        }
    )
@app.route("/export-leaves")
def export_leaves():
    conn = get_db()

    leaves = conn.execute("""
        SELECT leaves.id, employees.name, employees.email, employees.department,
               leaves.start_date, leaves.end_date, leaves.reason, leaves.status
        FROM leaves
        JOIN employees ON leaves.employee_id = employees.id
        ORDER BY leaves.id DESC
    """).fetchall()

    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID", "Employee", "Email", "Department",
        "Start Date", "End Date", "Reason", "Status"
    ])

    for leave in leaves:
        writer.writerow([
            leave["id"],
            leave["name"],
            leave["email"],
            leave["department"],
            leave["start_date"],
            leave["end_date"],
            leave["reason"],
            leave["status"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=leave_report.csv"
        }
    )
def send_leave_email(to_email, employee_name, start_date, end_date, status):
    sender_email = "maedeh.daryanavard2266@gmail.com"
    app_password = "cjlxjeujmcrxgivz"

    msg = EmailMessage()
    msg["Subject"] = f"Leave Request {status}"
    msg["From"] = sender_email
    msg["To"] = to_email

    msg.set_content(f"""
Dear {employee_name},

Your leave request from {start_date} to {end_date} has been {status.lower()} by the manager.

Thank you,
HR Department
""")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender_email, app_password)
        smtp.send_message(msg)


@app.route("/student-management")
def student_management():
    return render_template("student_management.html")
@app.route("/register-student", methods=["GET", "POST"])
def register_student():
    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        date_of_birth = request.form["date_of_birth"]
        gender = request.form["gender"]
        address = request.form["address"]
        course = request.form["course"]
        registration_date = request.form["registration_date"]

        image_file = request.files["image"]
        document_file = request.files["education_document"]

        image_filename = None
        document_filename = None

        if image_file and allowed_file(image_file.filename, ALLOWED_IMAGE_EXTENSIONS):
            image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config["STUDENT_IMAGE_FOLDER"], image_filename))

        if document_file and allowed_file(document_file.filename, ALLOWED_DOCUMENT_EXTENSIONS):
            document_filename = secure_filename(document_file.filename)
            document_file.save(os.path.join(app.config["STUDENT_DOCUMENT_FOLDER"], document_filename))

        conn = get_db()

        try:
            conn.execute("""
                INSERT INTO students
                (first_name, last_name, email, phone, date_of_birth, gender, address,
                 course, registration_date, image, education_document)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                first_name, last_name, email, phone, date_of_birth, gender, address,
                course, registration_date, image_filename, document_filename
            ))

            conn.commit()
            flash("Student registered successfully!", "success")

        except sqlite3.IntegrityError:
            flash("Student email already exists!", "danger")

        finally:
            conn.close()

        return redirect(url_for("register_student"))

    return render_template("register_student.html")
@app.route("/students")
def students():
    search = request.args.get("search", "")

    conn = get_db()

    if search:
        student_list = conn.execute("""
            SELECT * FROM students
            WHERE first_name LIKE ?
               OR last_name LIKE ?
               OR email LIKE ?
               OR course LIKE ?
            ORDER BY id DESC
        """, (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        )).fetchall()
    else:
        student_list = conn.execute(
            "SELECT * FROM students ORDER BY id DESC"
        ).fetchall()

    conn.close()

    return render_template("students.html", students=student_list, search=search)
@app.route("/student-details/<int:id>")
def student_details(id):
    conn = get_db()
    student = conn.execute(
        "SELECT * FROM students WHERE id = ?", (id,)
    ).fetchone()
    conn.close()

    return render_template("student_details.html", student=student)

@app.route("/edit-student/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    conn = get_db()
    student = conn.execute(
        "SELECT * FROM students WHERE id = ?", (id,)
    ).fetchone()

    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        address = request.form["address"]
        course = request.form["course"]

        conn.execute("""
            UPDATE students
            SET first_name = ?, last_name = ?, email = ?, phone = ?, address = ?, course = ?
            WHERE id = ?
        """, (first_name, last_name, email, phone, address, course, id))

        conn.commit()
        conn.close()

        flash("Student updated successfully!", "success")
        return redirect(url_for("students"))

    conn.close()
    return render_template("edit_student.html", student=student)
@app.route("/delete-student/<int:id>")
def delete_student(id):
    conn = get_db()

    conn.execute("DELETE FROM student_absences WHERE student_id = ?", (id,))
    conn.execute("DELETE FROM students WHERE id = ?", (id,))

    conn.commit()
    conn.close()

    flash("Student deleted successfully!", "success")
    return redirect(url_for("students"))
@app.route("/student-absence", methods=["GET", "POST"])
def student_absence():
    conn = get_db()
    students = conn.execute("SELECT * FROM students ORDER BY first_name").fetchall()

    if request.method == "POST":
        student_id = request.form["student_id"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        reason = request.form["reason"]

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        if end < start:
            flash("End date cannot be before start date!", "danger")
            conn.close()
            return redirect(url_for("student_absence"))

        conn.execute("""
            INSERT INTO student_absences
            (student_id, start_date, end_date, reason)
            VALUES (?, ?, ?, ?)
        """, (student_id, start_date, end_date, reason))

        conn.commit()
        conn.close()

        flash("Student absence request submitted!", "success")
        return redirect(url_for("student_absences"))

    conn.close()
    return render_template("student_absence.html", students=students)
@app.route("/student-absences")
def student_absences():
    conn = get_db()

    absences = conn.execute("""
        SELECT student_absences.id,
               students.first_name,
               students.last_name,
               students.email,
               students.course,
               student_absences.start_date,
               student_absences.end_date,
               student_absences.reason,
               student_absences.status
        FROM student_absences
        JOIN students ON student_absences.student_id = students.id
        ORDER BY student_absences.id DESC
    """).fetchall()

    conn.close()

    return render_template("student_absences.html", absences=absences)
def send_student_absence_email(to_email, student_name, start_date, end_date, status):
    sender_email = "maedeh.daryanavard2266@gmail.com"
    app_password = "cjlxjeujmcrxgivz"

    msg = EmailMessage()
    msg["Subject"] = f"Student Absence Request {status}"
    msg["From"] = sender_email
    msg["To"] = to_email

    msg.set_content(f"""
Dear {student_name},

Your absence request from {start_date} to {end_date} has been {status.lower()} by the office manager.

If you have any questions, please contact the office.

Best regards,
Office Management Team
""")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender_email, app_password)
        smtp.send_message(msg)

@app.route("/approve-student-absence/<int:id>")
def approve_student_absence(id):
    send_email_choice = request.args.get("send_email", "no")

    conn = get_db()

    absence = conn.execute("""
        SELECT student_absences.*, students.first_name, students.last_name, students.email
        FROM student_absences
        JOIN students ON student_absences.student_id = students.id
        WHERE student_absences.id = ?
    """, (id,)).fetchone()

    conn.execute(
        "UPDATE student_absences SET status = 'Approved' WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    if send_email_choice == "yes":
        send_student_absence_email(
            absence["email"],
            absence["first_name"] + " " + absence["last_name"],
            absence["start_date"],
            absence["end_date"],
            "Approved"
        )

    flash("Student absence approved successfully!", "success")
    return redirect(url_for("student_absences"))

@app.route("/reject-student-absence/<int:id>")
def reject_student_absence(id):
    send_email_choice = request.args.get("send_email", "no")

    conn = get_db()

    absence = conn.execute("""
        SELECT student_absences.*, students.first_name, students.last_name, students.email
        FROM student_absences
        JOIN students ON student_absences.student_id = students.id
        WHERE student_absences.id = ?
    """, (id,)).fetchone()

    conn.execute(
        "UPDATE student_absences SET status = 'Rejected' WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    if send_email_choice == "yes":
        send_student_absence_email(
            absence["email"],
            absence["first_name"] + " " + absence["last_name"],
            absence["start_date"],
            absence["end_date"],
            "Rejected"
        )

    flash("Student absence rejected successfully!", "success")
    return redirect(url_for("student_absences"))

@app.route("/delete-student-absence/<int:id>")
def delete_student_absence(id):
    conn = get_db()

    conn.execute(
        "DELETE FROM student_absences WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    flash("Student absence deleted successfully!", "success")
    return redirect(url_for("student_absences"))

@app.route("/program-management")
def program_management():
    return render_template("program_management.html")

@app.route("/add-program", methods=["GET", "POST"])
def add_program():
    if request.method == "POST":
        program_name = request.form["program_name"]
        program_code = request.form["program_code"]
        duration = request.form["duration"]
        fee = request.form["fee"] or 0
        description = request.form["description"]

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO programs (program_name, program_code, duration, fee, description)
                VALUES (?, ?, ?, ?, ?)
            """, (program_name, program_code, duration, fee, description))
            conn.commit()
            flash("Program added successfully!", "success")
        except sqlite3.IntegrityError:
            flash("Program code already exists!", "danger")
        finally:
            conn.close()

        return redirect(url_for("add_program"))

    return render_template("add_program.html")

@app.route("/programs")
def programs():
    search = request.args.get("search", "")
    conn = get_db()

    if search:
        program_list = conn.execute("""
            SELECT * FROM programs
            WHERE program_name LIKE ? OR program_code LIKE ? OR duration LIKE ?
            ORDER BY id DESC
        """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        program_list = conn.execute("SELECT * FROM programs ORDER BY id DESC").fetchall()

    conn.close()
    return render_template("programs.html", programs=program_list, search=search)

@app.route("/edit-program/<int:id>", methods=["GET", "POST"])
def edit_program(id):
    conn = get_db()
    program = conn.execute("SELECT * FROM programs WHERE id = ?", (id,)).fetchone()

    if request.method == "POST":
        program_name = request.form["program_name"]
        program_code = request.form["program_code"]
        duration = request.form["duration"]
        fee = request.form["fee"] or 0
        description = request.form["description"]

        conn.execute("""
            UPDATE programs
            SET program_name = ?, program_code = ?, duration = ?, fee = ?, description = ?
            WHERE id = ?
        """, (program_name, program_code, duration, fee, description, id))
        conn.commit()
        conn.close()

        flash("Program updated successfully!", "success")
        return redirect(url_for("programs"))

    conn.close()
    return render_template("edit_program.html", program=program)

@app.route("/delete-program/<int:id>")
def delete_program(id):
    conn = get_db()
    conn.execute("DELETE FROM programs WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash("Program deleted successfully!", "success")
    return redirect(url_for("programs"))


@app.route("/equipment-management")
def equipment_management():
    return render_template("equipment_management.html")

@app.route("/add-equipment", methods=["GET", "POST"])
def add_equipment():
    if request.method == "POST":
        equipment_name = request.form["equipment_name"]
        category = request.form["category"]
        quantity = request.form["quantity"] or 0
        purchase_date = request.form["purchase_date"]
        status = request.form["status"]
        notes = request.form["notes"]

        conn = get_db()
        conn.execute("""
            INSERT INTO equipment (equipment_name, category, quantity, purchase_date, status, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (equipment_name, category, quantity, purchase_date, status, notes))
        conn.commit()
        conn.close()

        flash("Equipment added successfully!", "success")
        return redirect(url_for("add_equipment"))

    return render_template("add_equipment.html")

@app.route("/equipment")
def equipment():
    search = request.args.get("search", "")
    conn = get_db()

    if search:
        equipment_list = conn.execute("""
            SELECT * FROM equipment
            WHERE equipment_name LIKE ? OR category LIKE ? OR status LIKE ?
            ORDER BY id DESC
        """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        equipment_list = conn.execute("SELECT * FROM equipment ORDER BY id DESC").fetchall()

    conn.close()
    return render_template("equipment.html", equipment=equipment_list, search=search)

@app.route("/edit-equipment/<int:id>", methods=["GET", "POST"])
def edit_equipment(id):
    conn = get_db()
    item = conn.execute("SELECT * FROM equipment WHERE id = ?", (id,)).fetchone()

    if request.method == "POST":
        equipment_name = request.form["equipment_name"]
        category = request.form["category"]
        quantity = request.form["quantity"] or 0
        purchase_date = request.form["purchase_date"]
        status = request.form["status"]
        notes = request.form["notes"]

        conn.execute("""
            UPDATE equipment
            SET equipment_name = ?, category = ?, quantity = ?, purchase_date = ?, status = ?, notes = ?
            WHERE id = ?
        """, (equipment_name, category, quantity, purchase_date, status, notes, id))
        conn.commit()
        conn.close()

        flash("Equipment updated successfully!", "success")
        return redirect(url_for("equipment"))

    conn.close()
    return render_template("edit_equipment.html", item=item)

@app.route("/delete-equipment/<int:id>")
def delete_equipment(id):
    conn = get_db()
    conn.execute("DELETE FROM equipment WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash("Equipment deleted successfully!", "success")
    return redirect(url_for("equipment"))
@app.route("/fix-database")
def fix_database():
    create_tables()
    return "Database fixed! Programs and equipment tables created."    
if __name__ == "__main__":
    create_tables()
    app.run(debug=True)