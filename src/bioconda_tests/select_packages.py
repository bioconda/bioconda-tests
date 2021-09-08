#! /usr/bin/env python

from argparse import ArgumentParser
from collections import defaultdict
from datetime import datetime, timezone
from functools import partial
from json import loads
from logging import INFO, basicConfig, getLogger
from pathlib import Path
from subprocess import DEVNULL, check_call
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Optional

from .ntp_time import format_utc_time, get_ntp_time, parse_utc_time

_log = getLogger(__name__)


def git(*args: str, **kwargs: Any) -> None:
    check_call(
        ("git", *args),
        stdout=DEVNULL,
        **kwargs,
    )


def fetch_package_downloads(stats_dir: Path) -> Dict[str, int]:
    channel_dir = stats_dir / "package-downloads" / "anaconda.org" / "bioconda"
    total_package_downloads: Dict[str, int] = {}
    for json_file in channel_dir.glob("*.json"):
        if not json_file.is_file():
            continue
        stats = loads(json_file.read_text())
        package = stats["package"]
        downloads = stats["downloads_per_date"][-1]["total"]
        total_package_downloads[package] = downloads
    return total_package_downloads


_time0 = datetime.utcfromtimestamp(0).replace(tzinfo=timezone.utc)


def get_processed_packages(now: datetime) -> Dict[str, datetime]:
    base_path = Path("./status")
    packages: Dict[str, datetime] = {}
    for package_path in base_path.glob("*"):
        status_json_path = package_path / "status.json"
        if not status_json_path.is_file():
            continue
        name = package_path.name
        status = loads(status_json_path.read_text())
        state = status["state"]
        time = parse_utc_time(status["started_at"])
        if state == "running":
            if (now - time).days > 1:
                # unfinished / interupted job
                packages[name] = _time0
            else:
                # already running in another job
                packages[name] = now
        else:
            # finished job
            packages[name] = time
    return packages


def get_selected_packages(now: datetime, num_packages: int, stats_dir: Path) -> List[str]:
    package_downloads = fetch_package_downloads(stats_dir)
    processed_packages = get_processed_packages(now)
    packages = {}
    for package, downloads in package_downloads.items():
        time = processed_packages.get(package, _time0)
        if time != now:
            packages[package] = (processed_packages.get(package, _time0), -downloads)

    selected_packages = sorted(packages.keys(), key=packages.__getitem__)
    if num_packages > 0:
        return selected_packages[:num_packages]
    return selected_packages


def get_argument_parser() -> ArgumentParser:
    arg_parser = ArgumentParser()
    arg_parser.add_argument(
        "--num-packages",
        type=int,
        default=1,
    )
    arg_parser.add_argument(
        "--output-dir",
        default="selected_packages",
    )
    return arg_parser


def main(args: Optional[List[str]] = None) -> None:
    arg_parser = get_argument_parser()
    parsed_args = arg_parser.parse_args(args)
    num_packages = parsed_args.num_packages or 0
    output_dir = Path(parsed_args.output_dir)

    now = get_ntp_time()

    with TemporaryDirectory() as temp_dir:
        stats_dir = Path(temp_dir)
        git_ = partial(git, cwd=stats_dir)
        git_(
            "clone",
            "--depth=1",
            "--filter=blob:none",
            "--no-checkout",
            "https://github.com/bioconda/bioconda-stats",
            ".",
        )
        git_("sparse-checkout", "init")
        git_("sparse-checkout", "set", "package-downloads/anaconda.org/bioconda/*.json")
        git_("checkout", "--quiet")

        selected_packages = get_selected_packages(now, num_packages, stats_dir)
        channel_dir = stats_dir / "package-downloads" / "anaconda.org" / "bioconda"
        subdir_lists: Dict[str, List[str]] = defaultdict(list)
        for package in selected_packages:
            git_(
                "sparse-checkout",
                "add",
                f"package-downloads/anaconda.org/bioconda/{package}/*/*.json",
            )
            subdirs = {
                path.name[: -len(".json")] for path in (channel_dir / package).glob("*/*.json")
            }
            if "noarch" in subdirs:
                subdirs = {"noarch"}
            for subdir in subdirs:
                subdir_lists[subdir].append(package)
    output_dir.mkdir(parents=True)
    for subdir, subdir_packages in subdir_lists.items():
        with (output_dir / f"{subdir}.txt").open("w") as list_file:
            for package in subdir_packages:
                print(package, file=list_file)


if __name__ == "__main__":
    basicConfig(level=INFO)
    main()
