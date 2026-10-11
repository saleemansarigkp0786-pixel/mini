from datetime import date, datetime, time, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import SavedPlan, Semester, StudentAcademicRecord, StudyTask, Subject

bp = Blueprint("planner", __name__, url_prefix="/planner")
TASK_TYPES = {"Assignment", "Exam", "Practical", "Revision", "Project milestone", "Study goal"}


@bp.get("/reminders")
@login_required
def reminders():
    now = datetime.now()
    items = StudyTask.query.filter_by(user_id=current_user.id).filter(
        StudyTask.status != "Completed", StudyTask.deadline >= now
    ).order_by(StudyTask.deadline).limit(50).all()
    return jsonify(reminders=[{
        "title": task.title,
        "deadline": task.deadline.isoformat(),
        "kind": task.task_type,
    } for task in items])


@bp.route("/tasks", methods=["GET", "POST"])
@login_required
def tasks():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        try:
            deadline = datetime.fromisoformat(request.form.get("deadline", ""))
            subject_id = int(request.form.get("subject_id")) if request.form.get("subject_id") else None
            if subject_id and not Subject.query.join(Semester).filter(Subject.id == subject_id, Semester.owner_id == current_user.id).first():
                raise ValueError
            task_type = request.form.get("task_type", "Assignment")
            priority = request.form.get("priority", "Medium")
            if task_type not in TASK_TYPES or priority not in {"Low", "Medium", "High"} or not title:
                raise ValueError
        except ValueError:
            flash("Check the task title, type, priority, date, and subject.", "error")
        else:
            db.session.add(StudyTask(user_id=current_user.id, subject_id=subject_id,
                                     title=title[:180], task_type=task_type, deadline=deadline,
                                     priority=priority, description=request.form.get("description", "")[:3000]))
            db.session.commit()
            flash("Planner item added.", "success")
            return redirect(url_for("planner.tasks"))
    filter_name = request.args.get("filter", "Upcoming")
    query = StudyTask.query.filter_by(user_id=current_user.id)
    today = date.today()
    today_start = datetime.combine(today, time.min)
    tomorrow = today_start + timedelta(days=1)
    if filter_name == "Completed":
        query = query.filter_by(status="Completed")
    elif filter_name == "Overdue":
        query = query.filter(StudyTask.status != "Completed", StudyTask.deadline < today_start)
    elif filter_name == "Today":
        query = query.filter(StudyTask.deadline >= today_start, StudyTask.deadline < tomorrow)
    else:
        filter_name = "Upcoming"
        query = query.filter(StudyTask.status != "Completed")
    task_list = query.order_by(StudyTask.deadline).all()
    subjects = Subject.query.join(Semester).filter(Semester.owner_id == current_user.id).all()
    return render_template("planner/tasks.html", tasks=task_list, subjects=subjects,
                           selected_filter=filter_name, today=today)


@bp.post("/tasks/<int:task_id>/complete")
@login_required
def complete_task(task_id):
    task = StudyTask.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    task.status = "Completed"
    db.session.commit()
    flash("Planner item completed.", "success")
    return redirect(url_for("planner.tasks"))


@bp.route("/what-if", methods=["GET", "POST"])
@login_required
def what_if():
    records = StudentAcademicRecord.query.filter_by(user_id=current_user.id).all()
    if request.method == "POST":
        try:
            subject_id = int(request.form.get("subject_id", ""))
            subject = Subject.query.join(Semester).filter(Subject.id == subject_id, Semester.owner_id == current_user.id).first_or_404()
            term = int(request.form.get("term", "1"))
            if not 1 <= term <= 16:
                raise ValueError
        except ValueError:
            flash("Choose a valid subject and future term.", "error")
        else:
            completed_ids = {record.subject_id for record in records if record.status == "Completed"}
            missing = [prerequisite.code for prerequisite in subject.prerequisites if prerequisite.id not in completed_ids]
            scenario = {"subject_id": subject.id, "subject": subject.name, "term": term,
                        "assumptions": ["This is a simulation, not an approved academic plan.",
                                        "Existing academic records are not changed."] + ([f"Prerequisites to clear first: {', '.join(missing)}"] if missing else [])}
            if request.form.get("save") == "yes":
                db.session.add(SavedPlan(user_id=current_user.id, title=f"Plan: {subject.name}", scenario=scenario))
                db.session.commit()
                flash("Scenario saved separately from your academic record.", "success")
            return render_template("planner/what_if.html", subjects=Subject.query.join(Semester).filter(Semester.owner_id == current_user.id).all(), scenario=scenario)
    subjects = Subject.query.join(Semester).filter(Semester.owner_id == current_user.id).all()
    return render_template("planner/what_if.html", subjects=subjects, scenario=None)