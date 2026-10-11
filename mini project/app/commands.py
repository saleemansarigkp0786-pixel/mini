import click
from flask import current_app
from flask.cli import with_appcontext

from .extensions import db
from .models import (ActivityLog, CurriculumVersion, DegreeProgram, Semester,
                     Subject, User)


def register_commands(app):
    @app.cli.command("create-admin")
    @with_appcontext
    def create_admin():
        """Create or promote an administrator without a hardcoded password."""
        email = click.prompt("Admin email").strip().lower()
        name = click.prompt("Admin name").strip()
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        if len(password) < 10 or not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
            raise click.ClickException("Use at least 10 characters including a letter and a number.")
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(email=email, name=name)
            db.session.add(user)
        user.role = "admin"
        user.is_enabled = True
        user.set_password(password)
        db.session.add(ActivityLog(action="admin.account_created", detail=email))
        db.session.commit()
        click.echo(f"Administrator account ready for {email}.")

    @app.cli.command("load-demo-data")
    @with_appcontext
    def load_demo_data():
        """Load fictional, explicitly unverified BTech CSE sample curriculum."""
        program = DegreeProgram.query.filter_by(name="DegreePath DEMO DATA: BTech CSE").first()
        if program:
            click.echo("DEMO DATA is already loaded; no changes made.")
            return
        program = DegreeProgram(name="DegreePath DEMO DATA: BTech CSE", branch="Computer Science and Engineering",
                                description="Fictional sample curriculum for demonstration only.", is_demo=True)
        db.session.add(program)
        db.session.flush()
        version = CurriculumVersion(program_id=program.id, name="DEMO DATA — unverified sample", verified=False)
        db.session.add(version)
        db.session.flush()
        subject_rows = [
            (1, "MAT101", "Engineering Mathematics I", 4, "Foundation", []),
            (1, "CSE101", "Programming Fundamentals", 4, "Core", []),
            (1, "PHY101", "Applied Physics", 3, "Foundation", []),
            (2, "MAT102", "Discrete Mathematics", 4, "Foundation", ["MAT101"]),
            (2, "CSE102", "Object-Oriented Programming", 4, "Core", ["CSE101"]),
            (2, "ECE102", "Digital Systems", 3, "Core", []),
            (3, "CSE201", "Data Structures", 4, "Core", ["CSE102"]),
            (3, "CSE202", "Computer Organization", 3, "Core", ["ECE102"]),
            (3, "MAT201", "Probability and Statistics", 3, "Foundation", ["MAT102"]),
            (4, "CSE203", "Database Systems", 4, "Core", ["CSE201"]),
            (4, "CSE204", "Operating Systems", 4, "Core", ["CSE201", "CSE202"]),
            (4, "CSE205", "Software Engineering", 3, "Core", ["CSE102"]),
        ]
        semester_map = {}
        subject_map = {}
        for number, code, name, credits, category, prerequisites in subject_rows:
            semester = semester_map.get(number)
            if semester is None:
                semester = Semester(curriculum_version_id=version.id, number=number,
                                    title=f"Semester {number}", status="Planned")
                db.session.add(semester)
                db.session.flush()
                semester_map[number] = semester
            subject = Subject(semester_id=semester.id, code=code, name=name,
                              credits=credits, category=category)
            db.session.add(subject)
            db.session.flush()
            for prerequisite_code in prerequisites:
                subject.prerequisites.append(subject_map[prerequisite_code])
            subject_map[code] = subject
        db.session.commit()
        click.echo("Loaded 12 fictional subjects across four semesters. Clearly labeled DEMO DATA; not an official curriculum.")