"""SparkSession construction for the V2 transformation path.

One place builds the session, so the DAG task, the CLI entrypoint, and the
tests all get an identically-configured local Spark. Everything here is
local-only: ``local[*]`` master, no cluster, no external services.

Two portability problems are handled here so callers never have to:

1. **Java 17/21 module access.** Spark 3.5 predates the JPMS restrictions
   tightened in newer JDKs; without these ``--add-opens`` flags it fails
   with ``InaccessibleObjectException`` on Java 17+ (this project's host
   JDK is 21; the Docker image pins JDK 17).
2. **Python worker executable.** On Windows especially, Spark launches its
   Python workers as bare ``python``; if that resolves to the Microsoft
   Store shim (or the wrong interpreter) workers never connect back. We
   pin ``PYSPARK_PYTHON`` to the current interpreter.

Arrow-based ``toPandas()`` is left disabled: on JDK 21 it needs additional
direct-buffer access flags and buys nothing at this data size (the frames
converted to pandas are already aggregated down to a few thousand rows).
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from pyspark.sql import SparkSession

_ADD_OPENS_PACKAGES = (
    "java.lang",
    "java.lang.invoke",
    "java.lang.reflect",
    "java.io",
    "java.net",
    "java.nio",
    "java.util",
    "java.util.concurrent",
    "java.util.concurrent.atomic",
    "sun.nio.ch",
    "sun.nio.cs",
    "sun.security.action",
    "sun.util.calendar",
)

_JAVA_OPTIONS = " ".join(
    f"--add-opens=java.base/{pkg}=ALL-UNNAMED" for pkg in _ADD_OPENS_PACKAGES
) + (
    " --add-opens=java.security.jgss/sun.security.krb5=ALL-UNNAMED"
    " -Dio.netty.tryReflectionSetAccessible=true"
)

APP_NAME = "querypilot-spark-transform"


def build_spark_session(
    app_name: str = APP_NAME,
    shuffle_partitions: int = 4,
    master: Optional[str] = None,
) -> SparkSession:
    """A configured local SparkSession. Safe to call repeatedly -- Spark
    returns the existing active session if one is already running in the
    process (the DAG runs one task per process, but the CLI and tests may
    reuse a session)."""
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

    builder = (
        SparkSession.builder.master(master or os.getenv("SPARK_MASTER", "local[*]"))
        .appName(app_name)
        .config("spark.driver.extraJavaOptions", _JAVA_OPTIONS)
        .config("spark.executor.extraJavaOptions", _JAVA_OPTIONS)
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.sql.shuffle.partitions", str(shuffle_partitions))
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.execution.arrow.pyspark.enabled", "false")
        .config("spark.ui.enabled", os.getenv("SPARK_UI_ENABLED", "false"))
    )
    return builder.getOrCreate()


def stop_spark_session(spark: Optional[SparkSession]) -> None:
    """Stop a session if one was passed and it is still active. The DAG
    task and CLI stop their session when done; tests keep a module-scoped
    one alive across cases."""
    if spark is not None:
        try:
            spark.stop()
        except Exception:  # noqa: BLE001 - shutdown best effort, never fatal
            pass
