import shutil
import subprocess
import threading
from collections import deque
from pathlib import Path
from datetime import datetime
from winapi import expect_keypress, parse_filename, create_handle, read_directory_changes, cleanup_handle

ffmpeg = shutil.which("ffmpeg")
SEGMENT_LIST = 'shadowpy-segment-list.m3u8'
CONCAT_FILE = "shadowpy-concat.ffconcat"

OUTPUT_DIR = "output"
OUTPUT_FILE = ""

KEY_ALT = 0x12
segment_time_secs = 8
replay_buffer_mins = 5
replay_buffer_secs = replay_buffer_mins * 60
buffer_segments = int(replay_buffer_secs / segment_time_secs)


class SegmentData:
    def __init__(self):
        self.segments = deque(maxlen=buffer_segments*2)
        self.duration = 0
        self.next_seg = 0
    
    def add(self, segment_file, duration):
        new_duration = self.duration + float(duration)
        # 1 added to balance it out
        if new_duration > replay_buffer_secs + segment_time_secs + 1:
            first_seg, first_dur = self.segments.popleft()
            new_duration = self.duration - float(first_dur)
            os.remove(f"{OUTPUT_DIR}/{first_seg}")
            
        self.segments.append((segment_file, duration))
        self.next_seg += 1
        self.duration = new_duration

segment_data = SegmentData()

ffmpeg_join = [
    ffmpeg,
    '-loglevel', 'quiet',
    '-f', 'concat',
    '-i',  f'{OUTPUT_DIR}/{CONCAT_FILE}',
    '-c', 'copy',
    f'{OUTPUT_DIR}/{OUTPUT_FILE}'
]

def setup_ffmpeg(audio_device, index):
    ffmpeg_segments = [
        ffmpeg, 
        '-loglevel', 'quiet',
        '-filter_complex', 'ddagrab=0,hwdownload,format=bgra', 
        '-f', 'dshow', 
        '-i', f'audio={audio_device}', #'audio=Stereo Mix (Realtek(R) Audio)', 
        '-vcodec', 'libx264', 
        '-pix_fmt', 'yuv420p', 
        '-preset', 'ultrafast',

        # Segment Options
        '-f', 'segment',
        '-segment_start_number', str(index),
        '-segment_time', str(segment_time_secs),
        '-segment_wrap', str(buffer_segments),
        '-segment_list',  f'{OUTPUT_DIR}/{SEGMENT_LIST}',
        '-segment_list_size', str(buffer_segments),
        f'{OUTPUT_DIR}/shadowpy-seg%d.ts'
    ]
    return ffmpeg_segments


# Get Audio Devices
def get_audio_devices():
    audio_devices = []
    ffmpeg_list_devices = ["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
    output = subprocess.run(ffmpeg_list_devices, capture_output=True).stderr
    output = str(output).split("\\r\\n")
    for l in output:
        line = l.split("] ")
        if len(line) <= 1: 
            continue
        line = line[1].strip()
        if line.endswith("(audio)"):
            audio_devices.append(line.split('"')[1])
    
    return audio_devices

def parse_m3u8(lines, offset=0):
    segment_file = lines[-1 - offset].strip()
    duration = lines[-2 - offset].strip().split(":")[1][0:-1]
    return segment_file, duration
    

def record_stream(ffmpeg_segments):
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    ffmpeg_process = subprocess.Popen(ffmpeg_segments, stdin=subprocess.PIPE)
    # Saves with ALT + S
    expect_keypress(KEY_ALT, ord('S'))

    print("Saving")
    ffmpeg_process.communicate(str.encode("q"))
    ffmpeg_process.wait()

    print("Merging Streams...")
    output_file = f"output-{datetime.now().strftime("%Y-%m-%d-%Hh%Mm%Ss")}.mp4"
    ffmpeg_join[-1] = f"{OUTPUT_DIR}/{output_file}"
    
    with open(f"output/{SEGMENT_LIST}", "r") as f:
        lines = f.readlines()
        segment_data.add(*parse_m3u8(lines, offset=1))
    
    with open(f"{OUTPUT_DIR}/{CONCAT_FILE}", "w") as f:
        for seg, _ in segment_data.segments:
            f.write(f"file '{seg}'\n")
        
    ffmpeg_process = subprocess.Popen(ffmpeg_join)
    ffmpeg_process.wait()
    print(f"Saved output to: {output_file}")


def watch_output_dir():
    handle = create_handle(OUTPUT_DIR)
    while True:
        info = read_directory_changes(handle)
        if not info:
            cleanup_handle(handle)
            print("Exiting...")
            _thread.interrupt_main()

        if parse_filename(info) == f"{SEGMENT_LIST}.tmp":
           print("Found Segment list!")
           print(segment_data.segments)
           try:
               with open(f"output/{SEGMENT_LIST}", "r") as f:
                    lines = f.readlines()
                    # set a offset from end if the m3u8 file has finished being saved
                    offset = 1 if lines[-1].startswith("#EXT-X-ENDLIST") else 0
                    segment_data.add(*parse_m3u8(lines, offset))
                    
           except PermissionError:
                continue
    
    cleanup_handle(handle)

def record(audio_device):
    # TODO: quit program on certain keypress
    watch_thread = threading.Thread(target=watch_output_dir)
    watch_thread.start()
    while True:
        ffmpeg_segments = setup_ffmpeg(audio_device, segment_data.next_seg)
        print("Capturing Screen (Press ALT+S to save recording, ALT+Q to quit)")
        record_stream(ffmpeg_segments)
    watch_thread.join()


if __name__ == "__main__":
    audio_devices = get_audio_devices();
    for i, audio in enumerate(audio_devices, start=1):
        print(f"[{i}] {audio}")

    n = int(input(f"Choose audio device to capture [1-{len(audio_devices)}] >> "))
    audio_device = audio_devices[n - 1]
    print(f"Using {audio_device} to capture audio stream")
    record(audio_device)
    

