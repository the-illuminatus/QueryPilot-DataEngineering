"""DAG-import smoke test for the V2 Airflow pipeline.

Skips unless ``apache-airflow`` is importable. Airflow is deliberately NOT
a V1 dependency -- it lives only in the Docker image
(docker-compose.airflow.yml) -- so in the normal environment this whole
module is skipped and the V1 suite is unaffected. It runs inside the
Airflow image, where it verifies the DAG parses, has the expected task
ids, and wires them in the required order.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("airflow.models", reason="apache-airflow not installed (V1 env)")

from airflow.models import DagBag  # noqa: E402

_DAG_ID = "querypilot_data_pipeline"
_DAGS_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "orchestration", "dags")

_EXPECTED_TASKS = [
    "generate_or_stage_raw",
    "validate",
    "pyspark_transform",
    "write_curated",
    "load_postgres",
    "quality_check",
]


@pytest.fixture(scope="module")
def dag():
    bag = DagBag(dag_folder=_DAGS_FOLDER, include_examples=False)
    assert not bag.import_errors, f"DAG import errors: {bag.import_errors}"
    d = bag.get_dag(_DAG_ID)
    assert d is not None, f"{_DAG_ID} not found in {_DAGS_FOLDER}"
    return d


def test_dag_has_expected_tasks(dag):
    assert sorted(t.task_id for t in dag.tasks) == sorted(_EXPECTED_TASKS)


def test_dag_is_a_linear_chain(dag):
    for upstream, downstream in zip(_EXPECTED_TASKS, _EXPECTED_TASKS[1:]):
        task = dag.get_task(downstream)
        assert {t.task_id for t in task.upstream_list} == {upstream}, downstream


def test_dag_run_settings(dag):
    assert dag.schedule_interval is None
    assert dag.max_active_runs == 1
    assert dag.catchup is False
