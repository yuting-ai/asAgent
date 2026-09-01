import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_DIRECTORY = _PROJECT_ROOT / "desktop" / "build" / "dist" / "asagent-backend"
_EXECUTABLE_NAME = "asagent-backend.exe" if os.name == "nt" else "asagent-backend"
_BUNDLE_EXECUTABLE = _BUNDLE_DIRECTORY / _EXECUTABLE_NAME
_READY_PREFIX = "ASAGENT_READY "
_TOKEN = "sidecar-smoke-token"
_START_TIMEOUT_SECONDS = 10.0
_RUN_TIMEOUT_SECONDS = 10.0
_KNOWLEDGE_TIMEOUT_SECONDS = 60.0


async def main() -> None:
    if not _BUNDLE_EXECUTABLE.is_file():
        raise RuntimeError(
            "Sidecar bundle is missing. Run `uv run python scripts/build_backend.py` first.",
        )

    with tempfile.TemporaryDirectory(prefix="asagent-sidecar-smoke-") as directory:
        temporary_root = Path(directory)
        working_directory = temporary_root / "outside-source"
        app_home = temporary_root / "app-home"
        knowledge_source = temporary_root / "knowledge-source"
        working_directory.mkdir()
        knowledge_source.mkdir()
        (knowledge_source / "bundle-smoke.md").write_text(
            "# Frozen Knowledge Smoke\n\n"
            "The cobalt lighthouse verifies bundled local knowledge retrieval.\n",
            encoding="utf-8",
        )

        process = await asyncio.create_subprocess_exec(
            str(_BUNDLE_EXECUTABLE),
            "serve",
            "--bootstrap-stdin",
            "--app-home",
            str(app_home),
            "--port",
            "0",
            cwd=working_directory,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            assert process.stdin is not None
            assert process.stdout is not None

            process.stdin.write(json.dumps({"token": _TOKEN}).encode() + b"\n")
            await process.stdin.drain()
            process.stdin.close()

            ready = await _read_ready(process)
            base_url = f"http://{ready['host']}:{ready['port']}"
            headers = {"Authorization": f"Bearer {_TOKEN}"}

            async with httpx.AsyncClient(
                base_url=base_url,
                headers=headers,
                timeout=2.0,
            ) as client:
                health = await client.get("/api/v1/health")
                health.raise_for_status()
                assert health.json() == {"status": "ok"}

                conversation = await client.post("/api/v1/conversations", json={})
                assert conversation.status_code == 201
                conversation_id = conversation.json()["conversation_id"]

                submission = await client.post(
                    f"/api/v1/conversations/{conversation_id}/messages",
                    json={"content": "calculate 2 + 2"},
                )
                assert submission.status_code == 201
                run_id = submission.json()["run"]["run_id"]

                await _wait_for_completion(client, run_id)

                messages = await client.get(
                    f"/api/v1/conversations/{conversation_id}/messages",
                )
                messages.raise_for_status()
                assert [message["content"] for message in messages.json()] == [
                    "calculate 2 + 2",
                    "Tool result: 4",
                ]

                libraries = await client.get("/api/v1/knowledge/libraries")
                libraries.raise_for_status()
                library_id = libraries.json()[0]["library_id"]

                source = await client.post(
                    f"/api/v1/knowledge/libraries/{library_id}/sources",
                    json={"path": str(knowledge_source)},
                )
                source.raise_for_status()
                source_id = source.json()["source_id"]

                index = await client.post(
                    f"/api/v1/knowledge/sources/{source_id}/index",
                )
                index.raise_for_status()
                await _wait_for_knowledge_index(client, index.json()["job_id"])

                search = await client.post(
                    f"/api/v1/knowledge/libraries/{library_id}/search",
                    json={"query": "What verifies bundled local knowledge retrieval?"},
                )
                search.raise_for_status()
                hits = search.json()["hits"]
                assert hits
                assert hits[0]["document_name"] == "bundle-smoke.md"
                assert "cobalt lighthouse" in hits[0]["snippet"].lower()

            assert (app_home / "data" / "asagent.sqlite3").is_file()
            assert not list(_BUNDLE_DIRECTORY.rglob("*.sqlite3"))
        finally:
            await _stop_process(process)


async def _read_ready(
    process: asyncio.subprocess.Process,
) -> dict[str, str | int]:
    assert process.stdout is not None

    try:
        async with asyncio.timeout(_START_TIMEOUT_SECONDS):
            while line := await process.stdout.readline():
                decoded = line.decode().strip()
                if decoded.startswith(_READY_PREFIX):
                    payload = json.loads(decoded.removeprefix(_READY_PREFIX))
                    assert payload["host"] == "127.0.0.1"
                    assert isinstance(payload["port"], int)
                    return payload
    except TimeoutError as error:
        raise RuntimeError("Sidecar did not report readiness in time.") from error

    raise RuntimeError("Sidecar exited before reporting readiness.")


async def _wait_for_completion(
    client: httpx.AsyncClient,
    run_id: str,
) -> None:
    try:
        async with asyncio.timeout(_RUN_TIMEOUT_SECONDS):
            while True:
                response = await client.get(f"/api/v1/runs/{run_id}")
                response.raise_for_status()
                status = response.json()["status"]

                if status == "completed":
                    return
                if status in {"failed", "cancelled"}:
                    raise RuntimeError(f"Sidecar Run ended as {status}.")

                await asyncio.sleep(0.05)
    except TimeoutError as error:
        raise RuntimeError("Sidecar Run did not complete in time.") from error


async def _wait_for_knowledge_index(
    client: httpx.AsyncClient,
    job_id: str,
) -> None:
    try:
        async with asyncio.timeout(_KNOWLEDGE_TIMEOUT_SECONDS):
            while True:
                response = await client.get(f"/api/v1/knowledge/jobs/{job_id}")
                response.raise_for_status()
                status = response.json()["status"]

                if status == "completed":
                    assert response.json()["indexed_chunks"] > 0
                    return
                if status in {"failed", "cancelled", "interrupted"}:
                    raise RuntimeError(f"Knowledge index ended as {status}.")

                await asyncio.sleep(0.05)
    except TimeoutError as error:
        raise RuntimeError("Knowledge index did not complete in time.") from error


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return

    process.terminate()
    try:
        async with asyncio.timeout(3.0):
            await process.wait()
    except TimeoutError:
        process.kill()
        await process.wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        print(f"Sidecar smoke failed: {error}", file=sys.stderr)
        raise
