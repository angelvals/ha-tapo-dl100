"""Shared base for the lock and battery entities.

Without a device, Home Assistant shows the lock and its battery as two loose
entities with no device page, no model or firmware, and no icon in the
integration list. Both entities inherit from this class so they register
under one device built from the lock's own getDeviceInfo reply.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Dl100Coordinator


class Dl100Entity(CoordinatorEntity[Dl100Coordinator]):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator: Dl100Coordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = _device_info(entry, coordinator)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


def _device_info(entry: ConfigEntry, coordinator: Dl100Coordinator) -> DeviceInfo:
    # The cloud deviceId is stable across IP changes and reinstalls. It is
    # resolved during the first refresh, which runs before entities are added;
    # the entry id is only a fallback if that ever changes.
    raw = coordinator.data.raw if coordinator.data is not None else {}
    info = DeviceInfo(
        identifiers={(DOMAIN, coordinator.api.device_id or entry.entry_id)},
        manufacturer="TP-Link",
        model=str(raw.get("model") or "DL-series lock"),
        name=entry.data[CONF_NAME],
    )
    if raw.get("fw_ver"):
        info["sw_version"] = str(raw["fw_ver"])
    if raw.get("hw_ver"):
        info["hw_version"] = str(raw["hw_ver"])
    if raw.get("mac"):
        info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(str(raw["mac"])))}
    if coordinator.api.device_id:
        info["serial_number"] = coordinator.api.device_id
    return info
