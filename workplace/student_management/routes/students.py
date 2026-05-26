from flask import Blueprint, request, jsonify
from models.student import Student, db

students_bp = Blueprint('students', __name__)

@students_bp.route('/students', methods=['GET'])
def get_students():
    students = Student.query.all()
    return jsonify([{'id': s.id, 'name': s.name, 'age': s.age, 'grade': s.grade, 'email': s.email} for s in students])

@students_bp.route('/students/<int:student_id>', methods=['GET'])
def get_student(student_id):
    student = Student.query.get_or_404(student_id)
    return jsonify({'id': student.id, 'name': student.name, 'age': student.age, 'grade': student.grade, 'email': student.email})

@students_bp.route('/students', methods=['POST'])
def add_student():
    data = request.get_json()
    new_student = Student(name=data['name'], age=data['age'], grade=data['grade'], email=data['email'])
    db.session.add(new_student)
    db.session.commit()
    return jsonify({'message': 'Student added successfully'}), 201

@students_bp.route('/students/<int:student_id>', methods=['PUT'])
def update_student(student_id):
    student = Student.query.get_or_404(student_id)
    data = request.get_json()
    if 'name' in data:
        student.name = data['name']
    if 'age' in data:
        student.age = data['age']
    if 'grade' in data:
        student.grade = data['grade']
    if 'email' in data:
        student.email = data['email']
    db.session.commit()
    return jsonify({'message': 'Student updated successfully'})

@students_bp.route('/students/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    return jsonify({'message': 'Student deleted successfully'})