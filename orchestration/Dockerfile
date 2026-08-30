# Local Airflow image for the QueryPilot V2 pipeline (Airflow + PySpark).
# Airflow itself comes from the official base image; this adds a JRE for
# Spark and the handful of project runtime packages the DAG's tasks import.
#
# Build context is the repo root:
#   docker compose -f docker-compose.airflow.yml build
#
# The pipeline's DAGs and Spark code live under orchestration/ and src/;
# both are bind-mounted at runtime (see docker-compose.airflow.yml). NOTE
# the directory is orchestration/ (not airflow/) so it can never shadow
# the installed `airflow` Python package on PYTHONPATH.

FROM apache/airflow:2.10.3-python3.11

USER root

# Spark 3.5 needs a JVM. JDK 17 is the Spark-supported LTS (the host may
# run 21; the container pins 17 for a clean, warning-free run).
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# amd64 layout. On arm64 hosts this is /usr/lib/jvm/java-17-openjdk-arm64
# -- override JAVA_HOME in docker-compose.airflow.yml if you build on arm64.
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

USER airflow

COPY orchestration/requirements-airflow.txt /tmp/requirements-airflow.txt
RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt
