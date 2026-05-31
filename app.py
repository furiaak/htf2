from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, date, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'dev-secret-key-12345'
import os

# Use PostgreSQL for both dev and prod
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    # Local development - adjust password if yours is different
    database_url = 'postgresql://postgres:010107@localhost:5432/inventory_dev'

if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ========== MODELS ==========

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    warehouse = db.relationship('Warehouse', backref='users')

class Warehouse(db.Model):
    __tablename__ = 'warehouses'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    store_code = db.Column(db.String(3), nullable=False)
    warehouse_type = db.Column(db.String(20), nullable=False)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Ingredient(db.Model):
    __tablename__ = 'ingredients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    base_unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    is_approved = db.Column(db.Boolean, default=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    base_unit = db.relationship('Unit', foreign_keys=[base_unit_id], post_update=True)

class Unit(db.Model):
    __tablename__ = 'units'
    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False)
    alt_unit = db.Column(db.String(10), nullable=False)
    conversion_to_base = db.Column(db.Float, nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ingredient = db.relationship('Ingredient', foreign_keys=[ingredient_id], backref='units')

class StockSetting(db.Model):
    __tablename__ = 'stock_settings'
    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False)
    min_quantity_base = db.Column(db.Float, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class InventoryBalance(db.Model):
    __tablename__ = 'inventory_balance'
    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False)
    balance_base = db.Column(db.Float, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    ingredient = db.relationship('Ingredient')
    warehouse = db.relationship('Warehouse')

class Movement(db.Model):
    __tablename__ = 'movements'
    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False)
    direction = db.Column(db.String(3), nullable=False)
    movement_type = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'), nullable=False)
    quantity_base = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    note = db.Column(db.Text)
    origin_destination = db.Column(db.String(200))
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    move_request_id = db.Column(db.Integer, db.ForeignKey('move_requests.id'))  # ADD THIS LINE
    status = db.Column(db.String(20), default='completed')
    
    # Relationships
    ingredient = db.relationship('Ingredient')
    unit = db.relationship('Unit')
    warehouse = db.relationship('Warehouse')
    created_by = db.relationship('User')
    move_request = db.relationship('MoveRequest')  # ADD THIS LINE

class MoveRequest(db.Model):
    __tablename__ = 'move_requests'
    id = db.Column(db.Integer, primary_key=True)
    from_warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    to_warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    request_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='PENDING')
    requested_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    movement_type = db.Column(db.String(20), default='transfer')
    
    # Relationships
    from_warehouse = db.relationship('Warehouse', foreign_keys=[from_warehouse_id])
    to_warehouse = db.relationship('Warehouse', foreign_keys=[to_warehouse_id])
    requested_by = db.relationship('User', foreign_keys=[requested_by_user_id])

class MoveRequestItem(db.Model):
    __tablename__ = 'move_request_items'
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('move_requests.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False)
    quantity_requested = db.Column(db.Float, nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'), nullable=False)
    
    # Relationships
    request = db.relationship('MoveRequest', backref='items')
    ingredient = db.relationship('Ingredient')
    unit = db.relationship('Unit')

# ========== HELPER FUNCTIONS ==========

def get_default_unit(ingredient, direction, movement_type=None):
    units = ingredient.units
    if not units:
        return None
    
    if direction == 'IN':
        return max(units, key=lambda u: u.rank)
    else:  # OUT
        if movement_type == 'production':
            return min(units, key=lambda u: u.rank)  # lowest (box)
        else:
            return max(units, key=lambda u: u.rank)  # highest (carton)

def format_quantity(base_quantity, ingredient):
    if not ingredient.units:
        return f"{base_quantity} units"
    units_sorted = sorted(ingredient.units, key=lambda u: u.rank, reverse=True)
    result = []
    remaining = base_quantity
    for unit in units_sorted:
        if unit.rank == 1:
            if remaining > 0 or not result:
                result.append(f"{int(remaining)} {unit.alt_unit}")
            break
        else:
            unit_value = unit.conversion_to_base
            count = int(remaining // unit_value)
            if count > 0:
                result.append(f"{count} {unit.alt_unit}")
                remaining = remaining % unit_value
    return ', '.join(result)

def get_low_stock(warehouse_id):
    results = db.session.query(
        Ingredient,
        InventoryBalance.balance_base,
        StockSetting.min_quantity_base
    ).join(
        InventoryBalance, InventoryBalance.ingredient_id == Ingredient.id
    ).join(
        StockSetting, StockSetting.ingredient_id == Ingredient.id
    ).filter(
        InventoryBalance.warehouse_id == warehouse_id,
        StockSetting.warehouse_id == warehouse_id,
        InventoryBalance.balance_base < StockSetting.min_quantity_base
    ).all()
    return results

def get_ingredients_with_units(warehouse_id):
    """Return all approved ingredients with units and stock balance (only stock > 0)"""
    ingredients = Ingredient.query.filter_by(is_approved=True).order_by(Ingredient.name).all()
    
    result = []
    for ing in ingredients:
        # Get current stock balance for this warehouse
        balance = InventoryBalance.query.filter_by(
            warehouse_id=warehouse_id,
            ingredient_id=ing.id
        ).first()
        
        current_stock = balance.balance_base if balance else 0
        
        # SKIP if stock is 0
        if current_stock <= 0:
            continue
        
        # Get all units for this ingredient
        units = []
        for unit in ing.units:
            units.append({
                'id': unit.id,
                'alt_unit': unit.alt_unit,
                'rank': unit.rank,
                'conversion_to_base': unit.conversion_to_base
            })
        
        result.append({
            'id': ing.id,
            'name': ing.name,
            'units': units,
            'current_stock': current_stock,
            'display_stock': format_quantity(current_stock, ing) if current_stock > 0 else "0"
        })
    
    return result

# ========== ROUTES ==========
@app.route('/move_request/reject/<int:request_id>', methods=['POST'])
def reject_move_request(request_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    if session['role'] not in ['WH_PIC', 'ST_MGR']:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
    
    move_request = MoveRequest.query.get_or_404(request_id)
    
    if move_request.status != 'PENDING':
        return jsonify({'success': False, 'message': 'Only pending requests can be rejected'}), 400
    
    move_request.status = 'REJECTED'
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Request rejected'})
    
@app.route('/move_request/fulfill/<int:request_id>', methods=['GET', 'POST'])
def fulfill_move_request(request_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    #if session['role'] not in ['WH_PIC', 'ST_MGR']:
    #    flash('Only warehouse or store PIC can fulfill requests')
    #    return redirect(url_for('current_stock'))
    
    move_request = MoveRequest.query.get_or_404(request_id)
    
    if move_request.status != 'PENDING':
        flash('This request is no longer pending')
        return redirect(url_for('pending_move_requests'))
    
    if request.method == 'POST':
        try:
            date_str = request.form['date']
            fulfillment_note = request.form.get('note', '')
            
            # Validate date
            try:
                fulfillment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format')
                return redirect(url_for('fulfill_move_request', request_id=request_id))
            
            all_fulfilled = True
            any_fulfilled = False
            has_error = False
            
            # Store items to process to avoid modification during iteration
            items_to_process = []
            
            for item in move_request.items:
                qty_key = f'qty_{item.ingredient_id}'
                
                if qty_key in request.form and request.form[qty_key]:
                    try:
                        actual_qty = float(request.form[qty_key])
                        if actual_qty < 0:
                            ingredient = Ingredient.query.get(item.ingredient_id)
                            flash(f'Quantity cannot be negative for {ingredient.name if ingredient else "item"}')
                            has_error = True
                            break
                    except ValueError:
                        ingredient = Ingredient.query.get(item.ingredient_id)
                        flash(f'Invalid quantity value for {ingredient.name if ingredient else "item"}')
                        has_error = True
                        break
                    
                    try:
                        unit_id = int(request.form[f'unit_{item.ingredient_id}'])
                    except (ValueError, TypeError):
                        flash('Invalid unit selection')
                        has_error = True
                        break
                else:
                    actual_qty = 0
                    unit_id = item.unit_id
                
                items_to_process.append({
                    'item': item,
                    'actual_qty': actual_qty,
                    'unit_id': unit_id
                })
            
            if has_error:
                return redirect(url_for('fulfill_move_request', request_id=request_id))
            
            # Check if any item has valid quantity
            if not any(item['actual_qty'] > 0 for item in items_to_process):
                flash('Please enter at least one quantity greater than zero')
                return redirect(url_for('fulfill_move_request', request_id=request_id))
            
            # Process each item
            for item_data in items_to_process:
                item = item_data['item']
                actual_qty = item_data['actual_qty']
                unit_id = item_data['unit_id']
                
                if actual_qty > 0:
                    any_fulfilled = True
                    # Explicit update instead of attribute assignment
                    db.session.query(MoveRequestItem).filter(
                        MoveRequestItem.id == item.id
                    ).update({
                        'unit_id': unit_id
                    })
                    
                    # Get unit conversion
                    unit = Unit.query.get(unit_id)
                    if not unit:
                        flash(f'Invalid unit for {item.ingredient.name}')
                        db.session.rollback()
                        return redirect(url_for('fulfill_move_request', request_id=request_id))
                    
                    quantity_base = actual_qty * unit.conversion_to_base
                    
                    # Check if source has enough stock
                    from_balance = InventoryBalance.query.filter_by(
                        warehouse_id=move_request.from_warehouse_id,
                        ingredient_id=item.ingredient_id
                    ).first()
                    
                    current_stock = from_balance.balance_base if from_balance else 0
                    if quantity_base > current_stock:
                        flash(f'Insufficient stock in {move_request.from_warehouse.name} for {item.ingredient.name}. Available: {format_quantity(current_stock, item.ingredient)}')
                        db.session.rollback()
                        return redirect(url_for('fulfill_move_request', request_id=request_id))
                    
                    # Use movement_type from the request
                    movement_type = move_request.movement_type
                    is_own_production = (move_request.movement_type == 'production' and move_request.from_warehouse_id == move_request.requested_by.warehouse_id)
                    # Create OUT movement from source warehouse
                    out_movement = Movement(
                        warehouse_id=move_request.from_warehouse_id,
                        ingredient_id=item.ingredient_id,
                        direction='OUT',
                        movement_type=movement_type,
                        quantity=actual_qty,
                        unit_id=unit_id,
                        quantity_base=quantity_base,
                        date=fulfillment_date,
                        note=f"Move Request #{request_id} fulfillment. {fulfillment_note}",
                        origin_destination=f"To {move_request.to_warehouse.name}",
                        created_by_user_id=session['user_id'],
                        move_request_id=request_id,
                        status='completed' 
                    )
                    db.session.add(out_movement)
                    
                    if not is_own_production:
                        # Create IN movement as pending (for case 3b or normal transfer)
                        in_movement = Movement(
                            warehouse_id=move_request.to_warehouse_id,
                            ingredient_id=item.ingredient_id,
                            direction='IN',
                            movement_type=move_request.movement_type,  # 'production'
                            quantity=actual_qty,
                            unit_id=unit_id,
                            quantity_base=quantity_base,
                            date=fulfillment_date,
                            note=f"Move Request #{request_id} fulfillment. {fulfillment_note}",
                            origin_destination=f"From {move_request.from_warehouse.name}",
                            created_by_user_id=session['user_id'],
                            move_request_id=request_id,
                            status='pending'
                        )
                        db.session.add(in_movement)
                    else:
                        # For own production, no IN movement; request will be completed after all items
                        pass
                    
                    # Update inventory balances
                    # Source warehouse (OUT)
                    if from_balance:
                        from_balance.balance_base -= quantity_base
                        from_balance.last_updated = datetime.now(timezone.utc)
                    
                    # Destination warehouse (IN) - stock NOT added yet, pending receipt confirmation
                    to_balance = InventoryBalance.query.filter_by(
                        warehouse_id=move_request.to_warehouse_id,
                        ingredient_id=item.ingredient_id
                    ).first()
                    if not to_balance:
                        to_balance = InventoryBalance(
                            warehouse_id=move_request.to_warehouse_id,
                            ingredient_id=item.ingredient_id,
                            balance_base=0
                        )
                        db.session.add(to_balance)
                    # DO NOT add stock here — remove the line that adds quantity_base
                    to_balance.last_updated = datetime.now(timezone.utc)
                    
                elif item.quantity_requested > 0:
                    all_fulfilled = False
            
            # Update request status
            if is_own_production and all_fulfilled:
                move_request.status = 'COMPLETED'
            elif all_fulfilled and any_fulfilled:
                move_request.status = 'IN_TRANSIT'
            elif any_fulfilled:
                move_request.status = 'PARTIAL'
            else:
                move_request.status = 'PENDING'
            
            db.session.commit()
            flash(f'Move Request #{request_id} fulfilled successfully')
            return redirect(url_for('pending_move_requests'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}')
            return redirect(url_for('fulfill_move_request', request_id=request_id))
    
    # GET request - show form
    request_items = move_request.items
    today = date.today().isoformat()
    
    return render_template('fulfill_move_request.html',
                          move_request=move_request,
                          request_items=request_items,
                          today=today)

@app.route('/move_requests/pending')
def pending_move_requests():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # if session['role'] not in ['WH_PIC', 'ST_MGR']:
    #    flash('Only warehouse PIC can view pending requests')
    #    return redirect(url_for('current_stock'))
    
    warehouse_id = session['warehouse_id']
    
    pending_reqs = MoveRequest.query.filter_by(
        from_warehouse_id=warehouse_id,
        status='PENDING'
    ).order_by(MoveRequest.request_date).all()
    
    return render_template('pending_move_requests.html', requests=pending_reqs)

@app.route('/request/create/<string:type>', methods=['GET', 'POST'])
def create_request(type):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Permission check
    # if type == 'incoming':
    #    if session['role'] not in ['ST_MGR', 'ST_REQ']:
    #        flash('Only store managers and requestors can create incoming requests')
    #        return redirect(url_for('current_stock'))
    # elif type == 'outgoing':
    #   if session['role'] != 'WH_PIC':
    #        flash('Only warehouse PIC can create outgoing requests')
    #        return redirect(url_for('current_stock'))
    # else:
    #    flash('Invalid request type')
    #    return redirect(url_for('request_type'))
    
    user_id = session['user_id']
    my_warehouse_id = session['warehouse_id']
    my_warehouse = Warehouse.query.get(my_warehouse_id)  # FIX: added this line
    
    if request.method == 'POST':
        date_str = request.form['date']
        note = request.form.get('note', '')
       
        movement_type = request.form.get('movement_type', 'transfer')
        if type in ['incoming', 'outgoing']:
            movement_type = 'transfer'
        elif type == 'production':
            movement_type = 'production'

        if type == 'incoming':
            to_warehouse_id = my_warehouse_id
            try:
                from_warehouse_id = int(request.form['from_warehouse_id'])
            except (ValueError, TypeError):
                flash('Please select a source warehouse')
                return redirect(url_for('create_request', type=type))

        elif type == 'outgoing':
            from_warehouse_id = my_warehouse_id
            try:
                to_warehouse_id = int(request.form['to_warehouse_id'])
            except (ValueError, TypeError):
                flash('Please select a destination warehouse')
                return redirect(url_for('create_request', type=type))

        else:  # production
            to_warehouse_id = my_warehouse_id
            try:
                from_warehouse_id = int(request.form['from_warehouse_id'])
            except (ValueError, TypeError):
                flash('Please select a source warehouse for production')
                return redirect(url_for('create_request', type=type))
        
        # Validate date
        try:
            request_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format')
            return redirect(url_for('create_request', type=type))
       
        # Check if warehouse exists
        if type == 'incoming':
            source_warehouse = Warehouse.query.get(from_warehouse_id)
            if not source_warehouse:
                flash('Selected warehouse does not exist')
                return redirect(url_for('create_request', type=type))
        else:
            dest_warehouse = Warehouse.query.get(to_warehouse_id)
            if not dest_warehouse:
                flash('Selected destination does not exist')
                return redirect(url_for('create_request', type=type))
        
        # Collect and validate items
        items = []
        has_error = False
        
        for key, value in request.form.items():
            if key.startswith('qty_') and value:
                try:
                    quantity = float(value)
                    if quantity < 0:
                        flash('Quantity cannot be negative')
                        has_error = True
                        break
                    if quantity == 0:
                        continue
                except ValueError:
                    flash('Invalid quantity value')
                    has_error = True
                    break
                
                ingredient_id = int(key.split('_')[1])
                unit_id = int(request.form[f'unit_{ingredient_id}'])
                
                # For outgoing: check if source has enough stock
                if type == 'outgoing':
                    balance = InventoryBalance.query.filter_by(
                        warehouse_id=from_warehouse_id,
                        ingredient_id=ingredient_id
                    ).first()
                    current_stock = balance.balance_base if balance else 0
                    
                    unit = Unit.query.get(unit_id)
                    quantity_base = quantity * unit.conversion_to_base
                    
                    if quantity_base > current_stock:
                        ingredient = Ingredient.query.get(ingredient_id)
                        flash(f'Insufficient stock for {ingredient.name}. Available: {format_quantity(current_stock, ingredient)}')
                        has_error = True
                        break
                
                items.append({
                    'ingredient_id': ingredient_id,
                    'unit_id': unit_id,
                    'quantity': quantity
                })
        
        if has_error:
            return redirect(url_for('create_request', type=type))
        
        if not items:
            flash('Please request at least one item')
            return redirect(url_for('create_request', type=type))
        
        # Create move request
        new_request = MoveRequest(
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            request_date=request_date,
            movement_type=movement_type,
            status='PENDING',
            requested_by_user_id=user_id,
            note=note
        )
        db.session.add(new_request)
        db.session.commit()
        
        # Add request items
        for item in items:
            request_item = MoveRequestItem(
                request_id=new_request.id,
                ingredient_id=item['ingredient_id'],
                quantity_requested=item['quantity'],
                unit_id=item['unit_id']
            )
            db.session.add(request_item)
        
        db.session.commit()
        
        # For outgoing: immediately deduct stock and create movements
        if type == 'outgoing':
            try:
                for item in items:
                    unit = Unit.query.get(item['unit_id'])
                    quantity_base = item['quantity'] * unit.conversion_to_base
                    
                    # Create OUT movement from source
                    out_movement = Movement(
                        warehouse_id=from_warehouse_id,
                        ingredient_id=item['ingredient_id'],
                        direction='OUT',
                        movement_type=movement_type,
                        quantity=item['quantity'],
                        unit_id=item['unit_id'],
                        quantity_base=quantity_base,
                        date=request_date,
                        note=f"Outgoing request #{new_request.id}: {note}",
                        origin_destination=f"To {dest_warehouse.name}",
                        created_by_user_id=user_id,
                        move_request_id=new_request.id,
                        status='completed'
                    )
                    db.session.add(out_movement)
                    
                    # Create IN movement (pending confirmation)
                    in_movement = Movement(
                        warehouse_id=to_warehouse_id,
                        ingredient_id=item['ingredient_id'],
                        direction='IN',
                        movement_type=movement_type,
                        quantity=item['quantity'],
                        unit_id=item['unit_id'],
                        quantity_base=quantity_base,
                        date=request_date,
                        note=f"Outgoing request #{new_request.id}: {note}",
                        origin_destination=f"From {my_warehouse.name}",  # FIX: now my_warehouse is defined
                        created_by_user_id=user_id,
                        move_request_id=new_request.id,
                        status='pending'
                    )
                    db.session.add(in_movement)
                    
                    # Deduct from source balance
                    source_balance = InventoryBalance.query.filter_by(
                        warehouse_id=from_warehouse_id,
                        ingredient_id=item['ingredient_id']
                    ).first()
                    if source_balance:
                        source_balance.balance_base -= quantity_base
                        source_balance.last_updated = datetime.utcnow()
                
                new_request.status = 'IN_TRANSIT'
                db.session.commit()
                flash(f'Outgoing request #{new_request.id} created. Stock deducted from your warehouse.')
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating movements: {str(e)}')
                return redirect(url_for('current_stock'))
        else:
            flash(f'Request #{new_request.id} created successfully')
        
        return redirect(url_for('my_move_requests'))
    
    # GET request - show form
    today = date.today().isoformat()
    
    if type == 'incoming':
        # Show other warehouses as source
        warehouses = Warehouse.query.filter(Warehouse.id != my_warehouse_id).all()
        selected_warehouse_id = request.args.get('from_warehouse_id', type=int)
        if not selected_warehouse_id and warehouses:
            selected_warehouse_id = warehouses[0].id
        
        ingredients_data = []
        if selected_warehouse_id:
            ingredients_data = get_ingredients_with_units(selected_warehouse_id)
            for ing in ingredients_data:
                if ing['units']:
                    default_unit = max(ing['units'], key=lambda u: u['rank'])
                    ing['default_unit_id'] = default_unit['id']
        
        return render_template('create_move_request.html',
                              ingredients=ingredients_data,
                              warehouses=warehouses,
                              selected_warehouse_id=selected_warehouse_id,
                              warehouse=my_warehouse,
                              today=today,
                              movement_type='transfer',
                              request_type=type)


    elif type == 'production':
        # Show all warehouses as possible sources
        warehouses = Warehouse.query.all()
        selected_warehouse_id = request.args.get('from_warehouse_id', type=int)
        if not selected_warehouse_id and warehouses:
            selected_warehouse_id = warehouses[0].id
        
        ingredients_data = []
        if selected_warehouse_id:
            # Get all approved ingredients
            ingredients = Ingredient.query.filter_by(is_approved=True).order_by(Ingredient.name).all()
            for ing in ingredients:
                # Check stock in the selected source warehouse
                balance = InventoryBalance.query.filter_by(
                    warehouse_id=selected_warehouse_id,
                    ingredient_id=ing.id
                ).first()
                current_stock = balance.balance_base if balance else 0
                if current_stock <= 0:
                    continue  # Only show items with stock > 0
                
                # Prepare units for this ingredient
                units = []
                for unit in ing.units:
                    units.append({
                        'id': unit.id,
                        'alt_unit': unit.alt_unit,
                        'rank': unit.rank,
                        'conversion_to_base': unit.conversion_to_base
                    })
                default_unit = max(units, key=lambda u: u['rank']) if units else None
                ingredients_data.append({
                    'id': ing.id,
                    'name': ing.name,
                    'units': units,
                    'default_unit_id': default_unit['id'] if default_unit else None,
                    'display_stock': format_quantity(current_stock, ing)
                })
        
        return render_template('create_production_request.html',
                              ingredients=ingredients_data,
                              warehouses=warehouses,
                              selected_warehouse_id=selected_warehouse_id,
                              warehouse=my_warehouse,
                              today=today,
                              request_type=type)

    
    else:  # outgoing
        # Show other warehouses as destination
        warehouses = Warehouse.query.filter(Warehouse.id != my_warehouse_id).all()
        selected_warehouse_id = request.args.get('to_warehouse_id', type=int)
        if not selected_warehouse_id and warehouses:
            selected_warehouse_id = warehouses[0].id
        
        # Show only ingredients with stock > 0
        ingredients_data = []
        ingredients = Ingredient.query.filter_by(is_approved=True).order_by(Ingredient.name).all()
        
        for ing in ingredients:
            balance = InventoryBalance.query.filter_by(
                warehouse_id=my_warehouse_id,
                ingredient_id=ing.id
            ).first()
            current_stock = balance.balance_base if balance else 0
            
            if current_stock <= 0:
                continue
            
            units = []
            for unit in ing.units:
                units.append({
                    'id': unit.id,
                    'alt_unit': unit.alt_unit,
                    'rank': unit.rank,
                    'conversion_to_base': unit.conversion_to_base
                })
            
            default_unit = max(units, key=lambda u: u['rank'])
            
            ingredients_data.append({
                'id': ing.id,
                'name': ing.name,
                'units': units,
                'default_unit_id': default_unit['id'],
                'display_stock': format_quantity(current_stock, ing)
            })
        
        return render_template('create_outgoing_request.html',
                              ingredients=ingredients_data,
                              warehouses=warehouses,
                              selected_warehouse_id=selected_warehouse_id,
                              warehouse=my_warehouse,
                              today=today,
                              movement_type='transfer',
                              request_type=type)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter(
            db.func.lower(User.username) == username.lower(),
            User.is_active == True
        ).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['warehouse_id'] = user.warehouse_id
            return redirect(url_for('current_stock'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('current_stock'))

@app.route('/request/create')
def request_type():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('request_type.html')
    
@app.route('/stock')
def current_stock():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_role = session['role']
    user_id = session['user_id']
    
    # Admin sees all warehouses
    if user_role == 'ADMIN':
        # Get all warehouses with their stock
        warehouses = Warehouse.query.order_by(Warehouse.name).all()
        
        stock_by_warehouse = []
        for wh in warehouses:
            balances = db.session.query(
                InventoryBalance, Ingredient
            ).join(
                Ingredient, InventoryBalance.ingredient_id == Ingredient.id
            ).filter(
                InventoryBalance.warehouse_id == wh.id
            ).order_by(Ingredient.name.asc()).all()
            
            stock_list = []
            for balance, ingredient in balances:
                display_qty = format_quantity(balance.balance_base, ingredient)
                stock_list.append({
                    'ingredient': ingredient,
                    'display_qty': display_qty,
                    'balance_base': balance.balance_base
                })
            
            stock_by_warehouse.append({
                'warehouse': wh,
                'stock_list': stock_list
            })
        
        return render_template('hq_stock.html', stock_by_warehouse=stock_by_warehouse)
    
    # Regular users see their assigned warehouse
    warehouse_id = session['warehouse_id']
    warehouse = Warehouse.query.get(warehouse_id)
    
    results = db.session.query(
        InventoryBalance, Ingredient
    ).join(
        Ingredient, InventoryBalance.ingredient_id == Ingredient.id
    ).filter(
        InventoryBalance.warehouse_id == warehouse_id
    ).order_by(Ingredient.name.asc()).all()
    
    stock_list = []
    for balance, ingredient in results:
        display_qty = format_quantity(balance.balance_base, ingredient)
        stock_list.append({
            'ingredient': ingredient,
            'balance_base': balance.balance_base,
            'display_qty': display_qty,
            'low_stock': False
        })
    
    return render_template('current_stock.html', 
                          stock_list=stock_list, 
                          warehouse=warehouse,
                          low_stock_count=0)
                          
@app.route('/movement/history/<int:ingredient_id>')
def movement_history(ingredient_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    warehouse_id = session['warehouse_id']
    ingredient = Ingredient.query.get_or_404(ingredient_id)
    movements = Movement.query.filter(
        Movement.warehouse_id == warehouse_id,
        Movement.ingredient_id == ingredient_id,
        Movement.status == 'completed'  # Only show completed movements
    ).order_by(Movement.date.desc(), Movement.created_at.desc()).all()
    return render_template('movement_history.html', movements=movements, ingredient=ingredient)

@app.route('/add_movement', methods=['GET', 'POST'])
def add_movement():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    warehouse_id = session['warehouse_id']
    user_id = session['user_id']
    
    if request.method == 'POST':
        date_str = request.form['date']
        direction = request.form['direction']
        movement_type = request.form.get('movement_type', '')
        if not movement_type:
            movement_type = 'transfer'  # or any default

        partner = request.form.get('partner', '')
        note = request.form.get('note', '')
        
        # Validate date
        try:
            movement_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format')
            return redirect(url_for('add_movement'))
        
        # Validate direction
        if direction not in ['IN', 'OUT']:
            flash('Invalid direction')
            return redirect(url_for('add_movement'))
        
        # Skip Validate movement type
        
        # Collect and validate items
        items = []
        has_error = False
        
        for key, value in request.form.items():
            if key.startswith('qty_') and value:
                try:
                    quantity = float(value)
                    if quantity < 0:
                        flash('Quantity cannot be negative')
                        has_error = True
                        break
                    if quantity == 0:
                        continue
                except ValueError:
                    flash(f'Invalid quantity value for {key}. Please enter a valid number.')
                    has_error = True
                    break
                
                ingredient_id = int(key.split('_')[1])
                unit_id = int(request.form[f'unit_{ingredient_id}'])
                
                items.append({
                    'ingredient_id': ingredient_id,
                    'unit_id': unit_id,
                    'quantity': quantity
                })
        
        if has_error:
            return redirect(url_for('add_movement'))
        
        if not items:
            flash('No items with valid quantities entered')
            return redirect(url_for('add_movement'))
        
        # Process all valid items
        for item in items:
            unit = Unit.query.get(item['unit_id'])
            if not unit:
                flash(f'Invalid unit selected for ingredient')
                return redirect(url_for('add_movement'))
            
            ingredient = Ingredient.query.get(item['ingredient_id'])
            if not ingredient:
                flash(f'Invalid ingredient')
                return redirect(url_for('add_movement'))
            
            quantity_base = item['quantity'] * unit.conversion_to_base
            
            # For OUT movement, check if enough stock
            if direction == 'OUT':
                balance = InventoryBalance.query.filter_by(
                    warehouse_id=warehouse_id,
                    ingredient_id=item['ingredient_id']
                ).first()
                current_stock = balance.balance_base if balance else 0
                if quantity_base > current_stock:
                    flash(f'Insufficient stock for {ingredient.name}. Available: {format_quantity(current_stock, ingredient)}')
                    return redirect(url_for('add_movement'))
            
            movement = Movement(
                warehouse_id=warehouse_id,
                ingredient_id=item['ingredient_id'],
                direction=direction,
                movement_type=movement_type,
                quantity=item['quantity'],
                unit_id=item['unit_id'],
                quantity_base=quantity_base,
                date=movement_date,
                note=note,
                origin_destination=partner,
                created_by_user_id=user_id,
                status='completed'
            )
            db.session.add(movement)
            
            balance = InventoryBalance.query.filter_by(
                warehouse_id=warehouse_id,
                ingredient_id=item['ingredient_id']
            ).first()
            
            if not balance:
                balance = InventoryBalance(
                    warehouse_id=warehouse_id,
                    ingredient_id=item['ingredient_id'],
                    balance_base=0
                )
                db.session.add(balance)
            
            if direction == 'IN':
                balance.balance_base += quantity_base
            else:
                balance.balance_base -= quantity_base
            
            balance.last_updated = datetime.now(timezone.utc)
        
        db.session.commit()
        flash(f'Recorded {len(items)} item(s) successfully')
        return redirect(url_for('current_stock'))
    
    # GET request - show form
    direction = request.args.get('direction', 'IN')
    movement_type = request.args.get('movement_type', '')
    if not movement_type:
        movement_type = ''
    warehouse = Warehouse.query.get(warehouse_id)

    # Get all ingredients with their units
    ingredients = Ingredient.query.filter_by(is_approved=True).order_by(Ingredient.name).all()

    ingredient_data = []
    for ing in ingredients:
        # Get current stock for this warehouse
        balance = InventoryBalance.query.filter_by(
            warehouse_id=warehouse_id,
            ingredient_id=ing.id
        ).first()
        
        current_stock = balance.balance_base if balance else 0
        
        # Skip if stock is 0 for OUT movements (show all for IN)
        if direction == 'OUT' and current_stock <= 0:
            continue
        
        units_list = []
        for unit in ing.units:
            units_list.append({
                'id': unit.id,
                'alt_unit': unit.alt_unit,
                'rank': unit.rank,
                'conversion_to_base': unit.conversion_to_base
            })
        
        class FakeIngredient:
            def __init__(self, units):
                self.units = units
        
        fake_ing = FakeIngredient(ing.units)
        default_unit = get_default_unit(fake_ing, direction, movement_type)

        print(f"DEBUG: Ingredient: {ing.name}")
        print(f"DEBUG: Units: {[(u.alt_unit, u.rank) for u in ing.units]}")
        print(f"DEBUG: Direction: {direction}, Movement type: {movement_type}")
        print(f"DEBUG: Default unit: {default_unit.alt_unit if default_unit else None}")
        print("---")  

  
        ingredient_data.append({
            'id': ing.id,
            'name': ing.name,
            'units': units_list,
            'default_unit_id': default_unit.id if default_unit else None,
            'display_stock': format_quantity(current_stock, ing) if current_stock > 0 else "0"
        })

    return render_template('add_movement.html',
                          ingredients=ingredient_data,
                          warehouse=warehouse,
                          today=date.today().isoformat(),
                          direction=direction,
                          movement_type=movement_type)

@app.route('/move_requests/my')
def my_move_requests():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Get all move requests created by this user
    my_requests = MoveRequest.query.filter_by(
        requested_by_user_id=user_id
    ).order_by(MoveRequest.request_date.desc(), MoveRequest.id.desc()).all()
    
    # For each request, enrich items with actual received quantity from movements
    for req in my_requests:
        for item in req.items:
            # Get the actual received quantity from IN movement
            received_movement = Movement.query.filter(
                Movement.move_request_id == req.id,
                Movement.ingredient_id == item.ingredient_id,
                Movement.direction == 'IN',
                Movement.status == 'completed'
            ).first()
            
            item.received_quantity = received_movement.quantity if received_movement else 0
            item.received_unit = received_movement.unit if received_movement else item.unit
    
    return render_template('my_move_requests.html', requests=my_requests)

@app.route('/move_request/edit/<int:request_id>', methods=['GET', 'POST'])
def edit_move_request(request_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session['role'] not in ['ST_REQ', 'ST_MGR']:
        flash('Only request creators can edit move requests')
        return redirect(url_for('current_stock'))
    
    move_request = MoveRequest.query.get_or_404(request_id)
    
    # Check ownership
    if move_request.requested_by_user_id != session['user_id']:
        flash('You can only edit your own move requests')
        return redirect(url_for('my_move_requests'))
    
    # Check status
    if move_request.status != 'PENDING':
        flash('Only pending move requests can be edited')
        return redirect(url_for('my_move_requests'))
    
    if request.method == 'POST':
        date_str = request.form['date']
        note = request.form.get('note', '')
        
        # Validate date
        try:
            request_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format')
            return redirect(url_for('edit_move_request', request_id=request_id))
        
        # Collect and validate items
        items_to_save = []
        has_error = False
        
        for key, value in request.form.items():
            if key.startswith('qty_') and value:
                ingredient_id = int(key.split('_')[1])
                
                # Validate quantity is a number and positive
                try:
                    quantity = float(value)
                    if quantity < 0:
                        flash(f'Quantity cannot be negative for ingredient')
                        has_error = True
                        break
                    if quantity == 0:
                        continue  # Skip zero quantities
                except ValueError:
                    flash(f'Invalid quantity value. Please enter a valid number.')
                    has_error = True
                    break
                
                unit_id = int(request.form[f'unit_{ingredient_id}'])
                
                items_to_save.append({
                    'ingredient_id': ingredient_id,
                    'unit_id': unit_id,
                    'quantity': quantity
                })
        
        if has_error:
            return redirect(url_for('edit_move_request', request_id=request_id))
        
        # Update request header
        move_request.request_date = request_date
        move_request.note = note
        db.session.commit()
        
        # Delete existing items
        MoveRequestItem.query.filter_by(request_id=request_id).delete()
        
        # Add validated items
        for item in items_to_save:
            request_item = MoveRequestItem(
                request_id=move_request.id,
                ingredient_id=item['ingredient_id'],
                quantity_requested=item['quantity'],
                unit_id=item['unit_id']
            )
            db.session.add(request_item)
        
        db.session.commit()
        flash(f'Move Request #{request_id} updated successfully')
        return redirect(url_for('my_move_requests'))
    
    # GET request - show form
    selected_warehouse_id = move_request.from_warehouse_id
    ingredients_data = get_ingredients_with_units(selected_warehouse_id)
    
    # Get existing quantities from request
    existing_items = {item.ingredient_id: {
        'quantity': item.quantity_requested,
        'unit_id': item.unit_id
    } for item in move_request.items}
    
    for ing in ingredients_data:
        if ing['units']:
            # Set default unit from existing request or highest rank
            if ing['id'] in existing_items:
                ing['default_unit_id'] = existing_items[ing['id']]['unit_id']
                ing['existing_qty'] = existing_items[ing['id']]['quantity']
            else:
                highest_unit = max(ing['units'], key=lambda u: u['rank'])
                ing['default_unit_id'] = highest_unit['id']
                ing['existing_qty'] = 0
        else:
            ing['existing_qty'] = 0
    
    warehouses = Warehouse.query.filter_by(warehouse_type='WH').all()
    store_warehouse = Warehouse.query.get(move_request.to_warehouse_id)
    
    return render_template('edit_move_request.html',
                          ingredients=ingredients_data,
                          warehouses=warehouses,
                          selected_warehouse_id=selected_warehouse_id,
                          warehouse=store_warehouse,
                          move_request=move_request,
                          today=move_request.request_date.isoformat())


@app.route('/move_request/cancel/<int:request_id>', methods=['POST'])
def cancel_move_request(request_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    if session['role'] not in ['ST_REQ', 'ST_MGR']:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
    
    move_request = MoveRequest.query.get_or_404(request_id)
    
    if move_request.requested_by_user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Can only cancel your own requests'}), 403
    
    if move_request.status != 'PENDING':
        return jsonify({'success': False, 'message': 'Only pending requests can be cancelled'}), 400
    
    move_request.status = 'CANCELLED'
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Request cancelled'})


# ========== RECEIPT CONFIRMATION ROUTES ==========

@app.route('/receipts/pending')
def pending_receipts():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Only WH_PIC can confirm receipts
    # if session['role'] != 'WH_PIC':
    #    flash('Only warehouse PIC can confirm receipts')
    #    return redirect(url_for('current_stock'))
    
    warehouse_id = session['warehouse_id']
    
    # Get pending IN movements for THIS warehouse only
    pending_movements = Movement.query.filter(
        Movement.direction == 'IN',
        Movement.status == 'pending',
        Movement.warehouse_id == warehouse_id
    ).order_by(Movement.date.desc(), Movement.created_at.desc()).all()
    
    # Group by move_request_id, skip orphaned
    grouped = {}
    for mov in pending_movements:
        if not mov.move_request_id:
            continue
        req_id = mov.move_request_id
        if req_id not in grouped:
            move_request = MoveRequest.query.get(req_id)
            if not move_request:
                continue
            grouped[req_id] = {
                'move_request': move_request,
                'movements': []
            }
        grouped[req_id]['movements'].append(mov)
    
    return render_template('pending_receipts.html', groups=grouped.values())


@app.route('/receipt/confirm', methods=['POST'])
def confirm_receipt():
    if 'user_id' not in session:
        flash('Not logged in')
        return redirect(url_for('login'))
    
    # Only WH_PIC can confirm receipts
    # if session['role'] != 'WH_PIC':
    #     flash('Only warehouse PIC can confirm receipts')
    #    return redirect(url_for('pending_receipts'))
    
    move_request_id = request.form.get('move_request_id', type=int)
    note = request.form.get('note', '')
    
    # Get all pending IN movements for this move request
    movements = Movement.query.filter(
        Movement.move_request_id == move_request_id,
        Movement.direction == 'IN',
        Movement.status == 'pending'
    ).all()
    
    if not movements:
        flash('No pending movements found for this request')
        return redirect(url_for('pending_receipts'))
    
    # Verify warehouse matches the logged-in WH_PIC's warehouse
    if movements[0].warehouse_id != session['warehouse_id']:
        flash('You can only confirm receipts for your warehouse')
        return redirect(url_for('pending_receipts'))
    
    try:
        for mov in movements:
            # Store original quantity for shortage calculation
            original_quantity = mov.quantity
            original_unit_id = mov.unit_id
            
            # Get submitted quantity and unit
            qty_key = f'qty_{mov.ingredient_id}'
            unit_key = f'unit_{mov.ingredient_id}'
            
            confirmed_quantity = float(request.form.get(qty_key, original_quantity))
            
            if confirmed_quantity < 0:
                flash(f'Quantity cannot be negative for {mov.ingredient.name}')
                return redirect(url_for('pending_receipts'))
            
            if confirmed_quantity > original_quantity:
                flash(f'Cannot confirm more than expected for {mov.ingredient.name}. Expected: {original_quantity} {mov.unit.alt_unit}')
                return redirect(url_for('pending_receipts'))
            
            # Get unit (might have been changed)
            unit_id = int(request.form.get(unit_key, original_unit_id))
            unit = db.session.get(Unit, unit_id)
            
            # Calculate received quantity in base unit
            received_base = confirmed_quantity * unit.conversion_to_base
            
            # ========== MODIFICATION FOR PRODUCTION MOVEMENTS ==========
            # If this is a production movement (case 3b), do NOT add stock to warehouse
            if mov.movement_type != 'production':
                # Add stock to destination warehouse (normal transfer or incoming)
                balance = InventoryBalance.query.filter_by(
                    warehouse_id=mov.warehouse_id,
                    ingredient_id=mov.ingredient_id
                ).first()
                
                if not balance:
                    balance = InventoryBalance(
                        warehouse_id=mov.warehouse_id,
                        ingredient_id=mov.ingredient_id,
                        balance_base=0
                    )
                    db.session.add(balance)
                
                balance.balance_base += received_base
                balance.last_updated = datetime.utcnow()
            else:
                # Production receipt: no stock addition, just log in note
                if note:
                    mov.note = f"{mov.note or ''} [PRODUCTION RECEIPT] {note}".strip()
                else:
                    mov.note = f"{mov.note or ''} [PRODUCTION RECEIPT]".strip()
            # ========== END MODIFICATION ==========
            
            # Update movement with actual received quantity
            mov.quantity = confirmed_quantity
            mov.quantity_base = received_base
            mov.unit_id = unit_id
            
            # Record shortage if partial (only for non-production? but still record)
            if abs(confirmed_quantity - original_quantity) > 0.001:
                discrepancy = original_quantity - confirmed_quantity
                mov.note = f"{mov.note or ''} [SHORTAGE: {discrepancy} {unit.alt_unit}]".strip()
            
            # Update movement status
            mov.status = 'completed'
            mov.confirmed_by_user_id = session['user_id']
            mov.confirmed_at = datetime.utcnow()
            
            # Add global note if provided (already handled above for production)
            if note and mov.movement_type != 'production':
                mov.note = f"{mov.note or ''} {note}".strip()

        move_request = MoveRequest.query.get(move_request_id)
        if move_request:
            move_request.status = 'COMPLETED' 
 
        db.session.commit()
        flash(f'Receipt confirmed for {len(movements)} item(s)')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}')
    
    return redirect(url_for('pending_receipts'))


@app.route('/receipt/reject/<int:movement_id>', methods=['POST'])
def reject_receipt(movement_id):
    if 'user_id' not in session:
        flash('Not logged in')
        return redirect(url_for('login'))
    
    # if session['role'] not in ['ST_MGR', 'ADMIN']:
    #    flash('Permission denied')
    #    return redirect(url_for('current_stock'))
    
    movement = Movement.query.get_or_404(movement_id)
    
    if movement.status != 'pending':
        flash('Movement already processed')
        return redirect(url_for('pending_receipts'))
    
    reason = request.form.get('reject_reason', 'No reason provided')
    unit = Unit.query.get(movement.unit_id)
    
    movement.status = 'rejected'
    movement.confirmed_by_user_id = session['user_id']
    movement.confirmed_at = datetime.now(timezone.utc)
    movement.note = f"{movement.note or ''} [REJECTED: {reason}]".strip()
    
    db.session.commit()
    
    flash(f'Receipt rejected for {movement.ingredient.name} ({movement.quantity} {unit.alt_unit})')
    return redirect(url_for('pending_receipts'))


# ========== ADMIN ROUTES ==========

@app.route('/admin/ingredients')
def admin_ingredients():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session['role'] != 'ADMIN':
        flash('Admin access only')
        return redirect(url_for('current_stock'))
    
    ingredients = Ingredient.query.order_by(Ingredient.name).all()
    return render_template('admin_ingredients.html', ingredients=ingredients)

@app.route('/admin/ingredient/add', methods=['POST'])
def admin_add_ingredient():
    if 'user_id' not in session or session['role'] != 'ADMIN':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    name = request.form.get('name')
    base_unit_alt = request.form.get('base_unit_alt')
    
    if not name or not base_unit_alt:
        flash('All fields required')
        return redirect(url_for('admin_ingredients'))
    
    existing = Ingredient.query.filter_by(name=name).first()
    if existing:
        flash('Ingredient already exists')
        return redirect(url_for('admin_ingredients'))
    
    new_ingredient = Ingredient(
        name=name,
        is_approved=True,
        created_by_user_id=session['user_id']
    )
    db.session.add(new_ingredient)
    db.session.commit()
    
    base_unit = Unit(
        ingredient_id=new_ingredient.id,
        alt_unit=base_unit_alt[:10],
        conversion_to_base=1,
        rank=1
    )
    db.session.add(base_unit)
    db.session.commit()
    
    new_ingredient.base_unit_id = base_unit.id
    db.session.commit()
    
    flash(f'Ingredient "{name}" created with base unit "{base_unit_alt}"')
    return redirect(url_for('admin_ingredients'))

@app.route('/admin/unit/add', methods=['POST'])
def admin_add_unit():
    if 'user_id' not in session or session['role'] != 'ADMIN':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    ingredient_id = int(request.form['ingredient_id'])
    alt_unit = request.form['alt_unit']
    conversion = float(request.form['conversion'])

    if conversion <= 0:
        flash('Conversion rate must be greater than 0')
        return redirect(url_for('admin_ingredients'))

    if conversion > 10000:
        flash('Conversion rate seems too high. Please verify.')
        return redirect(url_for('admin_ingredients'))
    
    ingredient = Ingredient.query.get(ingredient_id)
    if not ingredient:
        flash('Ingredient not found')
        return redirect(url_for('admin_ingredients'))
    
    max_rank = db.session.query(db.func.max(Unit.rank)).filter_by(ingredient_id=ingredient_id).scalar() or 1
    next_rank = max_rank + 1
    
    new_unit = Unit(
        ingredient_id=ingredient_id,
        alt_unit=alt_unit[:10],
        conversion_to_base=conversion,
        rank=next_rank
    )
    db.session.add(new_unit)
    db.session.commit()
    
    flash(f'Unit "{alt_unit}" added to {ingredient.name}')
    return redirect(url_for('admin_ingredients'))

@app.route('/admin/ingredient/set_base_unit', methods=['POST'])
def admin_set_base_unit():
    if 'user_id' not in session or session['role'] != 'ADMIN':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    ingredient_id = int(request.form['ingredient_id'])
    base_unit_id = int(request.form['base_unit_id'])
    
    ingredient = Ingredient.query.get(ingredient_id)
    if ingredient:
        ingredient.base_unit_id = base_unit_id
        db.session.commit()
        flash(f'Base unit set for {ingredient.name}')
    
    return redirect(url_for('admin_ingredients'))

@app.route('/admin/ingredient/delete/<int:ingredient_id>', methods=['POST'])
def admin_delete_ingredient(ingredient_id):
    if 'user_id' not in session or session['role'] != 'ADMIN':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    ingredient = Ingredient.query.get(ingredient_id)
    if not ingredient:
        return jsonify({'success': False, 'message': 'Not found'}), 404
    
    # Check if used in movements
    movement_count = Movement.query.filter_by(ingredient_id=ingredient_id).count()
    if movement_count > 0:
        return jsonify({'success': False, 'message': f'Cannot delete: used in {movement_count} movements'}), 400
    
    # Delete units first
    Unit.query.filter_by(ingredient_id=ingredient_id).delete()
    db.session.delete(ingredient)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Deleted'})



import os

with app.app_context():
    db.create_all()
    print("✅ Database ready")

# ========== RUN APP ==========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    is_production = os.environ.get('RENDER', False)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=not is_production
    )