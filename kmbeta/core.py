#!/usr/bin/env python3

import aiohttp
import asyncio
import datetime as dt
from typing import List
from dataclasses import dataclass


@dataclass
class BusETA:
    bus: str
    stop: str
    etas: List[dt.datetime]


@dataclass
class BusStop:
    id: str
    name: str
    latitude: float
    longitude: float


class BusKMB:

    stop_url = "https://data.etabus.gov.hk/v1/transport/kmb/stop"
    eta_url = "https://data.etabus.gov.hk/v1/transport/kmb/eta"

    def __init__(self, stops: List[BusStop]):
        self.stops = stops

    async def get_eta(self, bus, destination):
        all_etas = []

        for s in self.stops:
            i = s.id
            stop = s.name
            eta_url = f"{self.eta_url}/{i}/{bus}/1"

            async with aiohttp.ClientSession() as session:
                async with session.get(eta_url) as response:
                    res = await response.json()
                    stop_data = res.get("data")
                    if stop_data == [] or stop_data is None:
                        continue
                    else:
                        first = stop_data[0]
                        if first["dest_en"] == destination:
                            times = []
                            for eta in stop_data:
                                time = dt.datetime.fromisoformat(eta["eta"])
                                times.append(time)

                            eta = BusETA(bus=bus, stop=stop, etas=times)
                            all_etas.append(eta)
                        else:
                            continue

        print(all_etas)

    @classmethod
    async def get_stop_info(cls, stop_name_en: str) -> List[BusStop]:

        async with aiohttp.ClientSession() as session:
            async with session.get(cls.stop_url) as response:
                res = await response.json()
                all_stop_data = res["data"]

                stop_data = []

                for stop in all_stop_data:
                    if stop["name_en"] == stop_name_en:

                        try:
                            stop_obj = BusStop(
                                id=stop["stop"],
                                name=stop["name_en"],
                                latitude=float(stop["lat"]),
                                longitude=float(stop["long"]),
                            )
                            stop_data.append(stop_obj)
                        except (KeyError, ValueError):
                            pass

                return stop_data


async def main():
    stop_data = await BusKMB.get_stop_info("REGAL RIVERSIDE HOTEL")
    kmb = BusKMB(stop_data)
    await kmb.get_eta("86C", "CHEUNG SHA WAN")


if __name__ == "__main__":
    asyncio.run(main())
