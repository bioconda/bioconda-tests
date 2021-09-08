#! /usr/bin/env python

import os
import sys

from argparse import ArgumentParser
from json import dump, loads
from pathlib import Path
from re import sub
from signal import SIGINT
from subprocess import CalledProcessError, CompletedProcess, PIPE, Popen, TimeoutExpired
from tempfile import TemporaryDirectory
from typing import Any, Dict, Generator, List, Optional, Tuple

from urllib3 import PoolManager


STATUS_SUCCESS = "success"
STATUS_TIMEOUT = "timeout"
STATUS_FAILED = "failed"

TIMEOUT_MAMBA_CREATE = 3 * 60
TIMEOUT_MAMBABUILD = 9 * 60


def call(*args, **kwargs) -> CompletedProcess:
    """
    Similar to subprocess.check_output but also sends SIGINT to child processes on timeout.
    """
    # NOTE: This is Unix-specific. If we started to use this for Windows, changes are needed.
    timeout = kwargs.pop("timeout", None)
    with Popen(*args, **kwargs, stdout=PIPE, preexec_fn=os.setsid) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except TimeoutExpired:
            process.kill()
            os.killpg(process.pid, SIGINT)
            process.wait()
            raise
        except:
            process.kill()
            raise
        retcode = process.poll()
        if retcode:
            raise CalledProcessError(retcode, process.args, output=stdout, stderr=stderr)
    return CompletedProcess(process.args, retcode, stdout, stderr)


def test_build(
    output_root: Path,
    package: str,
    package_fetch_info: Dict[str, Any],
    timeout: int,
    conda_build_impl: str,
) -> str:
    archive_url = package_fetch_info["url"]
    download_url = sub(
        "https://github.com/bioconda/bioconda-repodata-archive/raw/.*/repodata/https=3A=2F/",
        "https://",
        archive_url,
    )
    file_name = package_fetch_info["fn"]
    subdir = package_fetch_info["subdir"]
    with TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir, subdir, file_name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with PoolManager() as http:
            response = http.request("GET", download_url, preload_content=False)
            with file_path.open("wb") as f:
                for chunk in response.stream():
                    f.write(chunk)
        env = os.environ.copy()
        env["CONDA_QUIET"] = "1"
        try:
            stdout = call(
                [
                    conda_build_impl,
                    "--test",
                    file_path,
                ],
                env=env,
                timeout=timeout,
            ).stdout
        except TimeoutExpired as exc:
            status = STATUS_TIMEOUT
            log = exc.stdout
        except CalledProcessError as exc:
            status = STATUS_FAILED
            log = exc.stdout
        else:
            status = STATUS_SUCCESS
        if status != STATUS_SUCCESS:
            log_path = output_root / package / f"{conda_build_impl}-create.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_bytes(log)
        return status


def solve(
    output_root: Path, package: str, timeout: int, conda_impl: str
) -> Tuple[str, Dict[str, Any]]:
    fetch_info: Optional[Dict[str, Any]] = None
    env = os.environ.copy()
    env["CONDA_QUIET"] = "1"
    env["CONDA_RC"] = str(Path.home() / "solve_only_condarc")
    try:
        stdout = call(
            [
                conda_impl,
                "create",
                "--dry-run",
                "--name=solve",
                "--json",
                package,
            ],
            env=env,
            timeout=timeout,
        ).stdout
    except TimeoutExpired as exc:
        status = STATUS_TIMEOUT
        log = exc.stdout
    except CalledProcessError as exc:
        status = STATUS_FAILED
        log = exc.stdout
    else:
        status = STATUS_SUCCESS
        fetch_actions = loads(stdout)["actions"]["FETCH"]
        (package_fetch_info,) = (info for info in fetch_actions if info["name"] == package)
    if status != STATUS_SUCCESS:
        log_path = output_root / package / f"{conda_impl}-create.log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_bytes(log)
    return status, package_fetch_info


def test_package_mamba(output_root: Path, package: str) -> Dict[str, Any]:
    status: Dict[str, Any] = {
        "implementation": "mamba",
        "solve": "not run",
        "test": "not run",
        "package": None,
    }
    solve_status, package_fetch_info = solve(
        output_root, package, TIMEOUT_MAMBA_CREATE, "mamba"
    )
    status["solve"] = solve_status
    if not package_fetch_info:
        return status
    status["package"] = {
        key: package_fetch_info[key]
        for key in ("name", "version", "build", "build_number", "subdir", "channel")
    }
    test_status = test_build(
        output_root, package, package_fetch_info, TIMEOUT_MAMBABUILD, "conda-mambabuild"
    )
    status["test"] = test_status
    return status


def test_package(output_root: Path, platform: str, package: str) -> None:
    mamba_status = test_package_mamba(output_root, package)
    status = {
        "name": package,
        "platform": platform,
        "status": [mamba_status],
    }
    status_file_path = output_root / package / "status.json"
    status_file_path.parent.mkdir(parents=True, exist_ok=True)
    with status_file_path.open("w") as status_file:
        dump(status, status_file, indent=1, sort_keys=True)


def get_lines(file_path: Path) -> Generator[str, None, None]:
    if not file_path.is_file():
        return
    with file_path.open() as file:
        yield from filter(None, map(str.strip, file))


def get_argument_parser() -> ArgumentParser:
    arg_parser = ArgumentParser()
    arg_parser.add_argument(
        "--workspace",
        default=".",
    )
    arg_parser.add_argument(
        "--subdir",
        action="append",
    )
    return arg_parser


def main(args: Optional[List[str]] = None) -> None:
    arg_parser = get_argument_parser()
    parsed_args = arg_parser.parse_args(args)

    workspace = Path(parsed_args.workspace)
    subdirs = parsed_args.subdir
    platform = subdirs[0]
    output_root = workspace / platform
    output_root.mkdir(parents=True, exist_ok=True)

    packages = sorted({
        package
        for subdir in subdirs
        for package in get_lines(workspace / "selected_packages" / f"{subdir}.txt")
    })
    for i, package in enumerate(packages, 1):
        test_package(output_root, platform, package)


if __name__ == "__main__":
    main()
