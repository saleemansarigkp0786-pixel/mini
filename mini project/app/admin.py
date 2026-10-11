import csv
import io

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import ActivityLog, CurriculumVersion, DegreeProgram, Semester, Subject, User

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


@bp.get("/")
@login_required
def dashboard():
    admin_required()
    return render_template("admin/dashboard.html", users=User.query.count(),
                           programs=DegreeProgram.query.count(), subjects=Subject.query.count(),
                           logs=ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(12).all())


@bp.get("/users")
@login_required
def users():
    admin_required()
    return render_template("admin/users.html", users=User.query.order_by(User.created_at.desc()).all())


@bp.post("/users/<int:user_id>")
@login_required
def update_user(user_id):
    admin_required()
    user = db.get_or_404(User, user_id)
    role = request.form.get("role")
    enabled = request.form.get("enabled")
    if role not in {"student", "admin"} or enabled not in {"true", "false"}:
        flash("Choose a valid role and account state.", "error")
    else:
        user.role = role
        user.is_enabled = enabled == "true"
        db.session.add(ActivityLog(actor_id=current_user.id, action="user.updated",
                                   detail=f"user_id={user.id}; role={role}; enabled={user.is_enabled}"))
        db.session.commit()
        flash("Account permissions updated.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/programs", methods=["GET", "POST"])
@login_required
def programs():
    admin_required()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        branch = request.form.get("branch", "").strip()
        version = request.form.get("version", "").strip()
        if not name or not branch or not version:
            flash("Program, branch, and version are required.", "error")
        else:
            program = DegreeProgram(name=name[:160], branch=branch[:120])
            db.session.add(program)
            db.session.flush()
            db.session.add(CurriculumVersion(program_id=program.id, name=version[:120]))
            db.session.add(ActivityLog(actor_id=current_user.id, action="curriculum.created", detail=name))
            db.session.commit()
            flash("Curriculum template created.", "success")
            return redirect(url_for("admin.programs"))
    return render_template("admin/programs.html", programs=DegreeProgram.query.order_by(DegreeProgram.name).all())


@bp.post("/curriculum/<int:version_id>/verify")
@login_required
def verify_version(version_id):
    admin_required()
    version = db.get_or_404(CurriculumVersion, version_id)
    requested_verified = request.form.get("verified") == "true"
    if version.program.is_demo and requested_verified:
        flash("Fictional demo data cannot be marked as institution-verified.", "error")
        return redirect(url_for("admin.programs"))
    version.verified = requested_verified
    db.session.add(ActivityLog(actor_id=current_user.id, action="curriculum.verification_changed",
                               detail=f"version_id={version.id}; verified={version.verified}"))
    db.session.commit()
    flash("Curriculum verification status updated.", "success")
    return redirect(url_for("admin.programs"))


@bp.route("/curriculum/<int:version_id>/import", methods=["GET", "POST"])
@login_required
def import_csv(version_id):
    admin_required()
    version = db.get_or_404(CurriculumVersion, version_id)
    errors = []
    if request.method == "POST":
        upload = request.files.get("file")
        if not upload or not upload.filename.lower().endswith(".csv"):
            errors.append("Upload a CSV file.")
        else:
            try:
                rows = csv.DictReader(io.StringIO(upload.stream.read().decode("utf-8-sig")))
                required = {"semester", "code", "name", "credits"}
                if not rows.fieldnames or not required.issubset(set(rows.fieldnames)):
                    errors.append("Required columns: semester, code, name, credits.")
                else:
                    parsed = []
                    for line, row in enumerate(rows, start=2):
                        try:
                            number = int(row["semester"])
                            credits = float(row["credits"])
                            if not 1 <= number <= 16 or not 0 <= credits <= 40 or not row["code"].strip() or not row["name"].strip():
                                raise ValueError
                            parsed.append((number, row["code"].strip(), row["name"].strip(), credits, row.get("category", "Core")))
                        except (ValueError, TypeError):
                            errors.append(f"Line {line}: invalid semester, code, name, or credits.")
                    if parsed and not errors:
                        semesters = {item.number: item for item in version.semesters}
                        for number, code, name, credits, category in parsed:
                            semester = semesters.get(number)
                            if not semester:
                                semester = Semester(curriculum_version_id=version.id, number=number,
                                                    title=f"Semester {number}", status="Planned")
                                db.session.add(semester)
                                db.session.flush()
                                semesters[number] = semester
                            db.session.add(Subject(semester_id=semester.id, code=code[:40], name=name[:160],
                                                   credits=credits, category=category[:80]))
                        db.session.add(ActivityLog(actor_id=current_user.id, action="curriculum.imported", detail=version.name))
                        try:
                            db.session.commit()
                            flash(f"Imported {len(parsed)} curriculum subjects.", "success")
                            return redirect(url_for("admin.programs"))
                        except IntegrityError:
                            db.session.rollback()
                            errors.append("One or more subject codes already exist in that semester; no rows were imported.")
            except (UnicodeDecodeError, csv.Error):
                errors.append("The file could not be read as UTF-8 CSV.")
    return render_template("admin/import.html", version=version, errors=errors)


@bp.get("/curriculum/<int:version_id>/export")
@login_required
def export_csv(version_id):
    admin_required()
    version = db.get_or_404(CurriculumVersion, version_id)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["semester", "code", "name", "credits", "category"])
    for semester in sorted(version.semesters, key=lambda item: item.number):
        for subject in semester.subjects:
            writer.writerow([semester.number, subject.code, subject.name, subject.credits, subject.category])
    return Response(stream.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=curriculum-{version.id}.csv"})