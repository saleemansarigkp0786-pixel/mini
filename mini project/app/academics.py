from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import Semester, StudentAcademicRecord, StudyTask, Subject, SubjectPrerequisite

bp = Blueprint("academics", __name__, url_prefix="/academics")
STATUSES = {"Planned", "In Progress", "Completed", "Pending"}


def owned_subject(subject_id):
    return Subject.query.join(Semester).filter(
        Subject.id == subject_id, Semester.owner_id == current_user.id
    ).first_or_404()


def ensure_record(subject, status=None, grade=None, notes=None):
    record = StudentAcademicRecord.query.filter_by(user_id=current_user.id, subject_id=subject.id).first()
    if not record:
        record = StudentAcademicRecord(user_id=current_user.id, subject_id=subject.id)
        db.session.add(record)
    if status is not None:
        record.status = status
        record.earned_credits = subject.credits if status == "Completed" else 0
    if grade is not None:
        record.grade = grade[:20]
    if notes is not None:
        record.notes = notes[:3000]
    return record


def prerequisite_cycle(subject, prerequisite):
    pending = [prerequisite]
    visited = set()
    while pending:
        candidate = pending.pop()
        if candidate.id == subject.id:
            return True
        if candidate.id not in visited:
            visited.add(candidate.id)
            pending.extend(candidate.prerequisites)
    return False


@bp.get("/roadmap")
@login_required
def roadmap():
    semesters = Semester.query.filter_by(owner_id=current_user.id).order_by(Semester.number).all()
    records = {record.subject_id: record for record in StudentAcademicRecord.query.filter_by(user_id=current_user.id)}
    return render_template("academics/roadmap.html", semesters=semesters, records=records)


@bp.get("/semesters/<int:semester_id>")
@login_required
def semester_detail(semester_id):
    semester = Semester.query.filter_by(id=semester_id, owner_id=current_user.id).first_or_404()
    records = {record.subject_id: record for record in StudentAcademicRecord.query.filter_by(user_id=current_user.id)}
    tasks = StudyTask.query.filter_by(user_id=current_user.id).join(
        Subject, StudyTask.subject_id == Subject.id
    ).filter(Subject.semester_id == semester.id).order_by(StudyTask.deadline).all()
    return render_template("academics/semester_detail.html", semester=semester, records=records, tasks=tasks)


@bp.get("/subjects/<int:subject_id>")
@login_required
def subject_detail(subject_id):
    subject = owned_subject(subject_id)
    record = StudentAcademicRecord.query.filter_by(user_id=current_user.id, subject_id=subject.id).first()
    records = {item.subject_id: item for item in StudentAcademicRecord.query.filter_by(user_id=current_user.id)}
    tasks = StudyTask.query.filter_by(user_id=current_user.id, subject_id=subject.id).order_by(StudyTask.deadline).all()
    missing = [item for item in subject.prerequisites
               if not StudentAcademicRecord.query.filter_by(user_id=current_user.id, subject_id=item.id, status="Completed").first()]
    return render_template("academics/subject_detail.html", subject=subject, record=record, records=records,
                           tasks=tasks, missing=missing)


@bp.route("/subjects/new", methods=["GET", "POST"])
@login_required
def subject_new():
    semesters = Semester.query.filter_by(owner_id=current_user.id).order_by(Semester.number).all()
    if request.method == "POST":
        try:
            semester_id = int(request.form.get("semester_id", ""))
            credits = float(request.form.get("credits", "0"))
            semester = Semester.query.filter_by(id=semester_id, owner_id=current_user.id).first_or_404()
            if not 0 <= credits <= 40:
                raise ValueError
        except ValueError:
            flash("Choose a semester and enter credits from 0 to 40.", "error")
            return render_template("academics/subject_form.html", subject=None, semesters=semesters)
        code = request.form.get("code", "").strip()[:40]
        name = request.form.get("name", "").strip()[:160]
        if not code or not name:
            flash("Subject code and name are required.", "error")
        else:
            subject = Subject(semester_id=semester.id, code=code, name=name, credits=credits,
                              category=request.form.get("category", "Core")[:80],
                              syllabus_units=request.form.get("syllabus_units", "")[:5000],
                              resources=request.form.get("resources", "")[:3000])
            db.session.add(subject)
            try:
                db.session.flush()
                prerequisites = request.form.getlist("prerequisites", type=int)
                for prerequisite_id in prerequisites:
                    prerequisite = owned_subject(prerequisite_id)
                    if prerequisite.id == subject.id:
                        raise ValueError("A subject cannot require itself.")
                    db.session.add(SubjectPrerequisite(subject_id=subject.id, prerequisite_id=prerequisite.id))
                ensure_record(subject)
                db.session.commit()
                flash("Subject added to your roadmap.", "success")
                return redirect(url_for("academics.roadmap"))
            except (IntegrityError, ValueError) as error:
                db.session.rollback()
                flash(str(error) if isinstance(error, ValueError) else "That subject code already exists in this semester.", "error")
    subjects = Subject.query.join(Semester).filter(Semester.owner_id == current_user.id).all()
    return render_template("academics/subject_form.html", subject=None, semesters=semesters, subjects=subjects)


@bp.route("/subjects/<int:subject_id>/edit", methods=["GET", "POST"])
@login_required
def subject_edit(subject_id):
    subject = owned_subject(subject_id)
    semesters = Semester.query.filter_by(owner_id=current_user.id).order_by(Semester.number).all()
    if request.method == "POST":
        subject.code = request.form.get("code", "").strip()[:40]
        subject.name = request.form.get("name", "").strip()[:160]
        subject.category = request.form.get("category", "Core")[:80]
        subject.syllabus_units = request.form.get("syllabus_units", "")[:5000]
        subject.resources = request.form.get("resources", "")[:3000]
        try:
            subject.credits = float(request.form.get("credits", "0"))
            subject.semester_id = int(request.form.get("semester_id", subject.semester_id))
            if not 0 <= subject.credits <= 40 or not Semester.query.filter_by(id=subject.semester_id, owner_id=current_user.id).first():
                raise ValueError
            prerequisites = []
            for prerequisite_id in request.form.getlist("prerequisites", type=int):
                prerequisite = owned_subject(prerequisite_id)
                if prerequisite.id == subject.id or prerequisite_cycle(subject, prerequisite):
                    raise ValueError("Prerequisites cannot create a subject dependency cycle.")
                prerequisites.append(prerequisite)
            subject.prerequisites = prerequisites
            db.session.commit()
            flash("Subject details updated.", "success")
            return redirect(url_for("academics.roadmap"))
        except (ValueError, IntegrityError) as error:
            db.session.rollback()
            flash(str(error) if isinstance(error, ValueError) and str(error) else "Check the semester, credits, prerequisites, and unique subject code.", "error")
    subjects = Subject.query.join(Semester).filter(Semester.owner_id == current_user.id, Subject.id != subject.id).all()
    return render_template("academics/subject_form.html", subject=subject, semesters=semesters, subjects=subjects)


@bp.post("/subjects/<int:subject_id>/delete")
@login_required
def subject_delete(subject_id):
    subject = owned_subject(subject_id)
    db.session.delete(subject)
    db.session.commit()
    flash("Subject removed from your personal plan.", "success")
    return redirect(url_for("academics.roadmap"))


@bp.post("/subjects/<int:subject_id>/status")
@login_required
def subject_status(subject_id):
    subject = owned_subject(subject_id)
    status = request.form.get("status")
    if status not in STATUSES:
        return jsonify(error="Invalid academic status."), 400
    missing = [item for item in subject.prerequisites
               if not StudentAcademicRecord.query.filter_by(user_id=current_user.id, subject_id=item.id, status="Completed").first()]
    if status == "Completed" and missing:
        return jsonify(error="Prerequisites still incomplete.", missing=[item.code for item in missing]), 409
    ensure_record(subject, status=status, grade=request.form.get("grade"), notes=request.form.get("notes"))
    db.session.commit()
    return jsonify(status=status, earned_credits=subject.credits if status == "Completed" else 0)


@bp.get("/progress")
@login_required
def progress():
    records = StudentAcademicRecord.query.filter_by(user_id=current_user.id).all()
    total_subjects = len(records)
    complete = [record for record in records if record.status == "Completed"]
    return render_template("academics/progress.html", records=records,
                           total=total_subjects, completed=len(complete),
                           pending=sum(record.status == "Pending" for record in records),
                           earned=sum(record.earned_credits for record in complete),
                           planned=sum(record.subject.credits for record in records),
                           percent=round(len(complete) * 100 / total_subjects) if total_subjects else 0)