from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import CurriculumVersion, Semester, StudentAcademicRecord, StudyTask, Subject

bp = Blueprint("student", __name__, url_prefix="/student")


@bp.get("/verified-curricula")
@login_required
def verified_curricula():
    versions = CurriculumVersion.query.filter_by(verified=True).join(CurriculumVersion.program).order_by(CurriculumVersion.name).all()
    return jsonify(curricula=[{
        "id": version.id,
        "name": version.program.name,
        "branch": version.program.branch,
        "version": version.name,
        "semesters": max((semester.number for semester in version.semesters), default=0),
    } for version in versions if not version.program.is_demo])


@bp.get("/dashboard")
@login_required
def dashboard():
    semesters = Semester.query.filter_by(owner_id=current_user.id).order_by(Semester.number).all()
    records = StudentAcademicRecord.query.filter_by(user_id=current_user.id).all()
    tasks = StudyTask.query.filter_by(user_id=current_user.id, status="Upcoming").order_by(StudyTask.deadline).limit(5).all()
    total = len(records)
    completed = [record for record in records if record.status == "Completed"]
    stats = {
        "total": total,
        "completed": len(completed),
        "pending": sum(record.status == "Pending" for record in records),
        "credits": sum(record.earned_credits for record in completed),
        "planned_credits": sum(record.subject.credits for record in records),
        "progress": round(len(completed) * 100 / total) if total else 0,
        "backlogs": sum(record.status == "Pending" for record in records),
    }
    return render_template("student/dashboard.html", semesters=semesters, stats=stats, tasks=tasks)


@bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    def render_setup():
        versions = CurriculumVersion.query.filter_by(verified=True).join(CurriculumVersion.program).order_by(CurriculumVersion.name).all()
        return render_template("student/onboarding_form.html", verified_curricula=[item for item in versions if not item.program.is_demo])

    if request.method == "POST":
        try:
            current = int(request.form.get("current_semester", "1"))
            total = int(request.form.get("total_semesters", "8"))
            hours = int(request.form.get("preferred_study_hours", "2"))
            if not (1 <= current <= total <= 16 and 1 <= hours <= 16):
                raise ValueError
        except ValueError:
            flash("Check semester numbers and study hours; values are outside the allowed range.", "error")
            return render_setup()
        current_user.degree_type = request.form.get("degree_type", "").strip()[:80]
        current_user.branch = request.form.get("branch", "").strip()[:120]
        current_user.college = request.form.get("college", "").strip()[:160]
        current_user.university = request.form.get("university", "").strip()[:160]
        current_user.scheme = request.form.get("scheme", "").strip()[:100]
        current_user.current_semester = current
        current_user.total_semesters = total
        current_user.academic_goals = request.form.get("academic_goals", "").strip()[:3000]
        current_user.target_role = request.form.get("target_role", "").strip()[:100]
        current_user.preferred_study_hours = hours
        existing_rows = Semester.query.filter_by(owner_id=current_user.id).all()
        if any(semester.number > total and semester.subjects for semester in existing_rows):
            flash("Move or remove subjects from later semesters before reducing your degree length.", "error")
            return render_setup()
        existing = {semester.number: semester for semester in existing_rows}
        semester_start = request.form.get("semester_start", "").strip()
        semester_end = request.form.get("semester_end", "").strip()
        try:
            start_date = date.fromisoformat(semester_start) if semester_start else None
            end_date = date.fromisoformat(semester_end) if semester_end else None
            if start_date and end_date and start_date > end_date:
                raise ValueError
        except ValueError:
            flash("The semester end date must be on or after its start date.", "error")
            return render_setup()
        for number in range(1, total + 1):
            semester = existing.get(number)
            if semester is None:
                semester = Semester(owner_id=current_user.id, number=number,
                                    title=f"Semester {number}")
                db.session.add(semester)
            semester.status = "In Progress" if number == current else "Planned"
        for semester in existing_rows:
            if semester.number > total:
                db.session.delete(semester)
            db.session.flush()
        current_row = Semester.query.filter_by(owner_id=current_user.id, number=current).first()
        if current_row:
            current_row.start_date = start_date
            current_row.end_date = end_date
        selected_version_id = request.form.get("curriculum_version_id", "").strip()
        if selected_version_id:
            try:
                version = CurriculumVersion.query.filter_by(id=int(selected_version_id), verified=True).first()
            except ValueError:
                version = None
            if not version or version.program.is_demo:
                flash("Choose a valid verified curriculum template.", "error")
                return render_setup()
            if StudentAcademicRecord.query.filter_by(user_id=current_user.id).first() or any(
                semester.subjects for semester in Semester.query.filter_by(owner_id=current_user.id)
            ):
                flash("Remove your current personal subjects before copying a template.", "error")
                return render_setup()
            source_semesters = sorted(version.semesters, key=lambda item: item.number)
            if not source_semesters or any(item.number > total for item in source_semesters):
                flash("The selected curriculum does not fit the total semesters in your degree setup.", "error")
                return render_setup()
            destination = {item.number: item for item in Semester.query.filter_by(owner_id=current_user.id)}
            subject_map = {}
            pending_links = []
            for source_semester in source_semesters:
                target_semester = destination[source_semester.number]
                for source_subject in source_semester.subjects:
                    subject = Subject(
                        semester_id=target_semester.id, code=source_subject.code,
                        name=source_subject.name, credits=source_subject.credits,
                        category=source_subject.category, syllabus_units=source_subject.syllabus_units,
                        resources=source_subject.resources,
                    )
                    db.session.add(subject)
                    db.session.flush()
                    subject_map[source_subject.id] = subject
                    pending_links.extend((subject, prerequisite.id) for prerequisite in source_subject.prerequisites)
            for subject, prerequisite_id in pending_links:
                if prerequisite_id in subject_map:
                    subject.prerequisites.append(subject_map[prerequisite_id])
            for subject in subject_map.values():
                db.session.add(StudentAcademicRecord(user_id=current_user.id, subject_id=subject.id))
        db.session.commit()
        flash("Your degree plan has been saved.", "success")
        return redirect(url_for("student.dashboard"))
    return render_setup()


@bp.get("/profile")
@login_required
def profile():
    return render_template("student/profile.html")