"""
Docker Sandbox — Secure, Isolated Code Execution

Runs agent-generated code inside ephemeral Docker containers with:
  - Memory limits (default 128MB)
  - CPU limits (default 20% of one core)
  - Network isolation (no outbound connections)
  - Read-only filesystem (with /tmp for writes)
  - Non-root execution (nobody user)
  - Hard timeout enforcement
  - Automatic container cleanup

Supports Python and JavaScript (Node.js) runtimes.

Security model:
  Standard Docker containers share the host kernel, so for untrusted
  code this is "sandbox-lite". For production deployments with truly
  untrusted code, replace the Docker runtime with gVisor (runsc)
  by setting DOCKER_DEFAULT_RUNTIME=runsc in your Docker config.

Usage::

    sandbox = DockerSandbox()
    result = await sandbox.execute_python("print('hello world')")
    print(result.stdout)  # 'hello world'
"""

import asyncio
import contextlib
import io
import json
import tarfile
import textwrap
import time
import uuid
from dataclasses import dataclass

import docker
import structlog

from app.config import settings

log = structlog.get_logger()

# Docker client (connects to Docker daemon via socket)
try:
    _docker_client = docker.from_env()
    _docker_available = True
except Exception as e:
    log.warning("sandbox.docker_unavailable", error=str(e))
    _docker_client = None
    _docker_available = False


@dataclass
class SandboxResult:
    """Result of a sandboxed code execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    error: str | None = None


class DockerSandbox:
    """
    Manages ephemeral Docker containers for secure code execution.

    Each call to `execute_python()` or `execute_node()`:
      1. Creates a new container with resource/network limits
      2. Copies the code in via a tar archive (no volume mounts)
      3. Runs the code, captures stdout/stderr
      4. Removes the container unconditionally (via finally block)
    """

    def __init__(self) -> None:
        self.client = _docker_client
        self.memory_limit = settings.sandbox_memory_limit
        self.cpu_quota = settings.sandbox_cpu_quota
        self.timeout = settings.sandbox_timeout_seconds

    async def execute_python(self, code: str, stdin: str = "") -> SandboxResult:
        """Execute Python code in an isolated Docker container."""
        return await self._execute(
            image=settings.sandbox_python_image,
            code=code,
            filename="solution.py",
            command="python /sandbox/solution.py",
            stdin=stdin,
        )

    async def execute_node(self, code: str, stdin: str = "") -> SandboxResult:
        """Execute JavaScript/Node.js code in an isolated Docker container."""
        return await self._execute(
            image=settings.sandbox_node_image,
            code=code,
            filename="solution.js",
            command="node /sandbox/solution.js",
            stdin=stdin,
        )

    async def _execute(
        self,
        image: str,
        code: str,
        filename: str,
        command: str,
        stdin: str = "",
    ) -> SandboxResult:
        """
        Core execution method — creates container, runs code, cleans up.

        The code is injected via a tar archive to avoid shell injection
        vulnerabilities that would occur with command-line string interpolation.
        """
        if not self.client or not _docker_available:
            return SandboxResult(
                success=False,
                stdout="",
                stderr="Docker is not available in this environment",
                exit_code=-1,
                duration_ms=0,
                error="sandbox_unavailable",
            )

        container_name = f"agentcraft-sandbox-{uuid.uuid4().hex[:8]}"
        container = None
        start_time = time.monotonic()

        try:
            # Create the container (do NOT start yet)
            container = await asyncio.to_thread(
                self.client.containers.create,
                image=image,
                name=container_name,
                command=command,
                # ─── Security hardening ────────────────────────────────────
                mem_limit=self.memory_limit,        # Hard memory cap
                cpu_quota=self.cpu_quota,            # CPU throttle (microseconds)
                cpu_period=100_000,                  # 100ms period
                network_mode="none",                 # No network access
                read_only=True,                      # Immutable filesystem
                tmpfs={"/tmp": "size=64m", "/sandbox": "size=32m"},
                user="nobody",                       # Non-root user
                security_opt=["no-new-privileges"],  # Prevent privilege escalation
                cap_drop=["ALL"],                    # Drop all Linux capabilities
            )

            # Inject code via tar archive (avoids shell injection)
            tar_data = self._create_tar(filename, code)
            await asyncio.to_thread(container.put_archive, "/sandbox", tar_data)

            # Start the container
            await asyncio.to_thread(container.start)

            # Wait with timeout
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(container.wait),
                    timeout=self.timeout,
                )
                exit_code = result.get("StatusCode", -1)
                timed_out = False
            except asyncio.TimeoutError:
                await asyncio.to_thread(container.kill)
                exit_code = -1
                timed_out = True

            # Capture output
            logs = await asyncio.to_thread(container.logs, stdout=True, stderr=True)
            raw = logs.decode("utf-8", errors="replace") if logs else ""

            # Separate stdout/stderr (Docker mixes them unless using split=True)
            logs_stdout = await asyncio.to_thread(
                container.logs, stdout=True, stderr=False
            )
            logs_stderr = await asyncio.to_thread(
                container.logs, stdout=False, stderr=True
            )

            stdout = logs_stdout.decode("utf-8", errors="replace") if logs_stdout else ""
            stderr = logs_stderr.decode("utf-8", errors="replace") if logs_stderr else ""

            duration_ms = int((time.monotonic() - start_time) * 1000)

            if timed_out:
                stderr += f"\n[SANDBOX] Execution timed out after {self.timeout}s"

            result_obj = SandboxResult(
                success=(exit_code == 0),
                stdout=stdout[:50_000],   # Cap at 50KB
                stderr=stderr[:10_000],   # Cap at 10KB
                exit_code=exit_code,
                duration_ms=duration_ms,
                error="timeout" if timed_out else None,
            )

            log.info(
                "sandbox.executed",
                image=image,
                exit_code=exit_code,
                duration_ms=duration_ms,
                stdout_len=len(stdout),
            )
            return result_obj

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log.error("sandbox.error", error=str(exc), image=image)
            return SandboxResult(
                success=False,
                stdout="",
                stderr=str(exc),
                exit_code=-1,
                duration_ms=duration_ms,
                error=str(exc),
            )
        finally:
            # Always clean up the container
            if container:
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(container.remove, force=True)

    @staticmethod
    def _create_tar(filename: str, content: str) -> bytes:
        """Create an in-memory tar archive containing a single code file."""
        content_bytes = content.encode("utf-8")
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            info = tarfile.TarInfo(name=filename)
            info.size = len(content_bytes)
            tf.addfile(info, io.BytesIO(content_bytes))
        return buf.getvalue()
