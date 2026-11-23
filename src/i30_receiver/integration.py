"""Projection presentation and button routing through an OEM-owned host interface."""

from typing import Protocol


# Names supplied by a host adapter after decoding supported, non-vehicle-control inputs.
BUTTONS = {
    'HOME': 'HOME', 'BACK': 'BACK', 'MENU': 'MENU', 'NAV': 'NAVIGATION',
    'MEDIA': 'MEDIA', 'SEEK_NEXT': 'MEDIA_NEXT', 'SEEK_PREVIOUS': 'MEDIA_PREVIOUS',
    'PLAY_PAUSE': 'MEDIA_PLAY_PAUSE', 'VOICE': 'SEARCH',
}


class StockUi(Protocol):
    def show_projection(self) -> bool: ...
    def restore_stock(self) -> None: ...
    def stock_button(self, button: str, down: bool, longpress: bool) -> None: ...


class ProjectionHost:
    """Foreground arbitration for adapters driven from the receiver's I/O thread."""

    def __init__(self, ui: StockUi):
        self.ui = ui
        self.session = None
        self.requested = True
        self.blockers = set()
        self.visible = False
        self.presses = {}

    @property
    def available(self):
        return self.requested and not self.blockers

    def attach(self, session):
        self.session = session

    def detach(self):
        self.session = None
        self.hide()

    def show(self):
        if not self.visible and self.available:
            self.visible = self.ui.show_projection()
        return self.visible

    def hide(self):
        for button, owner in self.presses.items():
            if owner == 'projection':
                self.presses[button] = 'released'
        if self.visible:
            self.visible = False
            self.ui.restore_stock()

    def select(self, projection):
        self.requested = projection
        self.update()

    def preempt(self, reason, active):
        if active:
            self.blockers.add(reason)
        else:
            self.blockers.discard(reason)
        self.update()

    def update(self):
        if not self.available:
            try:
                self.hide()
            finally:
                if self.session is not None:
                    self.session.revoke_projection()

    def button(self, button, down, longpress=False):
        if button not in BUTTONS:
            self.ui.stock_button(button, down, longpress)
            return
        if down and button not in self.presses:
            in_projection = self.visible and self.session is not None and self.session.key(
                BUTTONS[button], True, longpress)
            self.presses[button] = 'projection' if in_projection else 'stock'
            if in_projection:
                return
        elif button in self.presses:
            owner = self.presses[button] if down else self.presses.pop(button)
            if owner != 'stock':
                if owner == 'projection' and self.session is not None:
                    self.session.key(BUTTONS[button], down, longpress)
                return
        self.ui.stock_button(button, down, longpress)
