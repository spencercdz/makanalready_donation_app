# danyl - import libraries and make the app routing
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Donation, DonationStatus, Booking
from datetime import datetime
import logging

app = Flask(__name__)
app.secret_key = "supersecretkey"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///donation_app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
logging.basicConfig(level=logging.INFO)


def role_required(role):
    def decorator(f):
        def wrapper(*args, **kwargs):
            if "user_id" not in session or session.get("role") != role:
                flash("Access denied.", "danger")
                return redirect(url_for("home"))
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# default route to home page
@app.route("/")
def home():
    return render_template("home.html")

# danyl - app register function
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]
        location = request.form.get("location", "").strip()

        if User.query.filter_by(username=username).first():
            flash("Username already taken. Please choose a different username.", "danger")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password, role=role, location=location)
        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for("home"))
        except Exception as e:
            logging.error(f"Error during registration: {e}")
            flash("An error occurred during registration. Please try again.", "danger")
            return redirect(url_for("register"))
    return render_template("register.html")

# spencer - login route 
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            flash("Login successful!", "success")
            return redirect(url_for("view_donations"))
        flash("Invalid credentials. Please try again.", "danger")
    return render_template("login.html")

# spencer - donate route 
@app.route("/donate", methods=["POST", "GET"])
def donate():
    if "user_id" not in session:
        flash("You need to log in to list food.", "danger")
        return redirect(url_for("login"))
    if session["role"] != "donor":
        flash("You are not authorized to list food.", "danger")
        return redirect(url_for("view_donations"))

    if request.method == "POST":
        try:
            restaurant_name = request.form.get("restaurant_name", "").strip()
            food_item = request.form.get("food_item", "").strip()
            meal_type = request.form.get("meal_type", "").strip()
            special_diet = request.form.get("special_diet", "").strip()
            quota_str = request.form.get("quota", "").strip()
            latitude_str = request.form.get("latitude", "").strip()
            longitude_str = request.form.get("longitude", "").strip()
            address = request.form.get("address", "").strip()

            if not all([restaurant_name, food_item, meal_type, special_diet, quota_str,
                        latitude_str, longitude_str, address]):
                flash("All fields (including the address) are required.", "danger")
                return redirect(url_for("donate"))

            # Convert `quota` to int
            try:
                quota = int(quota_str)
                if quota <= 0:
                    raise ValueError("Quota must be a positive integer.")
            except ValueError as e:
                flash(str(e), "danger")
                return redirect(url_for("donate"))

            # Convert lat & lon to float
            try:
                latitude = float(latitude_str)
                longitude = float(longitude_str)
            except ValueError:
                flash("Invalid latitude/longitude. Please select a valid location on the map.", "danger")
                return redirect(url_for("donate"))

            donor_id = session["user_id"]
            new_donation = Donation(
                restaurant_name=restaurant_name,
                food_item=food_item,
                meal_type=meal_type,
                special_diet=special_diet,
                quota=quota,
                latitude=latitude,
                longitude=longitude,
                donor_id=donor_id,
                bookings=0,
                address=address
            )
            db.session.add(new_donation)
            db.session.commit()

            flash("Food listed successfully!", "success")
            return redirect(url_for("view_donations"))

        except Exception as e:
            logging.error(f"An error occurred while listing the food: {e}")
            flash(f"An error occurred while listing the food: {e}", "danger")
            return redirect(url_for("donate"))

    return render_template("donate.html")

# spencer - edit donation route 
@app.route("/edit_donation/<int:donation_id>", methods=["GET", "POST"])
@role_required("donor")
def edit_donation(donation_id):
    donation = Donation.query.get_or_404(donation_id)

    if donation.donor_id != session["user_id"]:
        flash("You are not authorized to edit this listing.", "danger")
        return redirect(url_for("view_donations"))

    if request.method == "POST":
        try:
            donation.food_item = request.form["food_item"].strip()
            donation.meal_type = request.form["meal_type"].strip()
            donation.special_diet = request.form["special_diet"].strip()
            donation.quota = int(request.form["quota"])
            donation.address = request.form["address"].strip()

            lat_str = request.form["latitude"].strip()
            lng_str = request.form["longitude"].strip()
            donation.latitude = float(lat_str)
            donation.longitude = float(lng_str)

            db.session.commit()
            flash("Donation updated successfully!", "success")
            return redirect(url_for("view_donations"))

        except KeyError as ke:
            flash(f"Missing field: {ke}", "danger")
            return redirect(url_for("edit_donation", donation_id=donation.id))
        except ValueError as ve:
            flash(f"Invalid input: {ve}", "danger")
            return redirect(url_for("edit_donation", donation_id=donation.id))
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")
            return redirect(url_for("edit_donation", donation_id=donation.id))

    return render_template("edit_donation.html", donation=donation)

# spencer - view donations route
@app.route("/view_donations", methods=["GET"])
def view_donations():
    donations = Donation.query.all()
    serialized_donations = []
    for donation in donations:
        serialized_donations.append({
            "id": donation.id,
            "restaurant_name": donation.restaurant_name,
            "food_item": donation.food_item,
            "meal_type": donation.meal_type,
            "special_diet": donation.special_diet,
            "quota": donation.quota,
            "remaining_quota": donation.remaining_quota(),
            "latitude": donation.latitude,
            "longitude": donation.longitude,
            "address": donation.address,
            "status": donation.status.name.replace("_", " ").title(),
            "date_posted": donation.date_posted.strftime('%d %b %Y, %I:%M %p') 
                           if donation.date_posted else "N/A"
        })
    return render_template("view_donations.html", donations=serialized_donations)

# spencer - delete donations route
@app.route("/delete_donation/<int:donation_id>", methods=["POST"])
@role_required("donor")
def delete_donation(donation_id):
    donation = Donation.query.get_or_404(donation_id)
    if donation.donor_id != session["user_id"]:
        flash("You are not authorized to delete this listing.", "danger")
        return redirect(url_for("view_donations"))

    db.session.delete(donation)
    db.session.commit()
    flash("Donation deleted successfully.", "success")
    return redirect(url_for("view_donations"))

# steph - make the chope route
@app.route("/chope/<int:donation_id>/<int:num_people>")
def chope(donation_id, num_people):
    donation = Donation.query.get_or_404(donation_id)
    # show chope.html with all details
    return render_template("chope.html", donation=donation, num_people=num_people)

# steph: a chope_form route that uses booking
@app.route("/chope_form/<int:donation_id>", methods=["GET", "POST"])
def chope_form(donation_id):
    from models import Booking  # need to import booking
    donation = Donation.query.get_or_404(donation_id)

    if donation.status == DonationStatus.FULLY_BOOKED:
        flash("This donation is already fully booked.", "danger")
        return redirect(url_for("view_donations"))

    if "user_id" not in session:
        flash("You must be logged in to book a donation.", "danger")
        return redirect(url_for("login"))

    # if only want recipients to book
    if session.get("role") != "recipient":
        flash("Only recipients can book a donation.", "danger")
        return redirect(url_for("view_donations"))

    # check if a booking already exists for user n donation etc.
    existing_booking = Booking.query.filter_by(
        user_id=session["user_id"],
        donation_id=donation.id
    ).first()
    if existing_booking:
        flash("You have already booked this donation.", "warning")
        return redirect(url_for("my_bookings"))  # send them to my bookings page

    if request.method == "POST":
        try:
            num_people = int(request.form["num_people"])
            if num_people <= 0:
                flash("Please enter a valid number of people.", "danger")
                return redirect(url_for("chope_form", donation_id=donation.id))

            success = donation.reserve_slot(num_people)
            if success:
                # new booking record
                new_booking = Booking(
                    user_id=session["user_id"],
                    donation_id=donation.id,
                    num_people=num_people
                )
                db.session.add(new_booking)
                db.session.commit()

                flash(f"{num_people} slot(s) reserved successfully!", "success")
                return redirect(url_for("my_bookings"))  # summary page
            else:
                flash("Not enough slots available.", "danger")
                return redirect(url_for("chope_form", donation_id=donation.id))
        except ValueError:
            flash("Invalid number of people.", "danger")
            return redirect(url_for("chope_form", donation_id=donation.id))

    return render_template("chope_form.html", donation=donation)

# steph: bookings page
@app.route("/my_bookings")
def my_bookings():
    from models import Booking
    if "user_id" not in session:
        flash("You must be logged in to view bookings.", "danger")
        return redirect(url_for("login"))
    if session.get("role") != "recipient":
        flash("Only recipients can view bookings.", "danger")
        return redirect(url_for("view_donations"))

    user_id = session["user_id"]
    user_bookings = Booking.query.filter_by(user_id=user_id).all()
    return render_template("my_bookings.html", bookings=user_bookings)

# danyl logout route
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # create the database, i think we leave this in for the git bah
    app.run(debug=True)
