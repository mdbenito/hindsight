"""PostgreSQL lifecycle manager for Android.

Manages an embedded PostgreSQL instance bundled in the APK assets.
Handles extraction, initialization, startup, and shutdown.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time


class PostgresManager:
    """Manages an embedded PostgreSQL server on Android."""

    def __init__(self, base_dir: str):
        """
        Args:
            base_dir: App's internal files directory (e.g., /data/data/pkg/files)
        """
        self.base_dir = base_dir
        self.pg_dir = os.path.join(base_dir, "postgres")
        self.pg_bin = os.path.join(self.pg_dir, "bin")
        self.pg_lib = os.path.join(self.pg_dir, "lib")
        self.pg_share = os.path.join(self.pg_dir, "share")
        self.data_dir = os.path.join(base_dir, "pg-data")
        self.log_file = os.path.join(base_dir, "pg.log")
        self.port = 5432
        self._process: subprocess.Popen | None = None

    @property
    def database_url(self) -> str:
        return f"postgresql://hindsight@localhost:{self.port}/hindsight"

    def is_initialized(self) -> bool:
        """Check if PG data directory exists."""
        return os.path.exists(os.path.join(self.data_dir, "PG_VERSION"))

    def is_running(self) -> bool:
        """Check if PG is accepting connections."""
        try:
            result = subprocess.run(
                [os.path.join(self.pg_bin, "pg_isready"), "-p", str(self.port)],
                capture_output=True,
                timeout=5,
                env=self._pg_env(),
            )
            return result.returncode == 0
        except Exception:
            return False

    def extract_binaries(self, assets_dir: str) -> None:
        """Extract PG binaries from APK assets to app files dir.

        The assets should contain a tar.gz of the PostgreSQL installation
        compiled for ARM64 Android.
        """
        import tarfile

        archive = os.path.join(assets_dir, "postgres-arm64.tar.gz")
        if not os.path.exists(archive):
            raise FileNotFoundError(
                f"PostgreSQL archive not found at {archive}. "
                "Build it with scripts/android/build-pg-binary.sh"
            )

        if os.path.exists(self.pg_dir):
            shutil.rmtree(self.pg_dir)

        os.makedirs(self.pg_dir, exist_ok=True)

        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(self.pg_dir)

        # Make binaries executable
        for name in os.listdir(self.pg_bin):
            path = os.path.join(self.pg_bin, name)
            os.chmod(path, 0o755)

    def initialize(self) -> None:
        """Run initdb to create a new database cluster."""
        if self.is_initialized():
            return

        os.makedirs(self.data_dir, exist_ok=True)

        result = subprocess.run(
            [
                os.path.join(self.pg_bin, "initdb"),
                "-D",
                self.data_dir,
                "--auth=trust",
                "--username=hindsight",
            ],
            capture_output=True,
            text=True,
            env=self._pg_env(),
        )
        if result.returncode != 0:
            raise RuntimeError(f"initdb failed: {result.stderr}")

    def start(self) -> None:
        """Start PostgreSQL server."""
        if self.is_running():
            return

        env = self._pg_env()

        self._process = subprocess.Popen(
            [
                os.path.join(self.pg_bin, "postgres"),
                "-D",
                self.data_dir,
                "-p",
                str(self.port),
                "-k",
                "/tmp",
            ],
            env=env,
            stdout=open(self.log_file, "a"),
            stderr=subprocess.STDOUT,
        )

        # Wait for PG to be ready
        for _ in range(30):
            if self.is_running():
                return
            time.sleep(0.5)

        raise RuntimeError("PostgreSQL failed to start. Check pg.log")

    def create_database(self) -> None:
        """Create the hindsight database and install pgvector."""
        env = self._pg_env()

        # Create database (ignore error if exists)
        subprocess.run(
            [
                os.path.join(self.pg_bin, "createdb"),
                "-p",
                str(self.port),
                "-U",
                "hindsight",
                "hindsight",
            ],
            capture_output=True,
            env=env,
        )

        # Install pgvector extension
        subprocess.run(
            [
                os.path.join(self.pg_bin, "psql"),
                "-p",
                str(self.port),
                "-U",
                "hindsight",
                "-d",
                "hindsight",
                "-c",
                "CREATE EXTENSION IF NOT EXISTS vector;",
            ],
            capture_output=True,
            env=env,
        )

    def stop(self) -> None:
        """Stop PostgreSQL server."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

    def _pg_env(self) -> dict:
        """Environment variables for PG subprocess."""
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = self.pg_lib
        env["PGDATA"] = self.data_dir
        env["PGPORT"] = str(self.port)
        env["PGUSER"] = "hindsight"
        env["PGHOST"] = "localhost"
        # Termux/Android-specific
        env["TMPDIR"] = "/tmp"
        return env


def setup_postgres(base_dir: str, assets_dir: str | None = None) -> PostgresManager:
    """Full PostgreSQL setup: extract, init, start, create DB.

    Returns a running PostgresManager instance.
    """
    mgr = PostgresManager(base_dir)

    if assets_dir and not os.path.exists(mgr.pg_bin):
        mgr.extract_binaries(assets_dir)

    if not mgr.is_initialized():
        mgr.initialize()

    if not mgr.is_running():
        mgr.start()

    mgr.create_database()
    return mgr
