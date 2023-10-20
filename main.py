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

import csv
from io import StringIO


def get_alignment_data(csv_path, beats_per_bar):
    csv_reader = csv.reader(StringIO(Path(csv_path).read_text()))
    _ = next(csv_reader)

    max_beat = max(int(row[1]) for row in csv_reader)
    total_bars = (max_beat // beats_per_bar) + 1

    csv_reader = csv.reader(StringIO(Path(csv_path).read_text()))
    next(csv_reader)  # skip header

    syncpoints_output = []
    for row in csv_reader:
        beat_time, beat_number = float(row[0]), int(row[1])

        bar = beat_number // beats_per_bar
        beat_in_bar = beat_number % beats_per_bar

        if beat_in_bar == 0:
            syncpoints_output.append([bar, beat_time])

    return syncpoints_output


def get_yt_id(url):
    # Parse the URL
    parsed_url = urlparse(url)

    # Check if it's an embed URL and extract the video ID
    if "embed" in parsed_url.path:
        video_id = parsed_url.path.split("/")[-1]
    else:
        video_id = parse_qs(parsed_url.query)["v"][0]

    return video_id


def write_music_xml(filename, bar_indexes, output_path):
    section_output = dict()

    data = json.load(open(filename))
    bar_length = int(data["time"].split(" ")[0])
    for label, chords in data["sections"].items():
        chord_output = []
        for bar in chords:
            bar_output = []
            for chord in bar:
                bar_output.append(
                    [Harte(chord["value"]), bar_length * (1 / int(chord["duration"]))]
                )
            chord_output.append(bar_output)
        section_output[label] = chord_output

    form_output = []
    for label in data["form"]:
        form_output.extend(section_output[label])

    piece_output = []
    for bar_index in bar_indexes:
        piece_output.extend(form_output[bar_index])

    s = music21.stream.Stream()
    p = music21.stream.Part()

    for chord, duration in piece_output:
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
    syncpoint_output_path = str.replace(input_path, ".json", "-syncpoints.json")

    # get beats per bar
    beats_per_bar = int(json.load(open(filename))["time"].split(" ")[0])

    alignment_data = get_alignment_data(syncpoints_path, beats_per_bar)
    bar_indexes = [row[0] for row in alignment_data]

    write_music_xml(input_path, bar_indexes, output_path)

    syncpoints = [
        [bar_idx, sync_time] for bar_idx, (_, sync_time) in enumerate(alignment_data)
    ]
    Path(syncpoint_output_path).write_text(json.dumps(list(syncpoints)))

    app_id = os.getenv("SOUNDSLICE_APP_ID")
    secret = os.getenv("SOUNDSLICE_SECRET")

    client = soundsliceapi.Client(app_id=app_id, password=secret)

    # create Pending folder on soundslice if not exist
    all_folders = client.list_folders()

    folder = None
    for f in all_folders:
        if f["name"] == "PiJAMA-Pending":
            folder = f
            break

    if not folder:
        folder = client.create_folder("PiJAMA-Pending")

    new_slice = client.create_slice(
        name=song_title, artist=artist, has_shareable_url=True, folder_id=folder["id"]
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
    # load full slice data
    new_slice = client.get_slice(scorehash)

    if new_slice["recording_count"] == 0:
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
            syncpoints=open(syncpoint_output_path, "r").read(),
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
        filename = "test/0002_Embraceable_You/leadsheet.json"
        yt_url = "https://www.youtube.com/watch?v=xAmuQIKiwms"
        artist = "Art Tatum"
        song_title = "Embraceable You"
        syncpoints_path = "test/0002_Embraceable_You/alignment.csv"

    main(filename, yt_url, artist, song_title, syncpoints_path)
