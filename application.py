import os

from flask import Flask, session, render_template, redirect, request, url_for
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():

    # If user is not logged in then redirect them to the sign in page
    if not session.get("user_id"):
        return redirect("/signin")
    else:
        # If user is signed in take them to the search page
        return redirect("/search")

@app.route("/register", methods=["GET", "POST"])
def register():

    # If request method is GET show user the registration form
    if request.method == "GET":
        return render_template("register.html")

    # Otherwise request method is POST - validate the user input
    # and update the database
    else: 

        # Check that user has confirmed their password correctly
        if not (request.form.get('register-password') == request.form.get('register-password-confirm')):
            return render_template("register.html", error_message="Passwords do not match")
        else:

            # Add users registration information into user database
            try:
                db.execute("INSERT INTO users (username, email, hash) VALUES (:username, :email, :hash)", 
                                    {"username": request.form.get("register-username"), 
                                    "email": request.form.get("register-email"), 
                                    "hash": generate_password_hash(request.form.get("register-password"))})
                db.commit()

            # Return an error if the username is taken    
            except:
                return render_template("register.html", error_message="Username taken")  

            # Remember which user has logged in
            session["user_id"] = db.execute("SELECT id FROM users WHERE username = :username", 
                                            {"username": request.form.get("register-username")}).fetchone()

            # Redirect to homepage
            return redirect("/")

@app.route("/signin", methods=["GET", "POST"])
def signin():

    # if request method is GET return the signin form
    if request.method == "GET":
        return render_template("signin.html")

    # Otherwise request method is POST - validate user input against database    
    else:
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          {"username": request.form.get("signin-username")}).fetchall()
        
        # If username is not in database, inform the user
        if len(rows) != 1:
            return render_template("signin.html", error_message="Username is incorrect")

        # If password does not match the password in database, inform the user    
        elif not check_password_hash(rows[0][2], request.form.get("signin-password")):
            return render_template("signin.html", error_message="Password is incorrect")

        # If username and password are validated store the user id in session and
        # redirect user to the home page    
        else:
            session['user_id'] = rows[0][0]
            return redirect("/")
        
@app.route("/signout")
def signout():

    # Clear the session and take user back to home page
    session.clear()
    return redirect("/")

@app.route("/search", methods=["GET", "POST"])
def search():

    # If request method is GET, show user the search form
    if request.method == "GET":
        return render_template("search.html")
    # Otherwise the request method is POST, search the database for the users input
    # and pass the data to the results page template
    else:
        # Get the users search inupt
        search_query = request.form['search-books']
        # Search the database and store the results in a session variable to pass to results page
        session["result"] = db.execute(
            "SELECT * FROM books WHERE title LIKE :search_query OR author LIKE :search_query OR isbn LIKE :search_query", 
            { "search_query": '%' + search_query + '%'}).fetchall()
        return redirect(url_for("search_results"))

@app.route("/results", methods=["GET"])
def search_results():
    ## If there are no matching results display an error message
    if session["result"] == []:
        return render_template("no_search_results.html", error_message="No matching books found")
    ## Otherwise display the results in a table
    else:
        print(session["result"])
        return render_template("search_results.html", result=session["result"])

@app.route("/book_page", methods=["GET"])        
def book_details():
    book_id = request.args.get("book_id")
    title = request.args.get("title")
    author = request.args.get("author")
    year = request.args.get("year")
    isbn = request.args.get("isbn")
    return render_template("book_page.html", title=title, author=author, publish_date=year, isbn=isbn)
