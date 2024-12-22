
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import enum
from sqlalchemy import Enum as SQLAlchemyEnum

db = SQLAlchemy()

class DonationStatus(enum.Enum):  
    AVAILABLE = "available"
    FULLY_BOOKED = "fully booked"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True, index=True)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # donor or recipient
    location = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    #donor relationship
    donations = db.relationship('Donation', backref='donor', lazy=True)
    #receipient relationship
    bookings = db.relationship('Booking', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}, Role: {self.role}, Location: {self.location}>'

class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_name = db.Column(db.String(150), nullable=False)
    food_item = db.Column(db.String(255), nullable=False)
    meal_type = db.Column(db.String(50), nullable=False)
    special_diet = db.Column(db.String(50), nullable=True)
    quota = db.Column(db.Integer, nullable=False)
    bookings = db.Column(db.Integer, default=0, nullable=False)
    address = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(SQLAlchemyEnum(DonationStatus), nullable=False, default=DonationStatus.AVAILABLE)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

    # booking relationship
    booking_records = db.relationship('Booking', backref='donation', lazy=True)

    def remaining_quota(self):
        return max(0, self.quota - self.bookings)

    def reserve_slot(self, slots=1):
        if self.remaining_quota() >= slots:
            self.bookings += slots
            if self.remaining_quota() == 0:
                self.status = DonationStatus.FULLY_BOOKED
            else:
                self.status = DonationStatus.AVAILABLE
            db.session.commit()
            return True
        return False

    def cancel_reservation(self, slots=1):
        if slots <= self.bookings:
            self.bookings -= slots
            if self.remaining_quota() > 0:
                self.status = DonationStatus.AVAILABLE
            else:
                self.status = DonationStatus.FULLY_BOOKED
            db.session.commit()
            return True
        return False

    def __repr__(self):
        return (f'<Donation Restaurant: {self.restaurant_name}, Foods: {self.food_item}, '
                f'Meal Type: {self.meal_type}, Special Diet: {self.special_diet}, '
                f'Quota: {self.quota}, Bookings: {self.bookings}, '
                f'Address: {self.address}, Status: {self.status}>')

class Booking(db.Model):
    """Tracks which recipient booked which donation, and how many people."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    donation_id = db.Column(db.Integer, db.ForeignKey('donation.id'), nullable=False)
    num_people = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return (f"<Booking user_id={self.user_id}, donation_id={self.donation_id}, "
                f"num_people={self.num_people}>")

@db.event.listens_for(Donation, "before_insert")
@db.event.listens_for(Donation, "before_update")
def validate_donation(mapper, connection, target):
    if target.quota is None or target.quota < 0:
        raise ValueError("Quota must be a non-negative integer.")
    if target.bookings is None or target.bookings < 0:
        raise ValueError("Bookings cannot be negative.")
    if target.bookings > target.quota:
        raise ValueError("Bookings cannot exceed quota.")
    if target.latitude is not None and not (-90 <= target.latitude <= 90):
        raise ValueError("Latitude must be between -90 and 90.")
    if target.longitude is not None and not (-180 <= target.longitude <= 180):
        raise ValueError("Longitude must be between -180 and 180.")
