# app.py
import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from datetime import datetime, date
from sqlalchemy import func
from config import Config
from models import (db, Role, Permission, User, BikeModel, Station, Part,
                    WorkOrder, Chassis, StationLog, Defect, Rework,
                    Notice, AuditLog)

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))


# ---------- Helpers ----------

def log_action(action, entity=None, entity_id=None):
    db.session.add(AuditLog(
        user_id=current_user.user_id if current_user.is_authenticated else None,
        action=action, entity=entity, entity_id=entity_id))
    db.session.commit()


def auto_notice(title, body, category="AUTO"):
    db.session.add(Notice(title=title, body=body, category=category, posted_by=None))
    db.session.commit()


def require_permission(code):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **k):
            if not current_user.is_authenticated or not current_user.has_permission(code):
                abort(403)
            return f(*a, **k)
        return wrapper
    return deco


def recalc_progress(c):
    total = Station.query.count()
    done = db.session.query(func.count(func.distinct(StationLog.station_id)))\
                     .filter(StationLog.chassis_id == c.chassis_id,
                             StationLog.status.in_(["COMPLETE", "QC_PASS"])).scalar() or 0
    c.progress = int((done / total) * 100) if total else 0


# ---------- Auth ----------

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uname = request.form["username"].strip()
        pwd = request.form["password"]
        user = User.query.filter_by(username=uname).first()
        if user and check_password_hash(user.password_hash, pwd):
            login_user(user)
            log_action("LOGIN", "User", user.user_id)
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    log_action("LOGOUT", "User", current_user.user_id)
    logout_user()
    return redirect(url_for("login"))


# ---------- Dashboard ----------

@app.route("/dashboard")
@login_required
def dashboard():
    today = date.today()

    today_done = Chassis.query.filter(
        Chassis.status == "COMPLETED",
        func.date(Chassis.completed_at) == today).all()

    today_scrapped = Chassis.query.filter(
        Chassis.status == "SCRAPPED",
        func.date(Chassis.created_at) == today).all()

    today_by_model = {}
    for c in today_done:
        name = c.model.model_name
        today_by_model[name] = today_by_model.get(name, 0) + 1

    today_completed = len(today_done)
    today_scrapped_count = len(today_scrapped)

    today_target = db.session.query(func.sum(WorkOrder.target_qty))\
                             .filter(WorkOrder.status == "OPEN").scalar() or 0

    if today_target == 0:
        today_target = today_completed or 1

    today_pct = int((today_completed / today_target) * 100) if today_target else 0
    if today_pct > 100:
        today_pct = 100

    total_attempted = today_completed + today_scrapped_count
    scrap_rate = round((today_scrapped_count / total_attempted) * 100, 1) if total_attempted else 0

    counts = {
        "total":     Chassis.query.count(),
        "in_prog":   Chassis.query.filter_by(status="IN_PROGRESS").count(),
        "awaiting":  Chassis.query.filter_by(status="AWAITING_QC").count(),
        "qc_hold":   Chassis.query.filter_by(status="QC_HOLD").count(),
        "rework":    Chassis.query.filter_by(status="REWORK").count(),
        "completed": Chassis.query.filter_by(status="COMPLETED").count(),
        "scrapped":  Chassis.query.filter_by(status="SCRAPPED").count(),
        "defects":   Defect.query.filter(Defect.status.in_(["OPEN", "IN_REWORK"])).count(),
    }

    status_rows = db.session.query(Chassis.status, func.count(Chassis.chassis_id))\
                            .group_by(Chassis.status).all()
    status_labels = [r[0] for r in status_rows]
    status_values = [r[1] for r in status_rows]

    sev_rows = db.session.query(Defect.severity, func.count(Defect.defect_id))\
                         .group_by(Defect.severity).all()
    sev_labels = [r[0] or "Unknown" for r in sev_rows]
    sev_values = [r[1] for r in sev_rows]

    recent_defects = Defect.query.order_by(Defect.created_at.desc()).limit(5).all()
    recent_notices = Notice.query.order_by(Notice.created_at.desc()).limit(4).all()
    active_wos = WorkOrder.query.filter_by(status="OPEN").all()

    stations = Station.query.order_by(Station.sequence).all()
    by_station = {s.station_id: [] for s in stations}
    line_active = Chassis.query.filter(Chassis.status.in_(["IN_PROGRESS", "AWAITING_QC"])).all()
    for c in line_active:
        if c.current_station_id in by_station:
            by_station[c.current_station_id].append(c)

    rework_items = Chassis.query.filter(
        Chassis.status.in_(["QC_HOLD", "REWORK", "RE_INSPECTION"]))\
        .order_by(Chassis.created_at.desc()).limit(5).all()
    rework_chassis = []
    for c in rework_items:
        cnt = Defect.query.filter(
            Defect.chassis_id == c.chassis_id,
            Defect.status.in_(["OPEN", "IN_REWORK"])).count()
        rework_chassis.append({"chassis": c, "defect_count": cnt})

    today_str = today.strftime("%A, %d %B %Y")

    return render_template("dashboard.html",
        counts=counts,
        today_completed=today_completed,
        today_target=today_target,
        today_pct=today_pct,
        today_scrapped_count=today_scrapped_count,
        scrap_rate=scrap_rate,
        today_by_model=today_by_model,
        status_labels=status_labels,
        status_values=status_values,
        sev_labels=sev_labels,
        sev_values=sev_values,
        recent_defects=recent_defects,
        recent_notices=recent_notices,
        active_wos=active_wos,
        stations=stations,
        by_station=by_station,
        rework_chassis=rework_chassis,
        today_str=today_str)


# ---------- Assembly Line ----------

@app.route("/line")
@login_required
@require_permission("line.view")
def line_view():
    stations = Station.query.order_by(Station.sequence).all()
    by_station = {s.station_id: [] for s in stations}
    active = Chassis.query.filter(Chassis.status.in_(["IN_PROGRESS", "AWAITING_QC"])).all()
    for c in active:
        if c.current_station_id in by_station:
            by_station[c.current_station_id].append(c)
    return render_template("line_view.html", stations=stations, by_station=by_station)


@app.route("/rework-line")
@login_required
@require_permission("line.view")
def rework_line():
    items = Chassis.query.filter(
        Chassis.status.in_(["QC_HOLD", "REWORK", "RE_INSPECTION"]))\
        .order_by(Chassis.created_at.desc()).all()
    data = []
    for c in items:
        defs = Defect.query.filter(
            Defect.chassis_id == c.chassis_id,
            Defect.status.in_(["OPEN", "IN_REWORK"])).all()
        data.append({"chassis": c, "defects": defs})
    return render_template("rework_line.html", data=data)


# ---------- Work Orders ----------

@app.route("/workorders")
@login_required
@require_permission("line.view")
def workorders():
    wos = WorkOrder.query.order_by(WorkOrder.wo_id.desc()).all()
    return render_template("workorders.html", wos=wos)


@app.route("/workorders/new", methods=["GET", "POST"])
@login_required
@require_permission("line.view")
def workorder_new():
    models = BikeModel.query.all()
    if request.method == "POST":
        wo = WorkOrder(
            wo_number=request.form["wo_number"].strip(),
            model_id=int(request.form["model_id"]),
            target_qty=int(request.form["target_qty"]),
            shift=request.form["shift"],
            wo_date=datetime.strptime(request.form["wo_date"], "%Y-%m-%d").date(),
            status="OPEN")
        db.session.add(wo)
        db.session.commit()
        log_action("CREATE_WO", "WorkOrder", wo.wo_id)
        auto_notice("New Batch Created",
                    f"{wo.wo_number} — {wo.model.model_name} x{wo.target_qty}", "INFO")
        flash("Work order created.", "success")
        return redirect(url_for("workorders"))
    return render_template("workorder_new.html", models=models)


@app.route("/batches")
@login_required
@require_permission("line.view")
def batches():
    wos = WorkOrder.query.order_by(WorkOrder.wo_id.desc()).all()
    return render_template("batches.html", wos=wos)


# ---------- Chassis ----------

@app.route("/chassis")
@login_required
@require_permission("line.view")
def chassis_list():
    chassis = Chassis.query.order_by(Chassis.chassis_id.desc()).all()
    return render_template("chassis_list.html", chassis=chassis)


@app.route("/chassis/new", methods=["GET", "POST"])
@login_required
@require_permission("station.complete")
def chassis_new():
    wos = WorkOrder.query.filter_by(status="OPEN").all()
    stations = Station.query.order_by(Station.sequence).all()
    first = stations[0] if stations else None
    
    if request.method == "POST":
        chassis_no = request.form["chassis_no"].strip()
        
        # CHECK IF CHASSIS ALREADY EXISTS
        existing = Chassis.query.filter_by(chassis_no=chassis_no).first()
        if existing:
            flash(f"Chassis number '{chassis_no}' already exists. Please enter a unique number.", "danger")
            return redirect(url_for("chassis_new"))
            
        wo = WorkOrder.query.get(int(request.form["wo_id"]))
        c = Chassis(chassis_no=chassis_no,
                    model_id=wo.model_id, wo_id=wo.wo_id,
                    current_station_id=first.station_id,
                    status="IN_PROGRESS", progress=0)
        db.session.add(c)
        db.session.commit()
        log_action("CREATE_CHASSIS", "Chassis", c.chassis_id)
        flash(f"Chassis {c.chassis_no} entered line at {first.station_name}.", "success")
        return redirect(url_for("chassis_detail", chassis_id=c.chassis_id))
        
    return render_template("chassis_new.html", wos=wos)


@app.route("/chassis/<int:chassis_id>")
@login_required
@require_permission("line.view")
def chassis_detail(chassis_id):
    c = Chassis.query.get_or_404(chassis_id)
    logs = StationLog.query.filter_by(chassis_id=c.chassis_id).order_by(StationLog.log_id).all()
    defects = Defect.query.filter_by(chassis_id=c.chassis_id).order_by(Defect.defect_id).all()
    stations = Station.query.order_by(Station.sequence).all()
    return render_template("chassis_detail.html", c=c, logs=logs,
                           defects=defects, stations=stations)


@app.route("/chassis/<int:chassis_id>/revive", methods=["POST"])
@login_required
@require_permission("admin.all")
def chassis_revive(chassis_id):
    c = Chassis.query.get_or_404(chassis_id)
    if c.status != "SCRAPPED":
        flash("Only scrapped chassis can be revived.", "warning")
        return redirect(url_for("chassis_detail", chassis_id=chassis_id))

    c.status = "QC_HOLD"
    c.completed_at = None

    for d in Defect.query.filter_by(chassis_id=c.chassis_id, status="SCRAPPED").all():
        d.status = "OPEN"

    db.session.commit()
    log_action("REVIVE_CHASSIS", "Chassis", c.chassis_id)
    auto_notice("Chassis Revived",
                f"{c.chassis_no} revived from SCRAPPED to QC_HOLD.", "INFO")
    flash(f"{c.chassis_no} revived to QC_HOLD.", "success")
    return redirect(url_for("chassis_detail", chassis_id=chassis_id))


# ---------- Station Entry ----------

@app.route("/station/<int:chassis_id>", methods=["GET", "POST"])
@login_required
@require_permission("station.complete")
def station_entry(chassis_id):
    c = Chassis.query.get_or_404(chassis_id)
    if c.status != "IN_PROGRESS":
        flash(f"Cannot do station entry. Status: {c.status}.", "warning")
        return redirect(url_for("chassis_detail", chassis_id=c.chassis_id))
    station = c.current_station
    parts = Part.query.filter_by(model_id=c.model_id, station_id=station.station_id).all()
    if request.method == "POST":
        log = StationLog(chassis_id=c.chassis_id, station_id=station.station_id,
                         operator_id=current_user.user_id, status="COMPLETE",
                         out_time=datetime.now(),
                         remarks=request.form.get("remarks", ""))
        db.session.add(log)
        c.status = "AWAITING_QC"
        recalc_progress(c)
        db.session.commit()
        log_action("STATION_COMPLETE", "Chassis", c.chassis_id)
        flash(f"Station '{station.station_name}' done. Awaiting QC.", "success")
        return redirect(url_for("chassis_detail", chassis_id=c.chassis_id))
    return render_template("station_entry.html", c=c, station=station, parts=parts)


# ---------- QC Gate ----------

@app.route("/qc/<int:chassis_id>", methods=["GET", "POST"])
@login_required
def qc_gate(chassis_id):
    if not (current_user.has_permission("qc.pass") or current_user.has_permission("qc.fail")):
        abort(403)
    c = Chassis.query.get_or_404(chassis_id)
    if c.status not in ("AWAITING_QC", "RE_INSPECTION"):
        flash(f"QC not available. Status: {c.status}.", "warning")
        return redirect(url_for("chassis_detail", chassis_id=c.chassis_id))

    station = c.current_station
    parts = Part.query.filter_by(model_id=c.model_id, station_id=station.station_id).all()
    DEFECT_TYPES = ["Missing Part", "Wrong Fitting", "Scratch / Dent",
                    "Torque Failure", "Electrical Fault", "Paint Defect"]
    SEVERITIES = ["MINOR", "MAJOR", "CRITICAL"]

    if request.method == "POST":
        result = request.form.get("result")
        if result == "PASS":
            log = StationLog(chassis_id=c.chassis_id, station_id=station.station_id,
                             operator_id=current_user.user_id, status="QC_PASS",
                             out_time=datetime.now())
            db.session.add(log)
            if c.status == "RE_INSPECTION":
                for d in Defect.query.filter_by(chassis_id=c.chassis_id,
                                                status="IN_REWORK").all():
                    d.status = "FIXED"
            nxt = Station.query.filter(Station.sequence > station.sequence)\
                               .order_by(Station.sequence).first()
            if nxt:
                c.current_station_id = nxt.station_id
                c.status = "IN_PROGRESS"
                msg = f"QC PASS. Moved to {nxt.station_name}."
            else:
                c.status = "COMPLETED"
                c.completed_at = datetime.now()
                c.progress = 100
                wo = c.work_order
                if wo:
                    wo.completed_qty = (wo.completed_qty or 0) + 1
                    if wo.completed_qty >= wo.target_qty:
                        wo.status = "CLOSED"
                        auto_notice("Batch Complete",
                                    f"{wo.wo_number} — {wo.model.model_name} finished "
                                    f"({wo.completed_qty}/{wo.target_qty})", "SUCCESS")
                msg = "QC PASS. Chassis COMPLETED."
                auto_notice("Chassis Completed",
                            f"{c.chassis_no} ({c.model.model_name}) passed final QC.",
                            "SUCCESS")
            recalc_progress(c)
            db.session.commit()
            log_action("QC_PASS", "Chassis", c.chassis_id)
            flash(msg, "success")
            return redirect(url_for("chassis_detail", chassis_id=c.chassis_id))
        else:
            part_id = request.form.get("part_id") or None
            part = Part.query.get(int(part_id)) if part_id else None
            defect = Defect(
                chassis_id=c.chassis_id, station_id=station.station_id,
                part_id=part.part_id if part else None,
                part_name_snapshot=part.part_name if part else "Unspecified",
                part_image_snapshot=part.image_path if part else None,
                defect_type=request.form.get("defect_type", "Unspecified"),
                severity=request.form.get("severity", "MINOR"),
                description=request.form.get("description", ""),
                reported_by=current_user.user_id, status="OPEN")
            db.session.add(defect)
            log = StationLog(chassis_id=c.chassis_id, station_id=station.station_id,
                             operator_id=current_user.user_id, status="QC_FAIL",
                             out_time=datetime.now(),
                             remarks=request.form.get("description", ""))
            db.session.add(log)
            c.status = "QC_HOLD"
            db.session.commit()
            log_action("QC_FAIL", "Chassis", c.chassis_id)
            auto_notice("QC Fail — Chassis Isolated",
                        f"{c.chassis_no} isolated at {station.station_name} "
                        f"(Defect: {defect.defect_type})", "URGENT")
            flash(f"QC FAILED. {c.chassis_no} isolated. Defect #{defect.defect_id} logged.",
                  "danger")
            return redirect(url_for("chassis_detail", chassis_id=c.chassis_id))

    return render_template("qc_gate.html", c=c, station=station, parts=parts,
                           defect_types=DEFECT_TYPES, severities=SEVERITIES)


# ---------- Defects ----------

@app.route("/defects")
@login_required
@require_permission("line.view")
def defects():
    all_defects = Defect.query.order_by(Defect.defect_id.desc()).all()
    return render_template("defects.html", defects=all_defects)


# ---------- Rework ----------

@app.route("/rework")
@login_required
@require_permission("rework.update")
def rework_list():
    open_defects = Defect.query.filter(
        Defect.status.in_(["OPEN", "IN_REWORK"]),
        Defect.chassis.has(Chassis.status != "SCRAPPED")
    ).all()
    return render_template("rework_list.html", defects=open_defects)


@app.route("/rework/<int:defect_id>", methods=["GET", "POST"])
@login_required
@require_permission("rework.update")
def rework_action(defect_id):
    d = Defect.query.get_or_404(defect_id)
    c = d.chassis

    if c.status == "SCRAPPED" or d.status == "SCRAPPED":
        flash("Cannot rework — this chassis/defect is scrapped.", "warning")
        return redirect(url_for("rework_list"))

    if request.method == "POST":
        action = request.form.get("action")
        if action == "START":
            r = Rework(defect_id=d.defect_id, technician_id=current_user.user_id,
                       started_at=datetime.now(), status="PENDING")
            db.session.add(r)
            d.status = "IN_REWORK"
            c.status = "REWORK"
            db.session.commit()
            log_action("REWORK_START", "Defect", d.defect_id)
            flash("Rework started.", "info")
        elif action == "COMPLETE":
            r = Rework.query.filter_by(defect_id=d.defect_id)\
                            .order_by(Rework.rework_id.desc()).first()
            if r:
                r.action_taken = request.form.get("action_taken", "")
                r.completed_at = datetime.now()
                r.status = "DONE"
            d.status = "FIXED"
            open_count = Defect.query.filter(
                Defect.chassis_id == c.chassis_id,
                Defect.status.in_(["OPEN", "IN_REWORK"]),
                Defect.defect_id != d.defect_id).count()
            if open_count == 0:
                c.status = "RE_INSPECTION"
                auto_notice("Rework Complete",
                            f"{c.chassis_no} — all defects fixed. Sent for re-inspection.",
                            "INFO")
            db.session.commit()
            log_action("REWORK_DONE", "Defect", d.defect_id)
            flash("Rework marked complete.", "success")
        elif action == "SCRAP":
            all_open = Defect.query.filter(
                Defect.chassis_id == c.chassis_id,
                Defect.status.in_(["OPEN", "IN_REWORK"])
            ).all()
            for dd in all_open:
                dd.status = "SCRAPPED"

            c.status = "SCRAPPED"
            c.completed_at = None
            db.session.commit()

            log_action("SCRAP", "Chassis", c.chassis_id)
            auto_notice("Chassis Scrapped",
                        f"{c.chassis_no} — scrapped with {len(all_open)} defect(s).",
                        "URGENT")
            flash(f"{c.chassis_no} SCRAPPED. {len(all_open)} defect(s) closed.", "danger")
        return redirect(url_for("rework_list"))
    return render_template("rework_action.html", d=d, c=c)


# ---------- Notice Board ----------

@app.route("/noticeboard")
@login_required
def noticeboard():
    notices = Notice.query.order_by(Notice.created_at.desc()).limit(100).all()
    return render_template("noticeboard.html", notices=notices)


@app.route("/noticeboard/post", methods=["POST"])
@login_required
@require_permission("notice.post")
def notice_post():
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    cat = request.form.get("category", "INFO")
    if not title:
        flash("Title required.", "warning")
        return redirect(url_for("noticeboard"))
    n = Notice(title=title, body=body, category=cat, posted_by=current_user.user_id)
    db.session.add(n)
    db.session.commit()
    log_action("POST_NOTICE", "Notice", n.notice_id)
    flash("Notice posted.", "success")
    return redirect(url_for("noticeboard"))


@app.route("/noticeboard/delete/<int:notice_id>", methods=["POST"])
@login_required
@require_permission("notice.post")
def notice_delete(notice_id):
    n = Notice.query.get_or_404(notice_id)
    if n.posted_by is None and not current_user.has_permission("admin.all"):
        flash("Cannot delete system notices.", "warning")
        return redirect(url_for("noticeboard"))
    db.session.delete(n)
    db.session.commit()
    log_action("DELETE_NOTICE", "Notice", notice_id)
    flash("Notice deleted.", "success")
    return redirect(url_for("noticeboard"))


# ---------- Admin: Models ----------

@app.route("/admin/models")
@login_required
@require_permission("admin.all")
def models_admin():
    models = BikeModel.query.all()
    return render_template("models_admin.html", models=models)


@app.route("/admin/models/new", methods=["GET", "POST"])
@login_required
@require_permission("admin.all")
def model_new():
    if request.method == "POST":
        m = BikeModel(
            model_name=request.form["model_name"].strip(),
            variant=request.form.get("variant", "").strip(),
            image_path=request.form.get("image_path", "").strip())
        db.session.add(m)
        db.session.commit()
        log_action("CREATE_MODEL", "BikeModel", m.model_id)
        flash("Model created.", "success")
        return redirect(url_for("models_admin"))
    return render_template("model_new.html")


@app.route("/admin/models/delete/<int:model_id>", methods=["POST"])
@login_required
@require_permission("admin.all")
def model_delete(model_id):
    m = BikeModel.query.get_or_404(model_id)
    if Part.query.filter_by(model_id=model_id).count() or \
       Chassis.query.filter_by(model_id=model_id).count():
        flash("Cannot delete — model has parts or chassis.", "warning")
        return redirect(url_for("models_admin"))
    db.session.delete(m)
    db.session.commit()
    log_action("DELETE_MODEL", "BikeModel", model_id)
    flash("Model deleted.", "success")
    return redirect(url_for("models_admin"))


# ---------- Admin: Stations ----------

@app.route("/admin/stations")
@login_required
@require_permission("admin.all")
def stations_admin():
    stations = Station.query.order_by(Station.sequence).all()
    return render_template("stations_admin.html", stations=stations)


@app.route("/admin/stations/new", methods=["GET", "POST"])
@login_required
@require_permission("admin.all")
def station_new():
    if request.method == "POST":
        s = Station(
            station_name=request.form["station_name"].strip(),
            sequence=int(request.form["sequence"]),
            standard_time_min=float(request.form.get("standard_time", 5)),
            is_qc_gate=bool(request.form.get("is_qc_gate")),
            is_final=bool(request.form.get("is_final")))
        db.session.add(s)
        db.session.commit()
        log_action("CREATE_STATION", "Station", s.station_id)
        flash("Station added.", "success")
        return redirect(url_for("stations_admin"))
    return render_template("station_new.html")


@app.route("/admin/stations/delete/<int:station_id>", methods=["POST"])
@login_required
@require_permission("admin.all")
def station_delete(station_id):
    s = Station.query.get_or_404(station_id)
    if Part.query.filter_by(station_id=station_id).count():
        flash("Cannot delete — parts assigned to this station.", "warning")
        return redirect(url_for("stations_admin"))
    db.session.delete(s)
    db.session.commit()
    log_action("DELETE_STATION", "Station", station_id)
    flash("Station deleted.", "success")
    return redirect(url_for("stations_admin"))


# ---------- Admin: Users ----------

@app.route("/admin/users")
@login_required
@require_permission("admin.all")
def users_admin():
    users = User.query.all()
    return render_template("users_admin.html", users=users)


@app.route("/admin/users/new", methods=["GET", "POST"])
@login_required
@require_permission("admin.all")
def user_new():
    roles = Role.query.all()
    if request.method == "POST":
        u = User(
            username=request.form["username"].strip(),
            full_name=request.form.get("full_name", "").strip(),
            password_hash=generate_password_hash(request.form["password"]),
            role_id=int(request.form["role_id"]))
        db.session.add(u)
        db.session.commit()
        log_action("CREATE_USER", "User", u.user_id)
        flash("User created.", "success")
        return redirect(url_for("users_admin"))
    return render_template("user_new.html", roles=roles)


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@login_required
@require_permission("admin.all")
def user_delete(user_id):
    u = User.query.get_or_404(user_id)
    if u.user_id == current_user.user_id:
        flash("You cannot delete your own account.", "warning")
        return redirect(url_for("users_admin"))
    has_activity = (
        StationLog.query.filter_by(operator_id=user_id).count() +
        Defect.query.filter_by(reported_by=user_id).count() +
        Rework.query.filter_by(technician_id=user_id).count() +
        Notice.query.filter_by(posted_by=user_id).count()
    ) > 0
    if has_activity:
        u.is_active_flag = False
        db.session.commit()
        log_action("DEACTIVATE_USER", "User", user_id)
        flash(f"User '{u.username}' deactivated (has activity records).", "warning")
    else:
        db.session.delete(u)
        db.session.commit()
        log_action("DELETE_USER", "User", user_id)
        flash(f"User '{u.username}' deleted.", "success")
    return redirect(url_for("users_admin"))


# ---------- Reports ----------

@app.route("/reports")
@login_required
@require_permission("line.view")
def reports():
    prod_rows = db.session.query(
        func.date(Chassis.completed_at).label('day'),
        func.count(Chassis.chassis_id)
    ).filter(Chassis.status == "COMPLETED")\
     .group_by(func.date(Chassis.completed_at))\
     .order_by(func.date(Chassis.completed_at)).all()
    prod_labels = [str(r[0]) for r in prod_rows]
    prod_values = [r[1] for r in prod_rows]

    pareto_rows = db.session.query(
        Defect.defect_type, func.count(Defect.defect_id)
    ).group_by(Defect.defect_type)\
     .order_by(func.count(Defect.defect_id).desc()).all()
    pareto_labels = [r[0] or "Unknown" for r in pareto_rows]
    pareto_values = [r[1] for r in pareto_rows]

    st_rows = db.session.query(
        Station.station_name, func.count(Defect.defect_id)
    ).join(Defect, Defect.station_id == Station.station_id)\
     .group_by(Station.station_name)\
     .order_by(Station.sequence).all()
    st_labels = [r[0] for r in st_rows]
    st_values = [r[1] for r in st_rows]

    sev_rows = db.session.query(Defect.severity, func.count(Defect.defect_id))\
                         .group_by(Defect.severity).all()
    sev_labels = [r[0] or "Unknown" for r in sev_rows]
    sev_values = [r[1] for r in sev_rows]

    scrap_st_rows = db.session.query(
        Station.station_name, func.count(Defect.defect_id)
    ).join(Defect, Defect.station_id == Station.station_id)\
     .filter(Defect.status == "SCRAPPED")\
     .group_by(Station.station_name)\
     .order_by(Station.sequence).all()
    scrap_st_labels = [r[0] for r in scrap_st_rows]
    scrap_st_values = [r[1] for r in scrap_st_rows]

    scrap_model_rows = db.session.query(
        BikeModel.model_name, func.count(Chassis.chassis_id)
    ).join(Chassis, Chassis.model_id == BikeModel.model_id)\
     .filter(Chassis.status == "SCRAPPED")\
     .group_by(BikeModel.model_name).all()
    scrap_model_labels = [r[0] for r in scrap_model_rows]
    scrap_model_values = [r[1] for r in scrap_model_rows]

    scrap_type_rows = db.session.query(
        Defect.defect_type, func.count(Defect.defect_id)
    ).filter(Defect.status == "SCRAPPED")\
     .group_by(Defect.defect_type)\
     .order_by(func.count(Defect.defect_id).desc()).all()
    scrap_type_labels = [r[0] or "Unknown" for r in scrap_type_rows]
    scrap_type_values = [r[1] for r in scrap_type_rows]

    scrapped_chassis = Chassis.query.filter_by(status="SCRAPPED")\
                                    .order_by(Chassis.created_at.desc())\
                                    .limit(20).all()

    scrapped_total = Chassis.query.filter_by(status="SCRAPPED").count()
    completed_total = Chassis.query.filter_by(status="COMPLETED").count()
    total_attempted = scrapped_total + completed_total
    scrap_rate = round((scrapped_total / total_attempted) * 100, 1) if total_attempted else 0

    status_counts = dict(db.session.query(Chassis.status, func.count(Chassis.chassis_id))
                         .group_by(Chassis.status).all())

    return render_template("reports.html",
        prod_labels=prod_labels, prod_values=prod_values,
        pareto_labels=pareto_labels, pareto_values=pareto_values,
        st_labels=st_labels, st_values=st_values,
        sev_labels=sev_labels, sev_values=sev_values,
        scrap_st_labels=scrap_st_labels, scrap_st_values=scrap_st_values,
        scrap_model_labels=scrap_model_labels, scrap_model_values=scrap_model_values,
        scrap_type_labels=scrap_type_labels, scrap_type_values=scrap_type_values,
        scrapped_chassis=scrapped_chassis,
        scrapped_total=scrapped_total,
        completed_total=completed_total,
        scrap_rate=scrap_rate,
        status_counts=status_counts)


# ---------- Audit ----------

@app.route("/audit")
@login_required
@require_permission("audit.view")
def audit():
    logs = AuditLog.query.order_by(AuditLog.audit_id.desc()).limit(300).all()
    return render_template("audit.html", logs=logs)


# ---------- Template helpers ----------

@app.context_processor
def inject_perms():
    def has(code):
        return current_user.is_authenticated and current_user.has_permission(code)
    return dict(has_permission=has)


@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


if __name__ == "__main__":
    app.run(debug=True)