from datetime import datetime, timedelta

from app.extensions import db
from app.models import (CareerGoal, CurriculumVersion, DegreeProgram, ProjectRecord,
                        Semester, Skill, StudentAcademicRecord, StudentSkill,
                        StudyTask, Subject, User)


def login(client, email="student@example.test", password="test-password-123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)


def make_semester(app, user_id, number=1):
    with app.app_context():
        semester = Semester(owner_id=user_id, number=number, title=f"Semester {number}")
        db.session.add(semester)
        db.session.commit()
        return semester.id


def test_onboarding_creates_personal_semesters_and_dates(client, app, user):
    login(client)
    response = client.post("/student/onboarding", data={
        "degree_type": "BTech", "branch": "CSE", "college": "Example College",
        "university": "Example University", "scheme": "Verified 2025",
        "current_semester": "2", "total_semesters": "3",
        "semester_start": "2026-08-01", "semester_end": "2026-12-15",
        "preferred_study_hours": "3", "target_role": "Python Developer",
    })
    assert response.status_code == 302
    with app.app_context():
        rows = Semester.query.filter_by(owner_id=user).order_by(Semester.number).all()
        assert len(rows) == 3
        assert rows[1].status == "In Progress"
        assert rows[1].start_date.isoformat() == "2026-08-01"


def test_verified_template_copies_into_private_subject_records(client, app, user):
    with app.app_context():
        program = DegreeProgram(name="Verified Example", branch="CSE")
        db.session.add(program)
        db.session.flush()
        version = CurriculumVersion(program_id=program.id, name="Current", verified=True)
        db.session.add(version)
        db.session.flush()
        semester = Semester(curriculum_version_id=version.id, number=1, title="Semester 1")
        db.session.add(semester)
        db.session.flush()
        template_subject = Subject(semester_id=semester.id, code="VER101", name="Verified subject", credits=3)
        db.session.add(template_subject)
        db.session.commit()
        version_id = version.id
        template_subject_id = template_subject.id
    login(client)
    response = client.post("/student/onboarding", data={
        "current_semester": "1", "total_semesters": "4", "preferred_study_hours": "2",
        "curriculum_version_id": version_id,
    })
    assert response.status_code == 302
    with app.app_context():
        copied = Subject.query.join(Semester).filter(Semester.owner_id == user, Subject.code == "VER101").one()
        assert copied.id != template_subject_id
        assert StudentAcademicRecord.query.filter_by(user_id=user, subject_id=copied.id).count() == 1
        assert db.session.get(Subject, template_subject_id).semester.curriculum_version_id == version_id


def test_semester_and_subject_detail_pages_render(client, app, user):
    semester_id = make_semester(app, user)
    with app.app_context():
        subject = Subject(semester_id=semester_id, code="VIEW101", name="Viewable subject", credits=3,
                         syllabus_units="Unit 1: Foundations", resources="https://example.test/notes")
        db.session.add(subject)
        db.session.commit()
        subject_id = subject.id
    login(client)
    semester_response = client.get(f"/academics/semesters/{semester_id}")
    subject_response = client.get(f"/academics/subjects/{subject_id}")
    assert semester_response.status_code == 200
    assert b"Viewable subject" in semester_response.data
    assert subject_response.status_code == 200
    assert b"Unit 1: Foundations" in subject_response.data


def test_subject_crud_and_completion_credits(client, app, user):
    semester_id = make_semester(app, user)
    login(client)
    created = client.post("/academics/subjects/new", data={
        "semester_id": semester_id, "code": "CS101", "name": "Programming",
        "credits": "4", "category": "Core",
    }, follow_redirects=True)
    assert created.status_code == 200
    with app.app_context():
        subject = Subject.query.filter_by(code="CS101").one()
        subject_id = subject.id
    response = client.post(f"/academics/subjects/{subject_id}/status", data={"status": "Completed", "grade": "A"})
    assert response.status_code == 200
    assert response.json["earned_credits"] == 4
    with app.app_context():
        record = StudentAcademicRecord.query.filter_by(user_id=user, subject_id=subject_id).one()
        assert record.earned_credits == 4
        record.status = "In Progress"
        record.earned_credits = 0
        db.session.commit()
        assert StudentAcademicRecord.query.filter_by(user_id=user, subject_id=subject_id).count() == 1


def test_prerequisite_validation_blocks_completion(client, app, user):
    first_semester = make_semester(app, user, 1)
    second_semester = make_semester(app, user, 2)
    with app.app_context():
        prerequisite = Subject(semester_id=first_semester, code="CS100", name="Intro", credits=3)
        subject = Subject(semester_id=second_semester, code="CS200", name="Advanced", credits=4)
        db.session.add_all([prerequisite, subject])
        db.session.flush()
        subject.prerequisites.append(prerequisite)
        db.session.commit()
        subject_id = subject.id
    login(client)
    response = client.post(f"/academics/subjects/{subject_id}/status", data={"status": "Completed"})
    assert response.status_code == 409
    assert response.json["missing"] == ["CS100"]


def test_subject_isolation_between_students(client, app, user):
    semester_id = make_semester(app, user)
    with app.app_context():
        other = User(name="Other Student", email="other@example.test")
        other.set_password("other-pass-123")
        db.session.add(other)
        db.session.commit()
        other_id = other.id
        subject = Subject(semester_id=semester_id, code="CS101", name="Private", credits=3)
        db.session.add(subject)
        db.session.commit()
        subject_id = subject.id
        other_semester = Semester(owner_id=other_id, number=1)
        db.session.add(other_semester)
        db.session.commit()
        their_subject = Subject(semester_id=other_semester.id, code="CS101", name="Their subject", credits=3)
        db.session.add(their_subject)
        db.session.commit()
        private_id = their_subject.id
    login(client, "other@example.test", "other-pass-123")
    assert client.get(f"/academics/subjects/{subject_id}/edit").status_code == 404
    assert client.post(f"/academics/subjects/{subject_id}/status", data={"status": "Completed"}).status_code == 404
    assert client.get(f"/academics/subjects/{private_id}/edit").status_code == 200


def test_tasks_filters_and_ownership(client, app, user):
    login(client)
    deadline = (datetime.now() + timedelta(days=2)).replace(second=0, microsecond=0)
    response = client.post("/planner/tasks", data={
        "title": "Lab report", "deadline": deadline.isoformat(timespec="minutes"),
        "priority": "High", "task_type": "Assignment", "description": "Write up",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Lab report" in response.data
    reminders = client.get("/planner/reminders")
    assert reminders.status_code == 200
    assert [item["title"] for item in reminders.json["reminders"]] == ["Lab report"]
    with app.app_context():
        task = StudyTask.query.filter_by(user_id=user).one()
        task_id = task.id
        assert task.priority == "High"
    with app.app_context():
        other = User(name="Other Student", email="second@example.test")
        other.set_password("other-pass-123")
        db.session.add(other)
        db.session.commit()
    client.post("/auth/logout")
    login(client, "second@example.test", "other-pass-123")
    assert client.get("/planner/reminders").json["reminders"] == []
    assert client.post(f"/planner/tasks/{task_id}/complete").status_code == 404


def test_what_if_does_not_change_academic_record(client, app, user):
    semester_id = make_semester(app, user)
    with app.app_context():
        subject = Subject(semester_id=semester_id, code="CS101", name="Planned", credits=4)
        db.session.add(subject)
        db.session.commit()
        subject_id = subject.id
    login(client)
    response = client.post("/planner/what-if", data={"subject_id": subject_id, "term": "3", "save": "yes"})
    assert response.status_code == 200
    assert b"simulation" in response.data.lower()
    with app.app_context():
        assert StudentAcademicRecord.query.filter_by(user_id=user).count() == 0
        assert len(db.session.get(User, user).saved_plans) == 1


def test_career_skill_tracking_and_project(client, app, user):
    login(client)
    client.post("/career/", data={"target_role": "Python Developer"}, follow_redirects=True)
    with app.app_context():
        goal = CareerGoal.query.filter_by(user_id=user).one()
        skill = StudentSkill.query.filter_by(career_goal_id=goal.id).first()
        skill_id = skill.id
    response = client.post(f"/career/skills/{skill_id}", data={"level": "Practiced"}, follow_redirects=True)
    assert response.status_code == 200
    client.post("/career/projects", data={"title": "Planner app", "kind": "Project", "url": "https://example.test"})
    with app.app_context():
        assert db.session.get(StudentSkill, skill_id).level == "Practiced"
        assert ProjectRecord.query.join(CareerGoal).filter(CareerGoal.user_id == user).count() == 1


def test_csv_import_validates_and_commits_atomically(client, app, admin):
    with app.app_context():
        program = DegreeProgram(name="Example program", branch="CSE")
        db.session.add(program)
        db.session.flush()
        version = CurriculumVersion(program_id=program.id, name="2026")
        db.session.add(version)
        db.session.commit()
        version_id = version.id
    client.post("/auth/login", data={"email": "admin@example.test", "password": "admin-password-123"})
    invalid = client.post(f"/admin/curriculum/{version_id}/import", data={
        "file": (bytes_file("semester,code,name,credits\n1,CS1,Intro,4\n0,BAD,Bad,-3\n"), "bad.csv")
    }, content_type="multipart/form-data")
    assert invalid.status_code == 200
    assert b"Line 3" in invalid.data
    with app.app_context():
        assert Subject.query.count() == 0
    valid = client.post(f"/admin/curriculum/{version_id}/import", data={
        "file": (bytes_file("semester,code,name,credits,category\n1,CS1,Intro,4,Core\n"), "good.csv")
    }, content_type="multipart/form-data", follow_redirects=True)
    assert b"Imported 1" in valid.data
    with app.app_context():
        assert Subject.query.filter_by(code="CS1").one().semester.curriculum_version_id == version_id


def bytes_file(content):
    from io import BytesIO
    return BytesIO(content.encode())