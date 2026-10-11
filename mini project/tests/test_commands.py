from app.models import ActivityLog, CurriculumVersion, DegreeProgram, Semester, Subject, User


def test_demo_loader_is_labeled_and_idempotent(app):
    runner = app.test_cli_runner()
    first = runner.invoke(args=["load-demo-data"])
    second = runner.invoke(args=["load-demo-data"])
    assert first.exit_code == 0, first.output
    assert "DEMO DATA" in first.output
    assert second.exit_code == 0, second.output
    assert "already loaded" in second.output
    with app.app_context():
        program = DegreeProgram.query.filter_by(is_demo=True).one()
        version = CurriculumVersion.query.filter_by(program_id=program.id).one()
        assert version.verified is False
        assert Subject.query.join(Semester).filter(Semester.curriculum_version_id == version.id).count() == 12
        assert len(Subject.query.filter(Subject.prerequisites.any()).all()) > 0


def test_admin_setup_command_prompts_and_hashes_password(app):
    result = app.test_cli_runner().invoke(
        args=["create-admin"],
        input="root@example.test\nRoot Admin\nStrong-pass-123\nStrong-pass-123\n",
    )
    assert result.exit_code == 0, result.output
    with app.app_context():
        account = User.query.filter_by(email="root@example.test").one()
        assert account.role == "admin"
        assert account.check_password("Strong-pass-123")
        assert account.password_hash != "Strong-pass-123"
        assert ActivityLog.query.filter_by(action="admin.account_created").count() == 1
