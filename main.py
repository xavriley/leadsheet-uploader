import sys
import json
import music21
import numpy as np
import os
import sys
from pathlib import Path
from harte.harte import Harte

import soundsliceapi
from soundsliceapi import Constants
import csv

from time import sleep
from urllib.parse import urlparse, parse_qs


def get_yt_id(url):
    # Parse the URL
    parsed_url = urlparse(url)

    # Check if it's an embed URL and extract the video ID
    if "embed" in parsed_url.path:
        video_id = parsed_url.path.split("/")[-1]
    else:
        video_id = parse_qs(parsed_url.query)["v"][0]

    return video_id


def write_music_xml(filename, output_path):
    section_output = dict()

    data = json.load(open(filename))
    bar_length = int(data["time"].split(" ")[0])
    for label, chords in data["sections"].items():
        chord_output = []
        for bar in chords:
            for chord in bar:
                chord_output.append(
                    [Harte(chord["value"]), bar_length * (1 / int(chord["duration"]))]
                )
        section_output[label] = chord_output

    form_output = []
    for label in data["form"]:
        form_output.extend(section_output[label])

    s = music21.stream.Stream()
    p = music21.stream.Part()

    for chord, duration in chord_output:
        root = chord.get_root()

        p.append(
            music21.harmony.ChordSymbol(
                music21.harmony.chordSymbolFigureFromChord(chord)
            )
        )
        p.append(music21.note.Rest(duration=music21.duration.Duration(duration)))

    s.append(p)
    s.write(fp=output_path)


def main(filename, yt_url, artist, song_title, syncpoints_path):
    input_path = str(Path(filename))
    output_path = str.replace(input_path, ".json", "-chords.xml")
    write_music_xml(input_path, output_path)

    sys.exit(0)

    app_id = os.getenv("SOUNDSLICE_APP_ID")
    secret = os.getenv("SOUNDSLICE_SECRET")

    client = soundsliceapi.Client(app_id=app_id, password=secret)

    # create Pending folder on soundslice if not exist
    all_folders = client.list_folders()

    for f in all_folders:
        if f["name"] == "PiJAMA-Pending":
            folder = f
            break

    if len(all_folders) == 0:
        folder = client.create_folder("PiJAMA-Pending")

    new_slice = client.create_slice(
        name=f"{artist} - {song_title}", has_shareable_url=True, folder_id=folder["id"]
    )

    sleep(1)  # soundslice API has conservative rate limits

    client.create_recording(
        scorehash=new_slice["scorehash"],
        source=Constants.SOURCE_YOUTUBE,
        source_data=get_yt_id(yt_url),
    )

    sleep(1)

    client.upload_slice_notation(
        scorehash=new_slice["scorehash"], fp=open(output_path, "rb"),
    )

    sleep(1)

    scorehash = new_slice["scorehash"]

    if slice["recording_count"] == 0:
        # Example of uploading a recording from an MP3 file.
        #
        # recording_response = client.create_recording(
        #     # Required scorehash.
        #     scorehash=scorehash,
        #     source=Constants.SOURCE_MP3_UPLOAD,
        #     filename=str(audio_path)
        # )

        # ready = False
        # while not ready:
        #     recordings = client.get_slice_recordings(scorehash)
        #     if len(recordings) == 0:
        #         sleep(1)
        #     else:
        #         recording_id = recordings[0]['id']
        #         ready = True
        print("No recording found")
        sys.exit(1)
    else:
        recordings = client.get_slice_recordings(scorehash)
        recording_id = recordings[0]["id"]

    if recordings[0]["syncpoint_count"] == 0:
        client.put_recording_syncpoints(
            # Required.
            recording_id=recording_id,
            # Required. See syncpoint data format link above.
            syncpoints=open(syncpoints_path, "r").read(),
        )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        yt_url = sys.argv[2]
        artist = sys.argv[3]
        song_title = sys.argv[4]
        syncpoints_path = sys.argv[5]
        print(f"Filename: {filename}")
    else:
        filename = "test/leadsheet.json"
        yt_url = ""
        artist = ""
        song_title = ""
        syncpoints_path = "test/syncpoints.json"

    main(filename, yt_url, artist, song_title, syncpoints_path)
