from flask import Flask, request, render_template, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mha_maths.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    is_teacher = db.Column(db.Boolean, default=False)
    score = db.Column(db.Integer, default=0)
    badges = db.Column(db.String(200), default='')

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500))
    answer = db.Column(db.String(100))
    difficulty = db.Column(db.String(20))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500))
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_correct = db.Column(db.Boolean)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create default teachers
def create_default_teachers():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(name='Administrator', username='admin', password='segni', is_teacher=True)
        db.session.add(admin)
    segni = User.query.filter_by(username='segni').first()
    if not segni:
        segni = User(name='Segni Teacher', username='segni', password='admin', is_teacher=True)
        db.session.add(segni)
    db.session.commit()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    user = User(name=data['name'], username=data['username'], password=data['password'])
    db.session.add(user)
    db.session.commit()
    flash('Registration successful! Please log in.', 'success')
    return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    user = User.query.filter_by(username=data['username'], password=data['password']).first()
    if user:
        session['user_id'] = user.id
        session['is_teacher'] = data.get('is_teacher') == 'on' and user.is_teacher
        return redirect(url_for('dashboard'))
    flash('Invalid credentials. Please try again.', 'danger')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_teacher', None)
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        data = request.form
        user.name = data['name']
        user.username = data['username']
        user.password = data['password']
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user)

@app.route('/add_question', methods=['POST'])
def add_question():
    if not session.get('is_teacher'):
        return redirect(url_for('index'))
    data = request.form
    question = Question(
        text=data['text'],
        answer=data['answer'],
        difficulty=data['difficulty'],
        category_id=data['category_id'],
        teacher_id=session['user_id']
    )
    db.session.add(question)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/edit_question/<int:id>', methods=['POST'])
def edit_question(id):
    if not session.get('is_teacher'):
        return redirect(url_for('index'))
    question = Question.query.get_or_404(id)
    data = request.form
    question.text = data['text']
    question.answer = data['answer']
    question.difficulty = data['difficulty']
    question.category_id = data['category_id']
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/delete_question/<int:id>')
def delete_question(id):
    if not session.get('is_teacher'):
        return redirect(url_for('index'))
    question = Question.query.get_or_404(id)
    db.session.delete(question)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    if 'user_id' not in session or session.get('is_teacher'):
        return redirect(url_for('index'))
    data = request.form
    question_id = int(data['question_id'])
    student_id = session['user_id']
    existing_answer = Answer.query.filter_by(student_id=student_id, question_id=question_id).first()
    if existing_answer:
        flash('You have already answered this question!', 'warning')
        return redirect(url_for('dashboard'))
    question = Question.query.get(question_id)
    is_correct = question.answer.lower() == data['text'].lower()
    answer = Answer(
        text=data['text'],
        question_id=question_id,
        student_id=student_id,
        is_correct=is_correct
    )
    db.session.add(answer)
    if is_correct:
        user = User.query.get(student_id)
        points = {'easy': 10, 'medium': 20, 'hard': 30}.get(question.difficulty, 10)
        user.score += points
        if user.score >= 100 and 'Beginner' not in user.badges:
            user.badges += ',Beginner'
        elif user.score >= 500 and 'Expert' not in user.badges:
            user.badges += ',Expert'
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    user = User.query.get(session['user_id'])
    categories = Category.query.all()
    if session['is_teacher']:
        search_query = request.args.get('search', '')
        questions = Question.query.filter(
            Question.teacher_id == user.id,
            Question.text.ilike(f'%{search_query}%')
        ).all()
        return render_template('teacher_dashboard.html', user=user, questions=questions, categories=categories, search_query=search_query)
    else:
        questions = Question.query.all()
        answers = Answer.query.filter_by(student_id=user.id).all()
        leaderboard = User.query.filter_by(is_teacher=False).order_by(User.score.desc()).limit(10).all()
        return render_template('student_dashboard.html', 
                             user=user,
                             questions=questions, 
                             answers=answers,
                             leaderboard=leaderboard,
                             categories=categories)

@app.route('/manage_students')
def manage_students():
    if not session.get('is_teacher'):
        return redirect(url_for('index'))
    user = User.query.get(session['user_id'])
    students = User.query.filter_by(is_teacher=False).all()
    student_data = []
    for student in students:
        correct_answers = Answer.query.filter_by(student_id=student.id, is_correct=True).count()
        student_data.append({
            'id': student.id,
            'name': student.name,
            'username': student.username,
            'password': student.password,
            'score': student.score,
            'correct_answers': correct_answers
        })
    return render_template('student_management.html', students=student_data, user=user)

@app.route('/add_student', methods=['POST'])
def add_student():
    if not session.get('is_teacher'):
        return redirect(url_for('index'))
    data = request.form
    student = User(name=data['name'], username=data['username'], password=data['password'])
    db.session.add(student)
    db.session.commit()
    return redirect(url_for('manage_students'))

@app.route('/edit_student/<int:id>', methods=['POST'])
def edit_student(id):
    if not session.get('is_teacher'):
        return redirect(url_for('index'))
    student = User.query.get_or_404(id)
    data = request.form
    student.name = data['name']
    student.username = data['username']
    student.password = data['password']
    db.session.commit()
    return redirect(url_for('manage_students'))

@app.route('/delete_student/<int:id>')
def delete_student(id):
    if not session.get('is_teacher'):
        return redirect(url_for('index'))
    student = User.query.get_or_404(id)
    db.session.delete(student)
    db.session.commit()
    return redirect(url_for('manage_students'))

@app.route('/add_teacher', methods=['POST'])
def add_teacher():
    if not session.get('is_teacher'):
        return redirect(url_for('index'))
    data = request.form
    teacher = User(
        name=data['name'], 
        username=data['username'], 
        password=data['password'], 
        is_teacher=True
    )
    db.session.add(teacher)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/add_category', methods=['POST'])
def add_category():
    if not session.get('is_teacher'):
        return redirect(url_for('index'))
    data = request.form
    category = Category(name=data['name'])
    db.session.add(category)
    db.session.commit()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_default_teachers()
    app.run(debug=True)
