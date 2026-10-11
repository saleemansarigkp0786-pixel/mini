from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student", index=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    degree_type = db.Column(db.String(80))
    branch = db.Column(db.String(120))
    college = db.Column(db.String(160))
    university = db.Column(db.String(160))
    scheme = db.Column(db.String(100))
    current_semester = db.Column(db.Integer)
    total_semesters = db.Column(db.Integer)
    academic_goals = db.Column(db.Text)
    target_role = db.Column(db.String(100))
    preferred_study_hours = db.Column(db.Integer, default=2)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    semesters = db.relationship("Semester", back_populates="owner", cascade="all, delete-orphan")
    records = db.relationship("StudentAcademicRecord", back_populates="user", cascade="all, delete-orphan")
    tasks = db.relationship("StudyTask", back_populates="user", cascade="all, delete-orphan")
    career_goals = db.relationship("CareerGoal", back_populates="user", cascade="all, delete-orphan")
    saved_plans = db.relationship("SavedPlan", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_active(self):
        return self.is_enabled


class DegreeProgram(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    branch = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    is_demo = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    versions = db.relationship("CurriculumVersion", back_populates="program", cascade="all, delete-orphan")


class CurriculumVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey("degree_program.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    regulation_year = db.Column(db.Integer)
    verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    program = db.relationship("DegreeProgram", back_populates="versions")
    semesters = db.relationship("Semester", back_populates="curriculum", cascade="all, delete-orphan")


class Semester(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), index=True)
    curriculum_version_id = db.Column(db.Integer, db.ForeignKey("curriculum_version.id", ondelete="CASCADE"), index=True)
    number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(100))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="Planned", nullable=False)
    owner = db.relationship("User", back_populates="semesters")
    curriculum = db.relationship("CurriculumVersion", back_populates="semesters")
    subjects = db.relationship("Subject", back_populates="semester", cascade="all, delete-orphan")
    __table_args__ = (
        db.UniqueConstraint("owner_id", "number", name="uq_owned_semester_number"),
        db.UniqueConstraint("curriculum_version_id", "number", name="uq_template_semester_number"),
    )


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    semester_id = db.Column(db.Integer, db.ForeignKey("semester.id", ondelete="CASCADE"), nullable=False, index=True)
    code = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    credits = db.Column(db.Float, nullable=False, default=0)
    category = db.Column(db.String(80), default="Core")
    syllabus_units = db.Column(db.Text, default="")
    resources = db.Column(db.Text, default="")
    semester = db.relationship("Semester", back_populates="subjects")
    prerequisites = db.relationship(
        "Subject", secondary="subject_prerequisite",
        primaryjoin="Subject.id == SubjectPrerequisite.subject_id",
        secondaryjoin="Subject.id == SubjectPrerequisite.prerequisite_id",
        backref="required_by",
    )
    records = db.relationship("StudentAcademicRecord", back_populates="subject", cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("semester_id", "code", name="uq_semester_subject_code"),)


class SubjectPrerequisite(db.Model):
    __tablename__ = "subject_prerequisite"
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id", ondelete="CASCADE"), primary_key=True)
    prerequisite_id = db.Column(db.Integer, db.ForeignKey("subject.id", ondelete="CASCADE"), primary_key=True)


class StudentAcademicRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(20), default="Planned", nullable=False)
    grade = db.Column(db.String(20))
    earned_credits = db.Column(db.Float, default=0, nullable=False)
    notes = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    user = db.relationship("User", back_populates="records")
    subject = db.relationship("Subject", back_populates="records")
    __table_args__ = (
        db.UniqueConstraint("user_id", "subject_id", name="uq_user_subject_record"),
        db.CheckConstraint("earned_credits >= 0", name="ck_record_credits_nonnegative"),
    )


class StudyTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(180), nullable=False)
    task_type = db.Column(db.String(40), default="Assignment", nullable=False)
    deadline = db.Column(db.DateTime, nullable=False, index=True)
    priority = db.Column(db.String(20), default="Medium", nullable=False)
    status = db.Column(db.String(20), default="Upcoming", nullable=False, index=True)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    user = db.relationship("User", back_populates="tasks")
    subject = db.relationship("Subject")


class CareerGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    target_role = db.Column(db.String(100), nullable=False)
    user = db.relationship("User", back_populates="career_goals")
    skills = db.relationship("StudentSkill", back_populates="goal", cascade="all, delete-orphan")
    projects = db.relationship("ProjectRecord", back_populates="goal", cascade="all, delete-orphan")


class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(db.String(80), default="Technical")
    recommendation = db.Column(db.Boolean, default=True, nullable=False)


class StudentSkill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    career_goal_id = db.Column(db.Integer, db.ForeignKey("career_goal.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skill.id", ondelete="CASCADE"), nullable=False)
    level = db.Column(db.String(20), default="Not Started", nullable=False)
    goal = db.relationship("CareerGoal", back_populates="skills")
    skill = db.relationship("Skill")
    __table_args__ = (db.UniqueConstraint("career_goal_id", "skill_id", name="uq_goal_skill"),)


class ProjectRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    career_goal_id = db.Column(db.Integer, db.ForeignKey("career_goal.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    kind = db.Column(db.String(40), default="Project")
    url = db.Column(db.String(500), default="")
    notes = db.Column(db.Text, default="")
    goal = db.relationship("CareerGoal", back_populates="projects")


class SavedPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    scenario = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    user = db.relationship("User", back_populates="saved_plans")


class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), index=True)
    action = db.Column(db.String(100), nullable=False)
    detail = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)