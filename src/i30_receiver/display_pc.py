"""PC projection window and local stand-in for the stock UI."""

from collections import deque
import tkinter as tk
from tkinter import ttk

from .platform import DiagnosticSink
from .protocol import TOUCH_SIZE
from .video import H264Decoder, frame_ppm
from .wire import ProtocolError


KEYS = {
    'F1': 'HOME', 'Escape': 'BACK', 'F2': 'NAV', 'F3': 'MEDIA', 'F4': 'MENU',
    'F5': 'VOICE', 'F6': 'SEEK_NEXT', 'F7': 'SEEK_PREVIOUS', 'F8': 'PLAY_PAUSE',
}


class ProjectionWindow(DiagnosticSink):
    wants_projection = True

    def __init__(self, log, av, stop):
        super().__init__(log)
        self.av = av
        self.root = tk.Tk()
        self.root.title('i30 Android Auto · PC')
        self.root.resizable(False, False)
        self.root.protocol('WM_DELETE_WINDOW', stop)
        toolbar = ttk.Frame(self.root, padding=(8, 6))
        toolbar.pack(fill='x')
        ttk.Button(toolbar, text='Android Auto', command=lambda: self.queue('select', True)).pack(side='left')
        ttk.Button(toolbar, text='Stock UI', command=lambda: self.queue('select', False)).pack(side='left', padx=8)
        ttk.Label(toolbar, text='F2 Navigation    F3 Media    F5 Voice    F6 / F7 Track').pack(side='right')
        width, height = TOUCH_SIZE
        self.canvas = tk.Canvas(self.root, width=width, height=height, highlightthickness=0, background='#202329')
        self.canvas.pack()
        self.stock = self.canvas.create_text(width // 2, height // 2, text='Stock UI (PC simulation)', fill='white')
        self.image_item = self.canvas.create_image(0, 0, anchor='nw')
        self.decoder = self.frame = self.image = None
        self.host = None
        self.events = deque()
        for event, action in (('<ButtonPress-1>', 'ACTION_DOWN'), ('<B1-Motion>', 'ACTION_MOVED'),
                              ('<ButtonRelease-1>', 'ACTION_UP')):
            self.canvas.bind(event, lambda point, action=action: self.queue('pointer', action, point.x, point.y))
        self.keys_down = set()
        self.root.bind('<KeyPress>', lambda event: self.key(event.keysym, True))
        self.root.bind('<KeyRelease>', lambda event: self.key(event.keysym, False))
        self.root.bind('<FocusOut>', self.focus_lost)

    def queue(self, event, *data):
        if len(self.events) >= 256:
            self.events.clear()
            self.events.append(('reset',))
        self.events.append((event, *data))

    def key(self, name, down):
        if name in KEYS:
            repeat = name in self.keys_down
            if down:
                self.keys_down.add(name)
            else:
                self.keys_down.discard(name)
            self.queue('key', KEYS[name], down, repeat and down)

    def focus_lost(self, _):
        for name in tuple(self.keys_down):
            self.key(name, False)
        self.queue('reset')

    def poll(self):
        self.root.update()
        width, height = TOUCH_SIZE
        while self.events:
            event, *data = self.events.popleft()
            session = self.host.session
            if event == 'select':
                self.host.select(*data)
            elif event == 'key':
                self.host.button(*data)
            elif event == 'reset' and session:
                session.release_input()
            elif event == 'pointer' and session:
                action, x, y = data
                session.pointer(action, min(width - 1, max(0, x)), min(height - 1, max(0, y)))

    def show_projection(self):
        if self.frame is None:
            return False
        self.draw()
        self.canvas.itemconfigure(self.stock, state='hidden')
        return True

    def restore_stock(self):
        self.canvas.itemconfigure(self.stock, state='normal')
        self.canvas.itemconfigure(self.image_item, image='')
        self.image = None

    def stock_button(self, button, down, longpress):
        self.log('stock_button', button=button, down=down, longpress=longpress)

    def draw(self):
        self.image = tk.PhotoImage(data=frame_ppm(self.frame, *TOUCH_SIZE), format='PPM')
        self.canvas.itemconfigure(self.image_item, image=self.image)

    def channel(self, channel, kind, state):
        super().channel(channel, kind, state)
        if kind == 'video':
            if state == 'receiving':
                try:
                    self.decoder = H264Decoder(self.av)
                except (ValueError, self.av.FFmpegError) as exc:
                    raise ProtocolError(f'Could not initialize PC projection decoder: {exc}') from exc
            if state in ('open', 'closed'):
                self.decoder = self.frame = None

    def packet(self, channel, kind, timestamp, data):
        super().packet(channel, kind, timestamp, data)
        if kind == 'video' and self.decoder is not None:
            try:
                previous = self.frame
                for frame in self.decoder.push(data):
                    self.frame = frame
                if self.frame is not previous and self.host.visible:
                    self.draw()
            except (ValueError, tk.TclError, self.av.FFmpegError) as exc:
                raise ProtocolError(f'PC projection display failed: {exc}') from exc
