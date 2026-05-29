from app import app, db
from app import User, Warehouse, Ingredient, Unit, InventoryBalance, StockSetting
from werkzeug.security import generate_password_hash

with app.app_context():
    # Clear existing data
    db.session.query(db.Model.metadata.tables['move_request_items']).delete()
    db.session.query(db.Model.metadata.tables['move_requests']).delete()
    db.session.query(db.Model.metadata.tables['movements']).delete()
    db.session.query(db.Model.metadata.tables['inventory_balance']).delete()
    db.session.query(db.Model.metadata.tables['stock_settings']).delete()
    db.session.query(db.Model.metadata.tables['units']).delete()
    db.session.query(db.Model.metadata.tables['ingredients']).delete()
    db.session.query(db.Model.metadata.tables['users']).delete()
    db.session.query(db.Model.metadata.tables['warehouses']).delete()
    db.session.commit()

    # ========== WAREHOUSES ==========
    warehouses = [
        ('BLOSSOM', 'BLO', 'WH'),
        ('Serpong', 'SER', 'STORE'),
        ('Suryo', 'SUR', 'STORE'),
        ('Bintaro', 'BIN', 'STORE'),
        ('Sunter', 'SUN', 'STORE'),
        ('Pabrik', 'PAB', 'WH'),
    ]
    
    for name, code, wtype in warehouses:
        wh = Warehouse(name=name, store_code=code, warehouse_type=wtype)
        db.session.add(wh)
    db.session.commit()
    
    # Get warehouse IDs
    wh_map = {wh.name: wh.id for wh in Warehouse.query.all()}
    
    # ========== USERS ==========
    users = [
        ('admin', 'admin', 'ADMIN', None),
        ('blogd', 'blogd', 'WH_PIC', wh_map['BLOSSOM']),
        ('pabgd', 'pabgd', 'WH_PIC', wh_map['Pabrik']),
        ('surgd', 'surgd', 'WH_PIC', wh_map['Suryo']),
        ('bingd', 'bingd', 'WH_PIC', wh_map['Bintaro']),
        ('sermg', 'sermg', 'ST_MGR', wh_map['Serpong']),
        ('sunmg', 'sunmg', 'ST_MGR', wh_map['Sunter']),
        ('surmg', 'surmg', 'ST_MGR', wh_map['Suryo']),
        ('binmg', 'binmg', 'ST_MGR', wh_map['Bintaro']),
        ('surrq', 'surrq', 'ST_REQ', wh_map['Suryo']),
        ('binrq', 'binrq', 'ST_REQ', wh_map['Bintaro']),
    ]
    
    for username, fullname, role, wh_id in users:
        user = User(
            username=username,
            password=generate_password_hash('123'),
            full_name=fullname,
            role=role,
            warehouse_id=wh_id,
            is_active=True
        )
        db.session.add(user)
    db.session.commit()
    
    # ========== INGREDIENTS ==========
    cheese = Ingredient(name='Cheese', is_approved=True)
    flour = Ingredient(name='Flour', is_approved=True)
    db.session.add_all([cheese, flour])
    db.session.commit()
    
    # ========== UNITS ==========
    cheese_box = Unit(ingredient_id=cheese.id, alt_unit='box', conversion_to_base=1, rank=1)
    cheese_ctn = Unit(ingredient_id=cheese.id, alt_unit='ctn', conversion_to_base=12, rank=2)
    flour_unit = Unit(ingredient_id=flour.id, alt_unit='bal', conversion_to_base=1, rank=1)
    db.session.add_all([cheese_box, cheese_ctn, flour_unit])
    db.session.commit()
    
    cheese.base_unit_id = cheese_box.id
    flour.base_unit_id = flour_unit.id
    db.session.commit()
    
    # ========== INVENTORY BALANCES ==========
    inv_balances = [
        (wh_map['Serpong'], cheese.id, 24),
        (wh_map['Serpong'], flour.id, 125),
        (wh_map['BLOSSOM'], cheese.id, 240),
        (wh_map['BLOSSOM'], flour.id, 500),
        (wh_map['Pabrik'], cheese.id, 120),
        (wh_map['Pabrik'], flour.id, 1000),
    ]
    
    for wh_id, ing_id, qty in inv_balances:
        balance = InventoryBalance(
            warehouse_id=wh_id,
            ingredient_id=ing_id,
            balance_base=qty
        )
        db.session.add(balance)
    db.session.commit()
    
    # ========== STOCK SETTINGS ==========
    stock_settings = [
        (wh_map['Serpong'], cheese.id, 12),
        (wh_map['Serpong'], flour.id, 50),
        (wh_map['BLOSSOM'], cheese.id, 24),
        (wh_map['BLOSSOM'], flour.id, 100),
    ]
    
    for wh_id, ing_id, min_qty in stock_settings:
        setting = StockSetting(
            warehouse_id=wh_id,
            ingredient_id=ing_id,
            min_quantity_base=min_qty
        )
        db.session.add(setting)
    db.session.commit()
    
    print("Database seeded successfully!")
    print(f"Warehouses: {Warehouse.query.count()}")
    print(f"Users: {User.query.count()}")
    print(f"Ingredients: {Ingredient.query.count()}")
    print(f"Units: {Unit.query.count()}")
    print(f"Inventory Balances: {InventoryBalance.query.count()}")