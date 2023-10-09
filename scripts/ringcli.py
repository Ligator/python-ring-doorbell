# vim:sw=4:ts=4:et
# Many thanks to @troopermax <https://github.com/troopermax>
"""Python Ring CLI."""
import os
import json
import getpass
import argparse
from datetime import datetime
from pathlib import Path
from oauthlib.oauth2 import MissingTokenError
from ring_doorbell import Ring, Auth


def _header():
    _bar()
    print("Ring CLI")


def _bar():
    print("---------------------------------")

cache_file = Path("ring_token.cache")

def token_updated(token):
    """Writes token to file"""
    cache_file.write_text(json.dumps(token), encoding="utf-8")


def _format_filename(event, directory):
    if not isinstance(event, dict):
        return None

    if event["answered"]:
        answered_status = "answered"
    else:
        answered_status = "_"

    filename = "{}_{}_{}_{}.mp4".format(
        event["created_at"].astimezone(None).strftime("%Y-%m-%d_%Hh%Mm%Ss_%Z"),
        event["kind"],
        answered_status,
        event["id"]
    )

    file_path ="{}_{}/{}/{}".format(
        event["doorbot"]["id"], event["doorbot"]["description"],
        event["created_at"].astimezone(None).year,
        event["created_at"].astimezone(None).strftime("%Y-%m")
    )

    if directory:
        file_path = directory + "/" + file_path

    os.makedirs(file_path, exist_ok=True)

    return file_path + "/" + filename


def cli():
    """Command line function."""
    parser = argparse.ArgumentParser(
        description="Ring Doorbell",
        epilog="https://github.com/tchellomello/python-ring-doorbell",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-u", "--username", dest="username", type=str, help="username for Ring account"
    )

    parser.add_argument(
        "-p", "--password", type=str, dest="password", help="username for Ring account"
    )

    parser.add_argument(
        "-d", "--directory", type=str, dest="directory", default="", help="directory to save the videos"
    )

    parser.add_argument(
        "-l", "--list", action="store_true", default=False, help="list of available devices"
    )

    parser.add_argument(
        "-did", "--device_id", type=str, dest="device_id", default="", help="device ID. You can get this from the listing"
    )

    parser.add_argument(
        "--count",
        action="store_true",
        default=False,
        help="count the number of videos on your Ring account",
    )

    parser.add_argument(
        "--download-all",
        action="store_true",
        default=False,
        help="download all videos on your Ring account",
    )

    args = parser.parse_args()
    _header()

    batch_size = 100

    # connect to Ring account
    if cache_file.is_file():
        auth = Auth(
            "RingCLI/0.6",
            json.loads(cache_file.read_text(encoding="utf-8")),
            token_updated,
        )
    else:
        if not args.username:
            args.username = input("Username: ")

        if not args.password:
            args.password = getpass.getpass("Password: ")

        auth = Auth("RingCLI/0.6", None, token_updated)
        try:
            auth.fetch_token(args.username, args.password)
        except MissingTokenError:
            auth.fetch_token(args.username, args.password, input("2FA Code: "))

    ring = Ring(auth)
    ring.update_data()
    devices = ring.devices()

    _bar()

    if args.list:
        for key in devices:
            devices_by_kind = devices[key]
            for device in devices_by_kind:
                print("[" + key + "]", "--device_id", device.device_id, "\t", device.name, device.address)
        return

    doorbell = ""

    if args.device_id:
        for key in devices:
            devices_by_kind = devices[key]
            for device in devices_by_kind:
                if (device.device_id == args.device_id):
                    doorbell = device
    else:
        for key in devices:
            devices_by_kind = devices[key]
            for device in devices_by_kind:
                doorbell = device

    if (doorbell == ""):
        print("Device", args.device_id, "not found")
        return

    if args.count:
        print(
            "\tCounting videos linked on your Ring account.\n"
            + "\tThis may take some time....\n"
        )

        events = []
        counter = 0
        history = doorbell.history(limit=100)
        while len(history) > 0:
            events += history
            counter += len(history)
            history = doorbell.history(older_than=history[-1]["id"])

        motion = len([m["kind"] for m in events if m["kind"] == "motion"])
        ding = len([m["kind"] for m in events if m["kind"] == "ding"])
        on_demand = len([m["kind"] for m in events if m["kind"] == "on_demand"])

        print("\tTotal videos: {}".format(counter))
        print("\tDing triggered: {}".format(ding))
        print("\tMotion triggered: {}".format(motion))
        print("\tOn-Demand triggered: {}".format(on_demand))

        # already have all events in memory
        if args.download_all:
            counter = 0
            print(
                "\tDownloading all videos linked on your Ring account.\n"
                + "\tThis may take some time....\n"
            )

            for event in events:
                counter += 1
                filename = _format_filename(event)
                print("\t{}/{} Downloading {}".format(counter, len(events), filename))

                doorbell.recording_download(
                    event["id"], filename=filename, override=False
                )

    if args.download_all and not args.count:
        print(
            "\tDownloading all videos linked on your Ring account.\n"
            + "\tThis may take some time....\n"
        )
        history = doorbell.history(limit=batch_size)

        while len(history) > 0:
            print(
                "\tProcessing and downloading the next "
                + format(len(history))
                + " videos"
            )

            counter = 0
            download_counter = 0
            for event in history:
                counter += 1
                filename = _format_filename(event, args.directory)
                filepath = Path(filename)
                if not filepath.is_file():
                    download_counter +=1
                    print("\t{}/{} Downloading {}".format(counter, len(history), filename))

                    try:
                        doorbell.recording_download(
                            event["id"], filename=filename, override=False
                        )
                        right_date = datetime.timestamp(event["created_at"])
                        os.utime(filename, (right_date, right_date))
                    except:
                        print("\t{}/{} Error {}".format(counter, len(history), filename))

            history = doorbell.history(limit=batch_size, older_than=history[-1]["id"])

        print("Downloaded videos: ", download_counter)
        print("Total videos: ", counter)

if __name__ == "__main__":
    cli()