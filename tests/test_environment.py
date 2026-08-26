"""Foundational smoke tests for the project skeleton.

The real pipeline (ingestion, validation, transformation, warehouse
loading) is not implemented yet. These tests only confirm the
environment, configuration, and package layout are wired correctly
before any pipeline code is written.
"""

from config.settings import (
    DATA_CURATED_DIR,
    DATA_RAW_DIR,
    DATA_REJECTED_DIR,
    PROJECT_ROOT,
    postgres,
)


def test_project_root_resolves():
    assert PROJECT_ROOT.is_dir()


def test_data_directories_exist():
    for directory in (DATA_RAW_DIR, DATA_CURATED_DIR, DATA_REJECTED_DIR):
        assert directory.is_dir()


def test_postgres_settings_have_defaults():
    assert postgres.host
    assert postgres.port > 0
    assert postgres.database


def test_src_packages_importable():
    import src.catalog  # noqa: F401
    import src.ingestion  # noqa: F401
    import src.transformation  # noqa: F401
    import src.validation  # noqa: F401
    import src.warehouse  # noqa: F401
