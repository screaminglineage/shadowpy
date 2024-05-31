import shutil
import subprocess
import threading
from pathlib import Path
from winapi import expect_keypress, parse_filename, create_handle, read_directory_changes, cleanup_handle

ffmpeg = shutil.which("ffmpeg")
SEGMENT_LIST = 'shadowpy-segment-list.m3u8'

OUTPUT_DIR = "output"
OUTPUT_FILE = "output"

KEY_ALT = 0x12


ffmpeg_join = [
    ffmpeg,
    '-loglevel', 'quiet',
    '-i',  f'{OUTPUT_DIR}/{SEGMENT_LIST}',
    '-c', 'copy',
    f'{OUTPUT_DIR}/{OUTPUT_FILE}.mp4'
]

def setup_ffmpeg(audio_device):
    segment_time_secs = 34
    replay_buffer_mins = 5

    replay_buffer_secs = replay_buffer_mins * 60
    buffer_segments = int(replay_buffer_secs / segment_time_secs)

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

def record_stream(count, ffmpeg_segments):
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    ffmpeg_command = subprocess.Popen(ffmpeg_segments, stdin=subprocess.PIPE)
    # Saves with ALT + S
    expect_keypress(KEY_ALT, ord('S'))

    print("Saving")
    ffmpeg_command.communicate(str.encode("q"))
    ffmpeg_command.wait()

    print("Merging Streams...")
    if count > 0:
        ffmpeg_join[-1] = f"{OUTPUT_DIR}/{OUTPUT_FILE}_{count}.mp4"
    p = subprocess.Popen(ffmpeg_join)
    p.wait()
    print(f"Saved output to {ffmpeg_join[-1]}")


def watch_output_dir():
    handle = create_handle(OUTPUT_DIR)
    while True:
        info = read_directory_changes(handle)
        if not info:
            cleanup_handle(handle)
            print("Exiting...")
            _thread.interrupt_main()

        if f"{SEGMENT_LIST}.tmp" in list(parse_filename(info)):
           print("Found Segment list!")
    
    cleanup_handle(handle)

def record(ffmpeg_segments):
    # TODO: quit program on certain keypress
    watch_thread = threading.Thread(target=watch_output_dir)
    watch_thread.start()
    count = 0
    while True:
        print("Capturing Screen (Press ALT+S to save recording, ALT+Q to quit)")
        record_stream(count, ffmpeg_segments)
        count += 1
    watch_thread.join()


if __name__ == "__main__":
    audio_devices = get_audio_devices();
    for i, audio in enumerate(audio_devices, start=1):
        print(f"[{i}] {audio}")

    n = int(input(f"Choose audio device to capture [1-{len(audio_devices)}] >> "))
    audio_device = audio_devices[n - 1]
    print(f"Using {audio_device} to capture audio stream")
    ffmpeg_segments = setup_ffmpeg(audio_device)
    record(ffmpeg_segments)
    

