# This is the routes.py file where all the URL routes for our Flask application are defined

# Import necessary modules from Flask and our local models
from flask import Blueprint, request, redirect, url_for, render_template, session  # Import Flask utilities
from .models import db, User, Listing  # Import our database models

# Create a Blueprint named 'main' - this helps organize our routes
main = Blueprint('main', __name__)

# Route for the home page ('/')
@main.route('/')
def index():
    if 'user_id' in session:  # Check if user is logged in by looking for user_id in session
        user = User.query.get(session['user_id'])  # Get the user object from database
        listings = Listing.query.filter_by(user_id=user.id).all()  # Get all listings for this user
        return render_template('index.html', username=user.username, listings=listings)  # Show personalized page
    return render_template('index.html', username=None)  # Show default page for non-logged in users

# Route for user registration - accepts both GET (show form) and POST (process form) requests
@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':  # If the request is POST (form submission)
        username = request.form['username']  # Get username from form data
        if User.query.filter_by(username=username).first() is None:  # Check if username is available
            new_user = User(username=username)  # Create new user object
            db.session.add(new_user)  # Add user to database
            db.session.commit()  # Save changes to database
            session['user_id'] = new_user.id  # Log user in by storing ID in session
            return redirect(url_for('main.index'))  # Redirect to home page
        return 'Username already registered'  # Error message if username taken
    return render_template('register.html')  # Show registration form for GET request

# Route for user login - accepts both GET (show form) and POST (process form) requests
@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':  # If the request is POST (form submission)
        username = request.form['username']  # Get username from form data
        user = User.query.filter_by(username=username).first()  # Look up user in database
        if user:  # If user exists
            session['user_id'] = user.id  # Store user ID in session (log them in)
            return redirect(url_for('main.index'))  # Redirect to home page
        return 'User not found'  # Error message if user doesn't exist
    return render_template('login.html')  # Show login form for GET request

# Route for user logout - only accepts POST requests for security
@main.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)  # Remove user_id from session (log them out)
    return redirect(url_for('main.index'))  # Redirect to home page

# Route for adding new listings - requires login
@main.route('/add-listing', methods=['GET', 'POST'])
def add_listing():
    if 'user_id' not in session:  # Check if user is logged in
        return redirect(url_for('main.login'))  # Redirect to login if not
    
    if request.method == 'POST':  # If the request is POST (form submission)
        listing_name = request.form['listing_name']  # Get listing name from form
        price = float(request.form['price'])  # Get and convert price to float
        new_listing = Listing(listing_name=listing_name, price=price, user_id=session['user_id'])  # Create new listing
        db.session.add(new_listing)  # Add listing to database
        db.session.commit()  # Save changes to database
        return redirect(url_for('main.listings'))  # Redirect to listings page

    return render_template('add_listing.html')  # Show add listing form for GET request

# Route to view all listings
@main.route('/listings')
def listings():
    all_listings = Listing.query.all()  # Get all listings from database
    return render_template('listings.html', listings=all_listings)  # Show listings page