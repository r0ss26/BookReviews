from functools import wraps
from flask import g, request, redirect, url_for, session

# wrapper function to restrict access to certain pages to loged in
# users only
# src: http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            return redirect(url_for('signin', next=request.url))
        return f(*args, **kwargs)
    return decorated_function