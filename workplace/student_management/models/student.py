from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    grade = db.Column(db.String(10), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<Student {self.name}>'

    @staticmethod
    def test_system():
        # 这里可以添加用于测试系统的代码
        print("这是一个用于测试学生管理系统的静态方法。")
        # 例如，我们可以创建一些测试学生数据
        # student = Student(name="Test", age=20, grade="Grade 10", email="test@example.com")
        # db.session.add(student)
        # db.session.commit()
        # 或者执行一些查询操作来验证系统功能
        # students = Student.query.all()
        # for s in students:
        #     print(s)