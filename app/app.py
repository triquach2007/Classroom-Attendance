from flask import Flask, render_template, jsonify, request, url_for, redirect, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import qrcode
import io

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///classroom.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Models ---
class AttendanceSession(db.Model):
    __tablename__ = 'attendance_sessions'
    session_id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    rows = db.Column(db.Integer, nullable=False, default=5)
    cols = db.Column(db.Integer, nullable=False, default=5)
    is_active = db.Column(db.Boolean, default=True)
    assignments = db.relationship('SeatingAssignment', backref='session', lazy=True, cascade="all, delete-orphan")

class Student(db.Model):
    __tablename__ = 'students'
    student_id = db.Column(db.String(20), primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    seats = db.relationship('SeatingAssignment', backref='student', lazy=True)

class SeatingAssignment(db.Model):
    __tablename__ = 'seating_assignments'
    assignment_id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('attendance_sessions.session_id'), nullable=False)
    student_id = db.Column(db.String(20), db.ForeignKey('students.student_id'), nullable=False)
    seat_row = db.Column(db.Integer, nullable=False)
    seat_col = db.Column(db.Integer, nullable=False)

# --- Routes ---
@app.route('/generate_qr/<int:session_id>')
def generate_qr(session_id):
    url = request.host_url.rstrip('/') + url_for('classroom', session_id=session_id)
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/dashboard')
def dashboard():
    all_sessions = AttendanceSession.query.order_by(AttendanceSession.session_id.desc()).all()
    active_count = AttendanceSession.query.filter_by(is_active=True).count()
    return render_template('dashboard.html', sessions=all_sessions, active_count=active_count, 
                           total_sessions=len(all_sessions), total_checked_in=SeatingAssignment.query.count())

@app.route('/classroom/<int:session_id>')
def classroom(session_id):
    session_record = AttendanceSession.query.get_or_404(session_id)
    seating_map = {(sa.seat_row, sa.seat_col): sa.student for sa in session_record.assignments}
    return render_template('classroom.html', session_id=session_id, rows=session_record.rows, cols=session_record.cols, seating_map=seating_map)

@app.route('/classroom/teacher/<int:session_id>')
def teacher_view(session_id):
    session_record = AttendanceSession.query.get_or_404(session_id)
    seating_map = {(sa.seat_row, sa.seat_col): sa.student for sa in session_record.assignments}
    return render_template('teacher_view.html', session_id=session_id, rows=session_record.rows, cols=session_record.cols, seating_map=seating_map)

@app.route('/create_session', methods=['POST'])
def create_session():
    rows = int(request.form.get('rows', 5))
    cols = int(request.form.get('cols', 5))
    new_session = AttendanceSession(rows=rows, cols=cols, is_active=True)
    db.session.add(new_session)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/toggle_session/<int:session_id>', methods=['POST'])
def toggle_session(session_id):
    session_record = AttendanceSession.query.get_or_404(session_id)
    session_record.is_active = not session_record.is_active
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/update_student', methods=['POST'])
def update_student():
    data = request.get_json() or {}
    session_id, row, col = data.get('session_id'), int(data.get('row')), int(data.get('col'))
    student_id, name = data.get('id', '').strip(), data.get('name', '').strip()
    
    session_record = AttendanceSession.query.get(session_id)
    if not session_record or not session_record.is_active:
        return jsonify({"status": "error", "message": "Session closed"}), 404

    # Remove existing and create new
    SeatingAssignment.query.filter_by(session_id=session_id, student_id=student_id).delete()
    db.session.add(SeatingAssignment(session_id=session_id, student_id=student_id, seat_row=row, seat_col=col))
    
    student = Student.query.filter_by(student_id=student_id).first() or Student(student_id=student_id, student_name=name)
    student.student_name = name
    db.session.add(student)
    db.session.commit()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)