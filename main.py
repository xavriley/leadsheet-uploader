import sys
import json
import music21
import numpy as np
import os
import sys
from pathlib import Path
from harte.harte import Harte

def write_music_xml(filename, output_path):
    chord_output = []

    data = json.load(open(filename))
    bar_length = int(data["time"].split(" ")[0])
    for label, chords in data["sections"].items():
        for bar in chords:
            for chord in bar:
                chord_output.append([Harte(chord["value"]), bar_length * (1/int(chord["duration"]))])
    
    s = music21.stream.Stream()
    p = music21.stream.Part()

    for chord, duration in chord_output:
        root = chord.get_root()

        p.append(music21.harmony.ChordSymbol(music21.harmony.chordSymbolFigureFromChord(chord)))
        p.append(music21.note.Rest(duration=music21.duration.Duration(duration)))
    
    s.append(p)
    s.write(fp=output_path)

def main(filename):
    input_path = str(Path(filename))
    output_path = str.replace(input_path, '.json', '-chords.xml')
    write_music_xml(input_path, output_path)
        

if __name__=='__main__':
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        print(f'Filename: {filename}')
    else:
        filename = 'test/leadsheet.json'
        # print('No filename provided')
        # sys.exit(1)
    
    main(filename)