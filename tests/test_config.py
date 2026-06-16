from config import APP_PAGES, CHECKPOINT_DB, DB_NAME, PROJECT_NAME


def test_project_name():
    assert PROJECT_NAME == "lager-agent"


def test_app_pages_have_dashboard_first():
    assert APP_PAGES[0] == "Dashboard"
    assert "Agent" in APP_PAGES


def test_database_paths_use_data_directory():
    assert DB_NAME.name == "lager.db"
    assert CHECKPOINT_DB.name == "checkpoints.db"
    assert DB_NAME.parent.name == "data"
