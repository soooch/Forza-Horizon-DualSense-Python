"""System tab: extends SettingsTab with controller selection."""
import logging
import threading

import customtkinter as ctk

from fhds.lang import t
from fhds.modules.config import preferences
from fhds.modules.dualsense.main import _enumerate_dualsenses, _is_bluetooth, identify_pulse

from . import theme as T
from . import widgets as W
from .settings_tab import SYSTEM_SECTIONS, SettingsTab

log = logging.getLogger("fhds")


class SystemTab(SettingsTab):
    SECTIONS = SYSTEM_SECTIONS
    SHOW_RESET = False
    PAGE_TITLE = "System"
    PAGE_SUBTITLE = "Controller and app-level options."

    def __init__(self, parent, app):
        self._devices: list[dict] = []
        self._lock_var: ctk.StringVar | None = None
        self._radio_holder: "W.FastScroll | None" = None
        self._radio_buttons: list[ctk.CTkRadioButton] = []
        self._controller_card: "W.Card | None" = None
        self._dsx_note: "W.Hint | None" = None
        self._first_section = None
        super().__init__(parent, app)
        threading.Thread(target=self._enumerate_async, daemon=True).start()

    def _build(self):
        self._build_controller_card()
        self._build_dsx_note()
        # Standard sections from SYSTEM_SECTIONS; remember the first so the
        # controller card / DSX note stay above them after a re-pack.
        existing = list(self._scroll.winfo_children())
        super()._build()
        self._first_section = next(
            (c for c in self._scroll.winfo_children() if c not in existing), None)
        # Run after every card exists so the DSX/controller swap can reference them.
        self._sync_controller_visibility()

    # MARK: controller card -------------------------------------------------

    def _build_controller_card(self):
        card = self._controller_card = W.Card(self._scroll)
        card.pack(fill="x", pady=(0, T.PAD_MD))
        W.H2(card, t("Controller")).pack(anchor="w", padx=T.PAD_MD,
                                         pady=(T.PAD_MD, T.PAD_XS))
        W.Hint(card, t("Lock the app to a specific DualSense, or let it pick the first one.")
               ).pack(anchor="w", padx=T.PAD_MD, pady=(0, T.PAD_SM))

        self._lock_var = ctk.StringVar(value=self.settings.controller_lock_serial or "")
        self._radio_holder = W.FastScroll(card, height=140,
                                                    fg_color=T.BG_INPUT,
                                                    corner_radius=6)
        self._radio_holder.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))
        self._render_radio_buttons()

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
        W.SecondaryButton(actions, t("Rescan"), self._on_rescan, width=120
                          ).pack(side="left")

    def _build_dsx_note(self):
        # Shown in place of the controller card while DSX owns the controller.
        self._dsx_note = W.Hint(
            self._scroll,
            t("DSX is active - controller managed by DSX. "
              "Disable DSX to select a controller here."),
            wrap=self.app.px(640),
        )

    def _sync_controller_visibility(self):
        """Controller picking is meaningless while DSX owns the device, so swap the
        controller card for an explanatory note when DSX is on."""
        if self._controller_card is None or self._dsx_note is None:
            return
        if self.settings.use_dsx:
            self._controller_card.pack_forget()
            if self._first_section is not None:
                self._dsx_note.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD),
                                    before=self._first_section)
            else:
                self._dsx_note.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
        else:
            self._dsx_note.pack_forget()
            if self._first_section is not None:
                self._controller_card.pack(fill="x", pady=(0, T.PAD_MD),
                                           before=self._first_section)
            else:
                self._controller_card.pack(fill="x", pady=(0, T.PAD_MD))

    # MARK: controller list -------------------------------------------------

    def _attached_serial(self) -> str:
        ds = getattr(self.app, "_ds", None)
        if ds is None or not ds.connected:
            return ""
        return getattr(ds, "dev_serial", "") or ""

    def _render_radio_buttons(self):
        if self._radio_holder is None or self._lock_var is None:
            return
        for rb in self._radio_buttons:
            rb.destroy()
        self._radio_buttons.clear()
        attached = self._attached_serial()

        rb = ctk.CTkRadioButton(self._radio_holder, text=t("Auto (first found)"),
                                variable=self._lock_var, value="",
                                command=self._on_lock_changed)
        rb.pack(anchor="w", padx=T.PAD_SM, pady=2)
        self._radio_buttons.append(rb)

        for d in self._devices:
            sn = d.get("serial_number") or ""
            transport = "BT" if _is_bluetooth(d) else "USB"
            if sn:
                marker = f"  < {t('attached now')}" if sn == attached else ""
                rb = ctk.CTkRadioButton(self._radio_holder,
                                        text=f"[{transport}] {sn}{marker}",
                                        variable=self._lock_var, value=sn,
                                        command=self._on_lock_changed)
            else:
                rb = ctk.CTkRadioButton(self._radio_holder,
                                        text=f"[{transport}] {t('(no serial - not selectable)')}",
                                        variable=self._lock_var,
                                        value=f"__noserial_{id(d)}__",
                                        state="disabled")
            rb.pack(anchor="w", padx=T.PAD_SM, pady=2)
            self._radio_buttons.append(rb)

    def _on_rescan(self):
        threading.Thread(target=self._enumerate_async, daemon=True).start()

    def _enumerate_async(self):
        try:
            devs = _enumerate_dualsenses()
        except Exception:
            log.exception("controller enumeration failed")
            devs = []
        try:
            self.app.root.after(0, lambda: self._apply_devices(devs))
        except Exception:
            pass

    def _apply_devices(self, devices: list[dict]):
        self._devices = devices
        if self._lock_var is not None:
            self._lock_var.set(self.settings.controller_lock_serial or "")
        self._render_radio_buttons()

    def _on_lock_changed(self):
        if self._lock_var is None:
            return
        new = self._lock_var.get()
        if new.startswith("__noserial_"):
            return
        if new:
            info = next((d for d in self._devices
                         if (d.get("serial_number") or "") == new), None)
            if info is not None:
                threading.Thread(
                    target=identify_pulse, args=(info,),
                    kwargs={"force": self.settings.startup_pulse_force},
                    daemon=True,
                ).start()
        if self.settings.controller_lock_serial != new:
            self.settings.controller_lock_serial = new
            preferences.save(self.settings)
            log.info("controller_lock_serial = %r", new)
        ds = getattr(self.app, "_ds", None)
        if ds is not None:
            ds.set_selection(new)
            if new and new != self._attached_serial():
                ds.force_reconnect()
        threading.Thread(target=self._enumerate_async, daemon=True).start()

    # MARK: dsx visibility --------------------------------------------------

    def _on_switch(self, attr: str):
        super()._on_switch(attr)
        if attr == "use_dsx":
            self._sync_controller_visibility()

    def _refresh_widgets(self):
        super()._refresh_widgets()
        if self._lock_var is not None:
            self._lock_var.set(self.settings.controller_lock_serial or "")
            self._render_radio_buttons()
