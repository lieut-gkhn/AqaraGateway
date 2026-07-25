"""Runtime entry data for Aqara stored in hass.data."""
from dataclasses import dataclass, fields
from typing import Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send


@dataclass
class DeviceInfo:
    host: str = ''
    name: str = ''
    mac_address: str = ''
    model: str = ''
    version: str = ''
    cloud: str = ''


@dataclass
class RuntimeEntryData:
    """Store runtime data for aqara gateway config entries."""

    entry_id: str
    device_info: DeviceInfo | None = None

    @callback
    def async_update_entity(
        self, hass: HomeAssistant, component_key: str, key: int
    ) -> None:
        """Schedule the update of an entity."""
        signal = f"aqaragateway_{self.entry_id}_update_{component_key}_{key}"
        async_dispatcher_send(hass, signal)

    @callback
    def async_remove_entity(
        self, hass: HomeAssistant, component_key: str, key: int
    ) -> None:
        """Schedule the removal of an entity."""
        signal = f"aqaragateway_{self.entry_id}_remove_{component_key}_{key}"
        async_dispatcher_send(hass, signal)


def _attr_obj_from_dict(cls, **kwargs):
    return cls(
        **{field.name: kwargs[field.name] for field in fields(cls) if field.name in kwargs})
