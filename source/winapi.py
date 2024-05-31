import ctypes
from ctypes import wintypes

CreateFileW = ctypes.windll.kernel32.CreateFileW
ReadDirectoryChangesW = ctypes.windll.kernel32.ReadDirectoryChangesW

FILE_SHARE_DELETE = 0x00000004
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
OPEN_EXISTING = 0x3
FILE_LIST_DIRECTORY = 0x1
FILE_NOTIFY_CHANGE_LAST_WRITE = 0x00000010

CreateFileW.restype = wintypes.HANDLE
CreateFileW.argtypes = (
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
)

ReadDirectoryChangesW.restype = wintypes.BOOL
ReadDirectoryChangesW.argtypes = (
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.BOOL,
    wintypes.DWORD,
    wintypes.LPDWORD,
    # ignored optional parameters
    wintypes.LPVOID, 
    wintypes.LPVOID,
)

def create_handle(directory_path):
    handle = CreateFileW(
        directory_path,    FILE_LIST_DIRECTORY, 
        FILE_SHARE_DELETE | FILE_SHARE_READ | FILE_SHARE_WRITE, 
        0, 
        OPEN_EXISTING, 
        FILE_FLAG_BACKUP_SEMANTICS, 
        0
    )
    print("Created handle: ", handle)
    return handle

# _FILE_NOTIFY_INFORMATION from winapi 
class FileNotifyInformation(ctypes.Structure):
    _fields_ = [("NextEntryOffset", wintypes.DWORD), 
    ("Action", wintypes.DWORD), 
    ("FileNameLength", wintypes.DWORD), 
    ("FileName", wintypes.WCHAR * 1)] 

def read_directory_changes(directory_handle):
    BUFFER_SIZE = 1024
    file_info_buffer = ctypes.create_unicode_buffer(BUFFER_SIZE)
    bytes_returned = wintypes.DWORD()

    success = ReadDirectoryChangesW(
        directory_handle, 
        file_info_buffer, 
        len(file_info_buffer), 
        wintypes.BOOL(False), 
        FILE_NOTIFY_CHANGE_LAST_WRITE,
        ctypes.byref(bytes_returned), 
        None, 
        None
    )

    if not success:
        print("Error: Reading Directory Failed")
        return None

    print(f"Received file info of {bytes_returned.value} bytes")
    return FileNotifyInformation.from_buffer(file_info_buffer, 0)


def parse_filename(file_notify_info):
    data = file_notify_info
    filename_offset = getattr(FileNotifyInformation,"FileName").offset
    while True:
        filename_address = ctypes.cast(ctypes.addressof(data) + filename_offset, ctypes.POINTER(wintypes.WCHAR))
        filename = ctypes.wstring_at(filename_address, data.FileNameLength // 2)
        yield filename

        if not data.NextEntryOffset:
            return
        data = ctypes.cast(ctypes.addressof(data) + data.NextEntryOffset, ctype.POINTER(FileNotifyInformation))

def cleanup_handle(handle):
    if not ctypes.windll.kernel32.CloseHandle(handle):
        print("Error Closing Handle")
    else:
        print("Closed Handle Successfully")

# Checks whether modifier and key are both pressed
def expect_keypress(modifier, key): 
    GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState
    while True:
        keystate_modif = GetAsyncKeyState(modifier) & 0x8000
        keystate_key = GetAsyncKeyState(key) & 0x8000
        if keystate_modif and keystate_key:
            return

if __name__ == "__main__":
    handle = create_handle('.\\output')
    info = read_directory_changes(handle)
    if info:
        for i in parse_filename(info):
            print(i)
    cleanup_handle(handle)