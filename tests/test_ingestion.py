"""Tests for the ingestion pipeline.

All tests use isolated tmp_path fixtures and monkeypatch
`config.settings.DATA_RAW_DIR` -- none of them touch the real `data/raw/`
directory or depend on the full generated dataset.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from config import settings
from src.ingestion.batch import create_batch_id
from src.ingestion.loader import land_entity
from src.ingestion.manifest import write_batch_manifest
from src.ingestion.pipeline import ingest_all, ingest_dataset
from src.ingestion.reader import IngestionShapeError, read_raw_file, validate_file_shape
from src.ingestion.schemas import ENTITIES, EXPECTED_COLUMNS


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    raw_dir = tmp_path / "data" / "raw"
    monkeypatch.setattr(settings, "DATA_RAW_DIR", raw_dir)
    return raw_dir


def _write_csv(path: Path, columns, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        handle.write(",".join(columns) + "\n")
        for row in rows:
            handle.write(",".join(str(row[c]) for c in columns) + "\n")


@pytest.fixture
def fixture_incoming(isolated_data_dir):
    incoming = isolated_data_dir / "_incoming"
    for entity in ENTITIES:
        columns = EXPECTED_COLUMNS[entity]
        rows = [{c: f"{c}_{i}" for c in columns} for i in range(3)]
        _write_csv(incoming / entity / f"{entity}.csv", columns, rows)
    return incoming


# 1. batch id format -------------------------------------------------------


def test_create_batch_id_format():
    batch_id = create_batch_id()
    timestamp_part, _, suffix_part = batch_id.partition("_")
    assert len(timestamp_part) == 16  # YYYYMMDDTHHMMSSZ
    assert timestamp_part.endswith("Z")
    assert len(suffix_part) == 6


# 2. batch ids differ across runs ------------------------------------------


def test_batch_ids_are_unique_across_calls():
    ids = {create_batch_id() for _ in range(20)}
    assert len(ids) == 20


# 3. valid schema accepted ---------------------------------------------------


def test_validate_file_shape_accepts_expected_columns():
    df = pd.DataFrame(columns=EXPECTED_COLUMNS["customers"])
    validate_file_shape("customers", df)  # must not raise


# 4. missing column rejected -------------------------------------------------


def test_validate_file_shape_rejects_missing_column():
    columns = [c for c in EXPECTED_COLUMNS["customers"] if c != "email"]
    df = pd.DataFrame(columns=columns)
    with pytest.raises(IngestionShapeError):
        validate_file_shape("customers", df)


# 5. missing file rejected ---------------------------------------------------


def test_read_raw_file_missing_file_raises(tmp_path):
    with pytest.raises(IngestionShapeError):
        read_raw_file("customers", tmp_path / "does_not_exist.csv")


# 6. empty file rejected ------------------------------------------------------


def test_read_raw_file_zero_byte_file_raises(tmp_path):
    empty_file = tmp_path / "customers.csv"
    empty_file.write_text("")
    with pytest.raises(IngestionShapeError):
        read_raw_file("customers", empty_file)


def test_read_raw_file_header_only_raises(tmp_path):
    header_only = tmp_path / "customers.csv"
    header_only.write_text(",".join(EXPECTED_COLUMNS["customers"]) + "\n")
    with pytest.raises(IngestionShapeError):
        read_raw_file("customers", header_only)


# 7. correct batch output path -----------------------------------------------


def test_land_entity_writes_expected_path(isolated_data_dir):
    df = pd.DataFrame([{"customer_id": "C0001", "full_name": "Test"}])
    output_path = land_entity("customers", df, "batch123")
    expected = isolated_data_dir / "customers" / "batch_id=batch123" / "customers.csv"
    assert output_path == expected
    assert expected.exists()
    assert len(pd.read_csv(expected)) == 1


def test_land_entity_never_overwrites_existing_batch(isolated_data_dir):
    df = pd.DataFrame([{"a": 1}])
    land_entity("orders", df, "batchX")
    with pytest.raises(FileExistsError):
        land_entity("orders", df, "batchX")


# 8. manifest creation --------------------------------------------------------


def test_write_batch_manifest_creates_file(isolated_data_dir):
    results = [{"entity": "customers", "status": "ok", "row_count": 3}]
    path = write_batch_manifest("batch123", results)
    assert path.exists()
    content = json.loads(path.read_text())
    assert content["batch_id"] == "batch123"
    assert "ingested_at" in content
    assert content["entities"] == results


# 9. all five entities share one batch id -------------------------------------


def test_ingest_all_shares_one_batch_id(fixture_incoming, isolated_data_dir):
    run = ingest_all()
    assert len(run["results"]) == len(ENTITIES)
    assert all(r["status"] == "ok" for r in run["results"])

    batch_dirs = {Path(r["output_path"]).parent.name for r in run["results"]}
    assert batch_dirs == {f"batch_id={run['batch_id']}"}

    manifest_files = list((isolated_data_dir / "_batches").glob("*.json"))
    assert len(manifest_files) == 1


# 10. end-to-end ingestion using small fixtures --------------------------------


def test_ingest_dataset_end_to_end(fixture_incoming):
    result = ingest_dataset("customers", "batchABC")
    assert result["status"] == "ok"
    assert result["row_count"] == 3
    assert Path(result["output_path"]).exists()
    assert result["error"] is None


def test_ingest_dataset_missing_source_records_failure_without_raising(isolated_data_dir):
    result = ingest_dataset("customers", "batchABC")
    assert result["status"] == "failed"
    assert result["error"] is not None
    assert result["output_path"] is None


def test_ingest_all_continues_after_one_entity_fails(fixture_incoming):
    # Remove one entity's incoming file so it fails structurally.
    (fixture_incoming / "products" / "products.csv").unlink()

    run = ingest_all()
    by_entity = {r["entity"]: r for r in run["results"]}

    assert by_entity["products"]["status"] == "failed"
    assert by_entity["products"]["error"] is not None
    for entity in ENTITIES:
        if entity != "products":
            assert by_entity[entity]["status"] == "ok"
