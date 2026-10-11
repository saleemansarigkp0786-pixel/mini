from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import CareerGoal, ProjectRecord, Skill, StudentSkill

bp = Blueprint("career", __name__, url_prefix="/career")
ROADMAPS = {
    "Python Developer": ["Python", "SQL", "Git", "Testing", "REST APIs"],
    "Web Developer": ["HTML and CSS", "JavaScript", "HTTP", "SQL", "Git"],
    "Data Analyst": ["Python", "SQL", "Statistics", "Data visualization", "Spreadsheets"],
    "Software Engineer": ["Data structures", "Algorithms", "Git", "Testing", "System design"],
    "AI/ML Engineer": ["Python", "Linear algebra", "Statistics", "Machine learning", "Data preparation"],
}
LEVELS = {"Not Started", "Learning", "Practiced", "Completed"}


@bp.route("/", methods=["GET", "POST"])
@login_required
def roadmap():
    goal = CareerGoal.query.filter_by(user_id=current_user.id).first()
    if request.method == "POST":
        role = request.form.get("target_role", "").strip()
        if role not in ROADMAPS:
            flash("Select one of the available career directions.", "error")
        else:
            if not goal:
                goal = CareerGoal(user_id=current_user.id, target_role=role)
                db.session.add(goal)
                db.session.flush()
            goal.target_role = role
            present = {item.skill.name for item in goal.skills}
            for name in ROADMAPS[role]:
                skill = Skill.query.filter_by(name=name).first()
                if not skill:
                    skill = Skill(name=name, recommendation=True)
                    db.session.add(skill)
                    db.session.flush()
                if name not in present:
                    db.session.add(StudentSkill(career_goal_id=goal.id, skill_id=skill.id))
            current_user.target_role = role
            db.session.commit()
            flash("Career direction updated. Recommendations are editable, not placement requirements.", "success")
            return redirect(url_for("career.roadmap"))
    return render_template("career/roadmap.html", goal=goal, roles=ROADMAPS.keys())


@bp.post("/skills/<int:student_skill_id>")
@login_required
def update_skill(student_skill_id):
    item = StudentSkill.query.join(CareerGoal).filter(
        StudentSkill.id == student_skill_id, CareerGoal.user_id == current_user.id
    ).first_or_404()
    level = request.form.get("level")
    if level not in LEVELS:
        flash("Choose a valid skill level.", "error")
    else:
        item.level = level
        db.session.commit()
        flash("Skill progress saved.", "success")
    return redirect(url_for("career.roadmap"))


@bp.post("/projects")
@login_required
def add_project():
    goal = CareerGoal.query.filter_by(user_id=current_user.id).first_or_404()
    title = request.form.get("title", "").strip()
    if title:
        db.session.add(ProjectRecord(career_goal_id=goal.id, title=title[:160],
                                     kind=request.form.get("kind", "Project")[:40],
                                     url=request.form.get("url", "")[:500],
                                     notes=request.form.get("notes", "")[:2000]))
        db.session.commit()
        flash("Portfolio item added.", "success")
    return redirect(url_for("career.roadmap"))