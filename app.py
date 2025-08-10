from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_migrate import Migrate


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ---------- DATABASE MODELS ----------
class Product(db.Model):
    product_id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Location(db.Model):
    location_id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class ProductMovement(db.Model):
    __tablename__ = 'product_movement'

    movement_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    from_location_id = db.Column(db.String(50), db.ForeignKey('location.location_id'), nullable=True)
    to_location_id = db.Column(db.String(50), db.ForeignKey('location.location_id'), nullable=True)

    product_id = db.Column(db.String(50), db.ForeignKey('product.product_id'), nullable=False)
    qty = db.Column(db.Integer, nullable=False)

    # Relationships
    product = db.relationship('Product', backref='movements')
    from_location = db.relationship('Location', foreign_keys=[from_location_id])
    to_location = db.relationship('Location', foreign_keys=[to_location_id])


# ---------- CREATE TABLES ----------
with app.app_context():
    db.create_all()


@app.route('/products')
def list_products():
    products = Product.query.all()
    return render_template('products.html', products=products)

@app.route('/product/add', methods=['POST'])
def add_product():
    product_id = request.form['product_id']
    name = request.form['name']
    # Check for duplicate product_id
    if Product.query.get(product_id):
        return {"status": "error", "message": "Product ID already exists."}, 400
    product = Product(product_id=product_id, name=name)
    db.session.add(product)
    db.session.commit()
    return {"status": "success"}

@app.route("/products/update/<product_id>", methods=["POST"])
def update_product(product_id):
    data = request.get_json()
    product = Product.query.get_or_404(product_id)
    if "name" in data:
        product.name = data["name"]
    db.session.commit()
    return {"status": "success"}

@app.route('/locations')
def list_locations():
    locations = Location.query.all()
    return render_template('locations.html', locations=locations)

@app.route('/location/add', methods=['POST'])
def add_location():
    location_id = request.form['location_id']
    name = request.form['name']
    # Check for duplicate location_id
    if Location.query.get(location_id):
        return {"status": "error", "message": "Location ID already exists."}, 400
    location = Location(location_id=location_id, name=name)
    db.session.add(location)
    db.session.commit()
    return {"status": "success"}

@app.route("/locations/update/<location_id>", methods=["POST"])
def update_location(location_id):
    data = request.get_json()
    location = Location.query.get_or_404(location_id)
    if "name" in data:
        location.name = data["name"]
    db.session.commit()
    return {"status": "success"}

from datetime import datetime

@app.route("/movements")
def list_movements():
    products = [{"product_id": p.product_id, "name": p.name} for p in Product.query.all()]
    locations = [{"location_id": l.location_id, "name": l.name} for l in Location.query.all()]
    
    movements = []
    for m in ProductMovement.query.all():
        ts = m.timestamp
        if isinstance(ts, str):  # If stored as string, parse it
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                ts = None
        
        # Format timestamp properly for display
        if ts:
            # For display in table
            display_ts = ts.strftime("%Y-%m-%d | %H:%M")
            # For datetime-local input (needs to be in format YYYY-MM-DDTHH:MM)
            input_ts = ts.strftime("%Y-%m-%dT%H:%M").replace("T", " | ")

        else:
            display_ts = ""
            input_ts = ""
        movements.append({
            "movement_id": m.movement_id,
            "timestamp": display_ts,
            "timestamp_input": input_ts,  # Add this for the input field
            "product_id": m.product_id,
            "product_name": m.product.name,
            "from_location_id": m.from_location_id,
            "from_location_name": m.from_location.name if m.from_location else None,
            "to_location_id": m.to_location_id,
            "to_location_name": m.to_location.name if m.to_location else None,
            "qty": m.qty
        })

    return render_template("movements.html",
                           products=products,
                           locations=locations,
                           movements=movements)


@app.route('/movement/add', methods=['POST'])
def add_movement():
    from_location = request.form.get('from_location') or None
    to_location = request.form.get('to_location') or None
    product_id = request.form['product_id']
    try:
        qty = int(request.form['qty'])
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid quantity."}, 400
    movement = ProductMovement(
        from_location_id=from_location,
        to_location_id=to_location,
        product_id=product_id,
        qty=qty
    )
    db.session.add(movement)
    db.session.commit()
    return {"status": "success"}



@app.route("/movements/update/<int:movement_id>", methods=["POST"])

def update_movement(movement_id):
    data = request.get_json()
    movement = ProductMovement.query.get_or_404(movement_id)

    if "product_id" in data:
        movement.product_id = data["product_id"]
    if "from_location_id" in data:
        movement.from_location_id = data["from_location_id"] or None
    if "to_location_id" in data:
        movement.to_location_id = data["to_location_id"] or None
    if "qty" in data:
        try:
            movement.qty = int(data["qty"])
        except (ValueError, TypeError):
            return {"status": "error", "message": "Invalid quantity"}, 400
    if "timestamp" in data:
        try:
            # Incoming format from datetime-local input is "YYYY-MM-DDTHH:mm"
            movement.timestamp = datetime.strptime(data["timestamp"], "%Y-%m-%dT%H:%M")
        except (ValueError, TypeError):
            return {"status": "error", "message": "Invalid timestamp"}, 400

    db.session.commit()
    return {"status": "success"}


@app.route('/')
def report():
    products = Product.query.all()
    locations = Location.query.all()

    balance = []

    for product in products:
        for location in locations:
            # Qty in (items moved into this location for this product)
            in_qty = db.session.query(db.func.sum(ProductMovement.qty)).filter(
                ProductMovement.product_id == product.product_id,
                ProductMovement.to_location_id == location.location_id
            ).scalar() or 0

            # Qty out (items moved out of this location for this product)
            out_qty = db.session.query(db.func.sum(ProductMovement.qty)).filter(
                ProductMovement.product_id == product.product_id,
                ProductMovement.from_location_id == location.location_id
            ).scalar() or 0

            balance.append({
                'product': product.name,
                'location': location.name,
                'qty': in_qty - out_qty
            })

    return render_template('report.html', balance=balance)

