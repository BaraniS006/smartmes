# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

role_permissions = db.Table(
    'role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.role_id'), primary_key=True),
    db.Column('perm_id', db.Integer, db.ForeignKey('permissions.perm_id'), primary_key=True)
)

class Role(db.Model):
    __tablename__ = 'roles'
    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    permissions = db.relationship('Permission', secondary=role_permissions, backref='roles')

class Permission(db.Model):
    __tablename__ = 'permissions'
    perm_id = db.Column(db.Integer, primary_key=True)
    perm_code = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(200))

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'))
    is_active_flag = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    role = db.relationship('Role')

    def get_id(self):
        return str(self.user_id)

    @property
    def is_active(self):
        return self.is_active_flag

    def has_permission(self, code):
        if any(p.perm_code == "admin.all" for p in self.role.permissions):
            return True
        return any(p.perm_code == code for p in self.role.permissions)

class BikeModel(db.Model):
    __tablename__ = 'bike_models'
    model_id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), unique=True, nullable=False)
    variant = db.Column(db.String(50))
    image_path = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Station(db.Model):
    __tablename__ = 'stations'
    station_id = db.Column(db.Integer, primary_key=True)
    station_name = db.Column(db.String(80), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    standard_time_min = db.Column(db.Float, default=5.0)
    is_qc_gate = db.Column(db.Boolean, default=False)
    is_final = db.Column(db.Boolean, default=False)

class Part(db.Model):
    __tablename__ = 'parts'
    part_id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey('bike_models.model_id'), nullable=False)
    station_id = db.Column(db.Integer, db.ForeignKey('stations.station_id'), nullable=False)
    part_no = db.Column(db.String(50), nullable=False)
    part_name = db.Column(db.String(100), nullable=False)
    image_path = db.Column(db.String(200))
    qty = db.Column(db.Integer, default=1)
    model = db.relationship('BikeModel')
    station = db.relationship('Station')

class WorkOrder(db.Model):
    __tablename__ = 'work_orders'
    wo_id = db.Column(db.Integer, primary_key=True)
    wo_number = db.Column(db.String(30), unique=True, nullable=False)
    model_id = db.Column(db.Integer, db.ForeignKey('bike_models.model_id'))
    target_qty = db.Column(db.Integer, default=0)
    completed_qty = db.Column(db.Integer, default=0)
    shift = db.Column(db.String(10))
    wo_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='OPEN')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    model = db.relationship('BikeModel')

    @property
    def fill_percent(self):
        if not self.target_qty: return 0
        return round((self.completed_qty / self.target_qty) * 100, 1)

class Chassis(db.Model):
    __tablename__ = 'chassis'
    chassis_id = db.Column(db.Integer, primary_key=True)
    chassis_no = db.Column(db.String(40), unique=True, nullable=False)
    model_id = db.Column(db.Integer, db.ForeignKey('bike_models.model_id'))
    wo_id = db.Column(db.Integer, db.ForeignKey('work_orders.wo_id'))
    current_station_id = db.Column(db.Integer, db.ForeignKey('stations.station_id'))
    status = db.Column(db.String(20), default='IN_PROGRESS')
    progress = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    model = db.relationship('BikeModel')
    work_order = db.relationship('WorkOrder')
    current_station = db.relationship('Station')

class StationLog(db.Model):
    __tablename__ = 'station_log'
    log_id = db.Column(db.Integer, primary_key=True)
    chassis_id = db.Column(db.Integer, db.ForeignKey('chassis.chassis_id'))
    station_id = db.Column(db.Integer, db.ForeignKey('stations.station_id'))
    operator_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    status = db.Column(db.String(20))
    in_time = db.Column(db.DateTime, default=datetime.utcnow)
    out_time = db.Column(db.DateTime)
    remarks = db.Column(db.String(200))
    chassis = db.relationship('Chassis')
    station = db.relationship('Station')
    operator = db.relationship('User')

class Defect(db.Model):
    __tablename__ = 'defects'
    defect_id = db.Column(db.Integer, primary_key=True)
    chassis_id = db.Column(db.Integer, db.ForeignKey('chassis.chassis_id'))
    station_id = db.Column(db.Integer, db.ForeignKey('stations.station_id'))
    part_id = db.Column(db.Integer, db.ForeignKey('parts.part_id'))
    part_name_snapshot = db.Column(db.String(100))
    part_image_snapshot = db.Column(db.String(200))
    defect_type = db.Column(db.String(80))
    severity = db.Column(db.String(20))
    description = db.Column(db.String(200))
    reported_by = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    status = db.Column(db.String(20), default='OPEN')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    chassis = db.relationship('Chassis')
    station = db.relationship('Station')
    part = db.relationship('Part')
    reporter = db.relationship('User')

class Rework(db.Model):
    __tablename__ = 'rework'
    rework_id = db.Column(db.Integer, primary_key=True)
    defect_id = db.Column(db.Integer, db.ForeignKey('defects.defect_id'))
    technician_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    action_taken = db.Column(db.String(300))
    status = db.Column(db.String(20), default='PENDING')
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    defect = db.relationship('Defect')
    technician = db.relationship('User')

class Notice(db.Model):
    __tablename__ = 'notices'
    notice_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.String(500))
    category = db.Column(db.String(20), default='INFO')
    posted_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    audit_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    action = db.Column(db.String(80))
    entity = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')