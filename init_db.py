# init_db.py
from app import app, db
from models import (Role, Permission, User, BikeModel, Station, Part,
                    WorkOrder, Notice)
from werkzeug.security import generate_password_hash
from datetime import date

with app.app_context():
    db.drop_all()
    db.create_all()

    perms = [
        ("admin.all",        "Full admin access"),
        ("line.view",        "View assembly line"),
        ("station.complete", "Mark station complete"),
        ("qc.pass",          "Pass QC"),
        ("qc.fail",          "Fail QC / raise defect"),
        ("rework.update",    "Update rework"),
        ("audit.view",       "View audit log"),
        ("notice.post",      "Post notice"),
    ]
    perm_objs = {}
    for code, desc in perms:
        p = Permission(perm_code=code, description=desc)
        db.session.add(p)
        perm_objs[code] = p
    db.session.commit()

    role_defs = {
        "Admin":             ["admin.all", "line.view", "audit.view", "notice.post"],
        "Line Supervisor":   ["line.view", "station.complete", "qc.pass", "qc.fail",
                              "audit.view", "notice.post"],
        "Operator":          ["line.view", "station.complete"],
        "QC Inspector":      ["line.view", "qc.pass", "qc.fail"],
        "Rework Technician": ["line.view", "rework.update"],
        "Auditor":           ["line.view", "audit.view"],
    }
    roles = {}
    for rname, pcs in role_defs.items():
        r = Role(role_name=rname, description=rname)
        r.permissions = [perm_objs[c] for c in pcs]
        db.session.add(r)
        roles[rname] = r
    db.session.commit()

    pw = generate_password_hash("pass123")
    for uname, fname, rname in [
        ("admin",      "Baranidharan",     "Admin"),
        ("supervisor", "Evansam",   "Line Supervisor"),
        ("operator1",  "Naveen Chandhran",    "Operator"),
        ("qc1",        "Ansci Mohan",   "QC Inspector"),
        ("rework1",    "Pqnika Chreen",    "Rework Technician"),
        ("auditor",    "John Edward", "Auditor"),
    ]:
        db.session.add(User(username=uname, full_name=fname,
                            password_hash=pw, role_id=roles[rname].role_id))
    db.session.commit()

    bullet = BikeModel(model_name="Bullet 350 UCE", variant="Standard",
                       image_path="images/models/bullet_350.png")
    himalayan = BikeModel(model_name="Himalayan 411", variant="Adventure",
                          image_path="images/models/himalayan_411.png")
    db.session.add_all([bullet, himalayan])
    db.session.commit()

    station_defs = [
        ("Frame Assembly",       1, 4.0, True,  False),
        ("Engine Mounting",      2, 6.0, True,  False),
        ("Wiring & Electrical",  3, 5.0, True,  False),
        ("Body & Panel Fitting", 4, 7.0, True,  False),
        ("Final QC & Testing",   5, 3.0, True,  True),
    ]
    stations = {}
    for name, seq, t, is_qc, is_final in station_defs:
        s = Station(station_name=name, sequence=seq, standard_time_min=t,
                    is_qc_gate=is_qc, is_final=is_final)
        db.session.add(s)
        stations[name] = s
    db.session.commit()

    bullet_parts = [
        ("Frame Assembly",       "BL-FR-001", "Frame Chassis",         "frame.png",      1),
        ("Frame Assembly",       "BL-FR-002", "Handlebar",             "handlebar.png",  1),
        ("Engine Mounting",      "BL-EN-001", "UCE Engine Assembly",   "engine.png",     1),
        ("Engine Mounting",      "BL-EN-002", "Fish-tail Silencer",    "exhaust.png",    1),
        ("Wiring & Electrical",  "BL-EL-001", "Casquette Headlamp",    "headlamp.png",   1),
        ("Wiring & Electrical",  "BL-EL-002", "Battery 12V",           "battery.png",    1),
        ("Body & Panel Fitting", "BL-BD-001", "Fuel Tank",             "fuel_tank.png",  1),
        ("Body & Panel Fitting", "BL-BD-002", "Long Dual Seat",        "seat.png",       1),
        ("Body & Panel Fitting", "BL-BD-003", "Side Panel / Tool Box", "side_panel.png", 1),
        ("Final QC & Testing",   "BL-FQ-001", "Spoke Wheel",           "wheel.png",      2),
    ]
    for st_name, pno, pname, img, qty in bullet_parts:
        db.session.add(Part(model_id=bullet.model_id,
                            station_id=stations[st_name].station_id,
                            part_no=pno, part_name=pname,
                            image_path=f"images/parts/bullet_350/{img}", qty=qty))
    db.session.commit()

    himalayan_parts = [
        ("Frame Assembly",       "HM-FR-001", "Split Cradle Frame",    "frame.png",      1),
        ("Frame Assembly",       "HM-FR-002", "Handlebar with Brace",  "handlebar.png",  1),
        ("Engine Mounting",      "HM-EN-001", "LS410 Engine Assembly", "engine.png",     1),
        ("Engine Mounting",      "HM-EN-002", "Exhaust Silencer",      "exhaust.png",    1),
        ("Wiring & Electrical",  "HM-EL-001", "Digital Console",       "console.png",    1),
        ("Wiring & Electrical",  "HM-EL-002", "Front Fairing + Visor", "fairing.png",    1),
        ("Body & Panel Fitting", "HM-BD-001", "Fuel Tank",             "fuel_tank.png",  1),
        ("Body & Panel Fitting", "HM-BD-002", "Split Seat",            "seat.png",       1),
        ("Body & Panel Fitting", "HM-BD-003", "Bash Plate",            "bash_plate.png", 1),
        ("Final QC & Testing",   "HM-FQ-001", "Spoke Wheel 21in",      "wheel.png",      2),
    ]
    for st_name, pno, pname, img, qty in himalayan_parts:
        db.session.add(Part(model_id=himalayan.model_id,
                            station_id=stations[st_name].station_id,
                            part_no=pno, part_name=pname,
                            image_path=f"images/parts/himalayan_411/{img}", qty=qty))
    db.session.commit()

    db.session.add_all([
        WorkOrder(wo_number="WO-2026-001", model_id=bullet.model_id,
                  target_qty=20, shift="A", wo_date=date.today(), status="OPEN"),
        WorkOrder(wo_number="WO-2026-002", model_id=himalayan.model_id,
                  target_qty=15, shift="A", wo_date=date.today(), status="OPEN"),
    ])
    db.session.commit()

    db.session.add_all([
        Notice(title="System Online",
               body="SmartMES is live. Bullet 350 UCE and Himalayan 411 models loaded.",
               category="SUCCESS", posted_by=None),
        Notice(title="Shift A Target",
               body="20 Bullet 350 · 15 Himalayan 411. Good luck, team.",
               category="INFO", posted_by=2),
    ])
    db.session.commit()

    print("=" * 55)
    print("  SmartMES database initialised")
    print("=" * 55)
    print("  Users (password: pass123):")
    print("    admin | supervisor | operator1 | qc1 | rework1 | auditor")
    print("=" * 55)