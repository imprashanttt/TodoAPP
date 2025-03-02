from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_wtf import FlaskForm, form
from wtforms import StringField, PasswordField, SubmitField, EmailField
from wtforms.validators import DataRequired, Length
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
from flask_mail import Mail, Message
from flask_apscheduler import APScheduler


app = Flask(__name__)
app.config["SECRET_KEY"] = "supersecretkey"  # Required for CSRF Protection
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///todo.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "prashu8511@gmail.com"
app.config["MAIL_PASSWORD"] = "zvep pvsq juuq ynck"


db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
mail = Mail(app)
scheduler = APScheduler()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)

    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        hash_password = bcrypt.generate_password_hash(password).decode("utf8")
        self.password = hash_password


class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )  # Foreign Key
    text = db.Column(db.String(255), nullable=False)
    target_date = db.Column(db.Date, nullable=False)
    recurring_type = db.Column(db.String(255), nullable=False)
    date = db.Column(db.Date, default=datetime.today)

    def __init__(self, user_id, text, target_date, recurring_date):
        self.user_id = user_id
        self.text = text
        self.target_date = target_date
        self.recurring_type = recurring_date


class LoginForm(FlaskForm):
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=3, max=20)]
    )
    email = EmailField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


# checking  date  of task when app start


@app.route("/")
def index():
    try:
        user_logged_in = "username" and "user_id" in session
        return render_template(
            "index.html",
            user_logged_in=user_logged_in,
            username=session["username"],
            user_id=session["user_id"],
        )

    except Exception as e:
        return render_template("index.html", user_logged_in=False)


def send_reminder():
    with app.app_context():  # Ensure Flask app context
        users = User.query.all()  # Fetch all users
        for user in users:
            todos = Todo.query.filter_by(user_id=user.id).all()
            for todo in todos:
                if todo.target_date == datetime.today().date():
                    msg = Message(
                        "Task Reminder",
                        sender="prashu8511@gmail.com",
                        recipients=[user.email],
                    )
                    msg.body = f"{user.username}, your task '{todo.text}' is scheduled for today. Did you complete it?"
                    mail.send(msg)
                    
                    # Update recurring tasks
                    if todo.recurring_type.lower() == "daily":
                        todo.target_date += timedelta(days=1)
                    elif todo.recurring_type.lower() == "weekly":
                        todo.target_date += timedelta(days=7)
                    else:  # Monthly
                        todo.target_date += timedelta(days=30)
                    
                    db.session.commit()


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        form = LoginForm()
        return render_template("registration.html", form=form)
    else:
        form = LoginForm()
        username = form.username.data
        email = form.email.data
        password = form.password.data
        try:
            user = User(username, email, password)
            db.session.add(user)
            db.session.commit()
            flash(f"Welcome {form.username.data} you have to login first !", "success")
            return redirect(url_for("login"))
        except IntegrityError:
            flash("Username or Email already exists", "danger")
            flash("Please try again later")


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if request.method == "GET":
        return render_template("login.html", form=form)
    else:
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email).first()
        todos = Todo.query.filter_by(user_id=user.id).all()
        if bcrypt.check_password_hash(user.password, password):
            session["username"] = user.username
            session["user_id"] = user.id
            flash(f"Welcome {form.username.data}!", "success")  # Flash message
            return redirect("/")
        flash("Incorrect Email or Password", "danger")
        return redirect("/login")


@app.route("/dashboard/<username>")
def dashboard(username):
    return f"<h1>Welcome, {username}!</h1>"


@app.route("/add")
def add():
    return render_template("addTask.html", user_id=session["user_id"])


@app.route("/viewTask")
def viewTask():
    return render_template("viewTask.html")


@app.route("/view/<user_id>")
def view(user_id):
    print(user_id)
    data = Todo.query.filter(Todo.user_id == user_id).all()
    return render_template("viewTask.html", data=data)


@app.route("/delete_todo/<id>")
def delete_todo(id):
    todo = Todo.query.get_or_404(id)
    db.session.delete(todo)
    db.session.commit()
    return redirect(f"/view/{session['user_id']}")


@app.route("/add_todo/<user_id>", methods=["POST"])
def add_todo(user_id):
    uid = user_id
    task = request.form["task"]
    target_date_str = request.form["target_date"]
    recurring_date = request.form["option"]
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    data = Todo(uid, task, target_date, recurring_date)
    db.session.add(data)
    db.session.commit()
    return redirect("/add")


@app.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("user_id", None)
    return redirect("/")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        scheduler.init_app(app)  # Initialize scheduler with app

        # Check if the job already exists, if not, then add it
        if not scheduler.get_job("reminder"):  
            scheduler.add_job(id="reminder", func=send_reminder, trigger="interval", hours=24)

        scheduler.start()  # Start the scheduler
    app.run(debug=True)

