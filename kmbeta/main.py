# TODO Change based on geo-location


import json
import time
import curses
import datetime as dt
from typing import List
from curses import wrapper
from dataclasses import dataclass


import requests


json_file = "./data.json"


@dataclass
class EtaData:
    stop_name: str
    bus_number: str
    eta_data: List[int]


def get_stop_info(stop_name_en: str) -> List:
    stop_url = "https://data.etabus.gov.hk/v1/transport/kmb/stop"
    stop_name_en = stop_name_en.upper()
    res = requests.get(stop_url).json()
    data = res["data"]
    stop_data = [s for s in data if s["name_en"] == stop_name_en]
    return stop_data


def get_eta(stop_name: str, bus_no: str, endpoint: str) -> EtaData:
    stops = get_stop_info(stop_name)

    etas = []

    for stop in stops:
        stop_id = stop["stop"]
        eta_url = (
            f"https://data.etabus.gov.hk/v1/transport/kmb/eta/{stop_id}/{bus_no}/1"
        )

        rsp = requests.get(eta_url).json()
        data = rsp["data"]
        endpoint = endpoint.upper()

        for item in data:
            if item["dest_en"] == endpoint:
                eta = (
                    dt.datetime.fromisoformat(item["eta"])
                    if item["eta"] is not None
                    else None
                )
                if eta is None:
                    continue

                now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
                mins_remaining = round((eta - now).total_seconds() / 60)
                etas.append(mins_remaining)

    return EtaData(stop_name=stop_name, bus_number=bus_no, eta_data=etas)


def display_eta(window: curses.window, data: EtaData):
    window.addstr(0, 0, data.stop_name)
    window.addstr(1, 0, data.bus_number)
    window.addstr(2, 0, "\n--".join(data.eta_data))


def run(stdscr):
    # The `screen` is a window that acts as the master window
    # that takes up the whole screen. Other windows created
    # later will get painted on to the `screen` window.
    screen = curses.initscr()
    screen.clrtobot()
    # lines, columns, start line, start column
    my_window = curses.newwin(20, 20, 0, 0)
    my_window.box()
    my_window.refresh()

    curses.napms(2000)
    screen.clear()
    screen.refresh()
    curses.endwin()


if __name__ == "__main__":
    wrapper(run)
