import os

from flask import Flask, session, render_template, redirect, request, url_for, jsonify, flash
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import login_required
import requests

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
@login_required
def signout():

    # Clear the session and take user back to home page
    session.clear()
    return redirect("/")

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():

    # If request method is GET, show user the search form
    if request.method == "GET":

        # If the user has already made a search which doesn't return any results
        # then show an error message
        if session.get('no_results'):
            session['no_results'] = None
            return render_template("search.html", error_message="No matching results")

        # Otherwise show the search form
        else:
            return render_template("search.html")

    # Otherwise the request method is POST, search the database for the users input
    # and pass the data to the results page template
    else:

        # Get the users search inupt
        search_query = request.form['search-books']

        # Search the database and store the results in a session variable to pass to results page
        session["result"] = db.execute(
            "SELECT * FROM books WHERE UPPER(title) LIKE UPPER(:search_query) OR author LIKE :search_query OR isbn LIKE :search_query",
            { "search_query": '%' + search_query + '%'}).fetchall()

        return redirect(url_for("search_results"))

@app.route("/results", methods=["GET"])
@login_required
def search_results():

        # If the the search returned no results then redirect the user to the search page
        if session["result"] == []:
            session['no_results'] = "No matching books"
            return redirect(url_for("search"))

        # Otherwise display the results
        else:
            return render_template("search_results.html", result=session["result"])

@app.route("/book_page", methods=["GET", "POST"])
@login_required
def book_details():

    # Get variables from query string and get user id from session
    title = request.args.get("title")
    author = request.args.get("author")
    year = request.args.get("year")
    isbn = request.args.get("isbn")
    user_id = session['user_id']

    # Get review details from goodreads as JSON
    review_counts = requests.get("https://www.goodreads.com/book/review_counts.json",
                        params={"key": os.getenv("KEY"), "isbns": isbn}).json()
    ratings_count = review_counts['books'][0]['work_ratings_count']
    average_rating = review_counts['books'][0]['average_rating']

    # Check if the book has any reviews
    try:
        reviews = db.execute("SELECT * FROM reviews WHERE isbn=:isbn", {"isbn": isbn}).fetchall()
    except:
        reviews = []

    # If request method is "GET" return the template for the requested book
    if request.method == "GET":

        # If the book has reviews then display them, otherwise don't
        if reviews:
            return render_template("book_page.html", title=title, author=author,
            publish_date=year, isbn=isbn, reviews=reviews, ratings_count=ratings_count, average_rating=average_rating)
        else:
            return render_template("book_page.html", title=title, author=author,
            publish_date=year, isbn=isbn, ratings_count=ratings_count, average_rating=average_rating)

    # Otherwise the request method is "POST" and the user has submitted a review
    else:

        # Check that user input a star rating
        if not request.form.get("star_rating"):
            return render_template("book_page.html", reviews=reviews, title=title, author=author,
            publish_date=year, isbn=isbn, ratings_count=ratings_count, average_rating=average_rating,
            error_message="Please enter a star rating")

        # Check that user input a review
        if not request.form.get("review"):
            return render_template("book_page.html", reviews=reviews, title=title, author=author,
            publish_date=year, isbn=isbn, ratings_count=ratings_count, average_rating=average_rating,
            error_message="Please enter a review")

        # Check if the user has already reviewed the book
        try:
            db.execute(
                    "SELECT * FROM reviews WHERE user_id = :user_id AND isbn = :isbn",
                    {"user_id": user_id, "isbn": isbn})

            # If they haven't then commit the review into the database and return the user to the
            # book template
            db.execute(
                    "INSERT INTO reviews (user_id, isbn, review, star_rating) VALUES (:user_id, :isbn, :review, :star_rating)",
                    {"user_id": user_id, "isbn": isbn, "review": request.form['review'], "star_rating": request.form['star_rating']})
            reviews = db.execute("SELECT * FROM reviews WHERE isbn=:isbn", {"isbn": isbn})
            db.commit()

            return render_template("book_page.html", reviews=reviews, title=title, author=author,
            publish_date=year, isbn=isbn, ratings_count=ratings_count, average_rating=average_rating)

        except:
        # If the user has already reviewed the book then display an error message
            return render_template("book_page.html", reviews=reviews, title=title, author=author,
            publish_date=year, isbn=isbn, ratings_count=ratings_count, average_rating=average_rating,
            error_message="You have already reviewed this book")

@app.route("/api/<isbn>", methods=["GET"])
def api_json(isbn):
    try:

        # Get book details and review statistics to display
        book_request = db.execute("SELECT reviews.isbn, title, author, year FROM books JOIN reviews ON books.isbn=reviews.isbn WHERE reviews.isbn=:isbn", {"isbn": isbn}).fetchone()
        book_stats = db.execute("SELECT COUNT(*) AS review_count, AVG(star_rating) AS average_score FROM reviews WHERE isbn=:isbn", {"isbn": isbn}).fetchone()
        isbn = book_request[0]
        title = book_request[1]
        author = book_request[2]
        year = book_request[3]
        review_count = book_stats[0]
        average_score = book_stats[1]

        return jsonify(isbn=isbn, title=title, author=author, year=year,
        review_count=review_count, average_score=(int(average_score*1000)/1000))

    # If the book is not in the database return a 404 error
    except:
        return render_template("404.html"), 404
