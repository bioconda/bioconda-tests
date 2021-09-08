#! /usr/bin/env python

from datetime import datetime, timezone
from typing import Optional

from ntplib import NTPClient, NTPException


def get_ntp_time(client: Optional[NTPClient] = None) -> datetime:
    ntp_pool = (
        "0.pool.ntp.org",
        "1.pool.ntp.org",
        "2.pool.ntp.org",
        "3.pool.ntp.org",
    )
    if client is None:
        client = NTPClient()
    errors = []
    for server in ntp_pool:
        try:
            response = client.request(server, version=4, timeout=2)
        except NTPException as e:
            errors.append(e)
            continue
        time = datetime.utcfromtimestamp(response.tx_time)
        return time.replace(tzinfo=timezone.utc)
    raise NTPException(f"Could not get timestamp. Errors: {errors}")


def format_utc_time(utc_time: datetime) -> str:
    assert utc_time.tzinfo == timezone.utc
    return utc_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def parse_utc_time(utc_time_str: str) -> datetime:
    time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S+00:00")
    return time.replace(tzinfo=timezone.utc)


if __name__ == "__main__":
    print(format_utc_time(get_ntp_time()))
