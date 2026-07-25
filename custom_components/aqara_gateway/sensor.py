"""Support for Xiaomi Aqara sensors."""
import re
from homeassistant.helpers.event import async_track_time_interval

from datetime import timedelta
from typing import Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_VOLTAGE,
    STATE_PROBLEM,
    EntityCategory,
)
from homeassistant.util.dt import now

from . import DOMAIN, GatewayGenericDevice
from .core.const import (
    APPROACHING_DISTANCE,
    ATTR_APPROACHING_DISTANCE,
    ATTR_CHIP_TEMPERATURE,
    ATTR_DETECTING_REGION,
    ATTR_EXITS_ENTRANCES_REGION,
    ATTR_FW_VER,
    ATTR_INTERFERENCE_REGION,
    ATTR_LATCH_STATUS,
    ATTR_LI_BATTERY,
    ATTR_LI_BATTERY_TEMP,
    ATTR_LOCK_STATUS,
    ATTR_LQI,
    ATTR_MONITORING_MODE,
    ATTR_NOTIFICATION,
    ATTR_REVERTED_MODE,
    BACK_VERSION,
    BATTERY,
    CHIP_TEMPERATURE,
    DETECTING_REGION,
    EXITS_ENTRANCES_REGION,
    ICONS,
    INTERFERENCE_REGION,
    LATCH_STATUS,
    LATCH_STATUS_TYPE,
    LI_BATTERY,
    LI_BATTERY_TEMP,
    LOAD_POWER,
    LOCK_STATE,
    LOCK_STATUS_TYPE,
    LQI,
    MONITORING_MODE,
    POWER,
    REVERTED_MODE,
    UNITS,
    VOLTAGE,
)
from .core.gateway import Gateway
from .core.lock_data import (
    DEVICE_MAPPINGS,
    LOCK_NOTIFICATION,
    SUPPORT_ALARM,
    SUPPORT_CAMERA,
    SUPPORT_DOORBELL,
    SUPPORT_WIFI,
    WITH_LI_BATTERY,
)
from .core.utils import CLUSTERS, Utils


async def async_setup_entry(hass, entry, async_add_entities):
    """ setup config entry """
    def setup(gateway: Gateway, device: dict, attr: str):
        if attr == 'gateway':
            async_add_entities([GatewayStats(gateway, device, attr)])
        elif attr == 'zigbee':
            async_add_entities([ZigbeeStats(gateway, device, attr)])
        elif attr == 'last_seen':
            async_add_entities([GatewayLastSeenSensor(gateway, device, attr)])
        elif attr == 'gas density':
            async_add_entities([GatewayGasSensor(gateway, device, attr)])
        elif attr == 'lock':
            async_add_entities([GatewayLockSensor(gateway, device, attr)])
        elif attr == 'key_id':
            async_add_entities([GatewayKeyIDSensor(gateway, device, attr)])
        elif attr == 'lock_event':
            async_add_entities([GatewayLockEventSensor(gateway, device, attr)])
        elif attr in ('hear_rate', 'breath_rate', 'body_movements'):
            async_add_entities([GatewaySleepMonitorSensor(gateway, device, attr)])
        elif attr == 'illuminance':
            if (device['type'] == 'gateway' and
                    Utils.gateway_illuminance_supported(device['model'])) or device['type'] == 'zigbee':
                async_add_entities([GatewaySensor(gateway, device, attr)])
        elif attr == 'movements':
            async_add_entities([GatewayMoveSensor(gateway, device, attr)])
        elif attr == 'occupancy_region':
            async_add_entities([GatewayOccupancyRegionSensor(gateway, device, attr)])
        
        elif attr == "wifi_ip":
            async_add_entities([GatewaySystemSensor(gateway, device, attr)])
        elif attr == "temperature":
            async_add_entities([GatewaySystemSensor(gateway, device, attr)])
        elif attr == "volume":
            async_add_entities([GatewaySystemSensor(gateway, device, attr)])
        #elif attr in (
        #    "wifi_ip",
        #    "temperature",
        #    "radio_channel",
        #    "network_pan_id",
        #    "radio_tx_power",
        #    "rssi",
        #):
        #    async_add_entities(
        #        [GatewaySystemSensor(gateway, device, attr)]
        #    )
        else:
            async_add_entities([GatewaySensor(gateway, device, attr)])

    aqara_gateway: Gateway = hass.data[DOMAIN][entry.entry_id]
    aqara_gateway.add_setup('sensor', setup)

    gateway_device = next(
        (
            dev
            for dev in aqara_gateway.devices.values()
            if dev["type"] == "gateway"
        ),
        None,
    )

    if gateway_device:
        async_add_entities(
            [
                GatewaySystemSensor(
                    aqara_gateway,
                    gateway_device,
                    "wifi_ip",
                ),
                GatewaySystemSensor(
                    aqara_gateway,
                    gateway_device,
                    "temperature",
                ),
                GatewaySystemSensor(
                    aqara_gateway,
                    gateway_device,
                    "volume",
                ),
            ],
            True,
        )


async def async_unload_entry(hass, entry):
    # pylint: disable=unused-argument
    """ unload entry """
    return True


class GatewaySensor(GatewayGenericDevice, SensorEntity):
    """ Xiaomi/Aqara Sensors """

    def __init__(
        self,
        gateway,
        device,
        attr,
    ):
        """Initialize the Xiaomi/Aqara Sensors."""
        self._state = False
        self.is_metric = False
        self.with_attr = bool(device['type'] not in (
            'gateway', 'zigbee')) and bool(attr not in (
                'key_id', 'battery', 'power', 'consumption'))

        if self.with_attr:
            self._battery = None
            self._chip_temperature = None
            self._lqi = None
            self._voltage = None

        if attr == 'consumption':
            self._attr_state_class = 'total_increasing'
        elif attr in UNITS:
            self._attr_state_class = 'measurement'

        super().__init__(gateway, device, attr)

    @property
    def state(self):
        """return state."""
        return self._state

    @property
    def device_class(self):
        """return device class."""
        if "consumption" == self._attr:
            return "energy"
        return self._attr

    @property
    def unit_of_measurement(self):
        """return unit."""
        return UNITS.get(self._attr)

    @property
    def icon(self):
        """return icon."""
        return ICONS.get(self._attr)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.with_attr:
            attrs = {
                ATTR_BATTERY_LEVEL: self._battery,
                ATTR_LQI: self._lqi,
                ATTR_VOLTAGE: self._voltage,
                ATTR_CHIP_TEMPERATURE: self._chip_temperature,
            }
            return attrs
        return None

    def update(self, data: dict = None):
        """update sensor."""
        for key, value in data.items():
            if self.with_attr:
                if key == BATTERY:
                    self._battery = value
                if key == CHIP_TEMPERATURE:
                    if self.is_metric:
                        self._chip_temperature = format(
                            (int(value) - 32) * 5 / 9, '.2f') if isinstance(
                            value, (int, float)) else None
                    else:
                        self._chip_temperature = value
                if key == LQI:
                    self._lqi = value
                if key == VOLTAGE:
                    self._voltage = format(
                        float(value) / 1000, '.3f') if isinstance(
                        value, (int, float)) else None
            if self._attr == POWER and LOAD_POWER in data:
                self._state = data[LOAD_POWER]
            if self._attr == key:
                self._state = value
        self.async_write_ha_state()


class GatewayLastSeenSensor(GatewaySensor):
    """Last seen timestamp for Aqara devices."""
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, gateway, device, attr):
        """Initialize the last seen sensor."""
        super().__init__(gateway, device, attr)
        self._state = None

    @property
    def device_class(self):
        """return device class."""
        # don't use const to support older Hass version
        return 'timestamp'

    @property
    def available(self):
        """return available."""
        return True

    @property
    def icon(self):
        """return icon."""
        return 'mdi:clock-outline'

    def update(self, data: dict = None):
        """update last seen timestamp."""
        self._state = now().isoformat(timespec='seconds')
        self.async_write_ha_state()


class GatewayGasSensor(GatewaySensor):
    """ Xiaomi/Aqara Gas sensor """
    def update(self, data: dict = None):
        """update sensor."""
        if 'gas' in data:
            self._state = data['gas']
        self.async_write_ha_state()


class GatewayStats(GatewaySensor):
    """ Aqara Gateway status """
    _state = None

    def __init__(self, gateway, device, attr):
        """Initialize the gateway stats sensor."""
        super().__init__(gateway, device, attr)
        self._attrs = {}

    @property
    def device_class(self):
        """return device class."""
        # don't use const to support older Hass version
        return 'timestamp'

    @property
    def available(self):
        """return available."""
        return True

    async def async_added_to_hass(self):
        """add to hass."""
        self.gateway.add_update('lumi.0', self.update)
        self.gateway.add_stats('lumi.0', self.update)
        # update available when added to Hass
        self.update()

    async def async_will_remove_from_hass(self) -> None:
        """remove from hass."""
        self.gateway.remove_update('lumi.0', self.update)
        self.gateway.remove_stats('lumi.0', self.update)

    def update(self, data: dict = None):
        """update gateway stats."""
        # empty data - update state to available time
        if not data:
            self._state = now().isoformat(timespec='seconds') \
                if self.gateway.available else None
        else:
            self._attrs.update(data)

        self.async_write_ha_state()


class ZigbeeStats(GatewaySensor):
    """ Aqara Gateway Zigbee status """
    last_seq1 = None
    last_seq2 = None
    _attrs: dict
    _state = None

    def __init__(self, gateway, device, attr):
        """Initialize the zigbee stats sensor."""
        super().__init__(gateway, device, attr)
        self._attrs = {}

    @property
    def device_class(self):
        """device class."""
        # don't use const to support older Hass version
        return 'timestamp'

    @property
    def available(self):
        """return available."""
        return True

    async def async_added_to_hass(self):
        """add to hass."""
        if not self._attrs:
            ieee = '0x' + self.device['did'][5:].rjust(16, '0').upper()
            self._attrs = {
                'ieee': ieee,
                'nwk': None,
                'msg_received': 0,
                'msg_missed': 0,
                'unresponsive': 0,
                'last_missed': 0,
            }

        self.gateway.add_stats(self._attrs['ieee'], self.update)

    async def async_will_remove_from_hass(self) -> None:
        """remove from hass."""
        self.gateway.remove_stats(self._attrs['ieee'], self.update)

    def update(self, data: dict = None):
        """update zigbee states."""
        if 'sourceAddress' in data:
            self._attrs['nwk'] = data['sourceAddress']
            self._attrs['link_quality'] = data['linkQuality']
            self._attrs['rssi'] = data['rssi']

            cid = int(data['clusterId'], 0)
            self._attrs['last_msg'] = cluster = CLUSTERS.get(cid, cid)

            self._attrs['msg_received'] += 1

            # For some devices better works APSCounter, for other - sequence
            # number in payload. Sometimes broken messages arrived.
            try:
                new_seq1 = int(data['APSCounter'], 0)
                raw = data['APSPlayload']
                manufact_spec = int(raw[2:4], 16) & 4
                new_seq2 = int(raw[8:10] if manufact_spec else raw[4:6], 16)
                last_seq1 = self.last_seq1
                last_seq2 = self.last_seq2
                if last_seq1 is not None and last_seq2 is not None:
                    miss = min(
                        (new_seq1 - last_seq1 - 1) & 0xFF,
                        (new_seq2 - last_seq2 - 1) & 0xFF
                    )
                    self._attrs['msg_missed'] += miss
                    self._attrs['last_missed'] = miss
                    if miss:
                        self.debug(
                            f"Msg missed: {last_seq1} => {new_seq1}, "
                            f"{last_seq2} => {new_seq2}, {cluster}"
                        )
                self.last_seq1 = new_seq1
                self.last_seq2 = new_seq2

            except:  # noqa: E722, S110
                pass

            self._state = now().isoformat(timespec='seconds')

        elif 'parent' in data:
            ago = timedelta(seconds=data.pop('ago'))
            self._state = (now() - ago).isoformat(timespec='seconds')
            self._attrs.update(data)

        elif data.get('deviceState') == 17:
            self._attrs['unresponsive'] += 1

        self.schedule_update_ha_state()


class GatewayLockSensor(GatewaySensor):
    # pylint: disable=too-many-instance-attributes
    """Representation of a Aqara Lock."""

    def __init__(self, gateway, device, attr):
        """Initialize the Aqara lock device."""
        super().__init__(gateway, device, attr)
        self._features = DEVICE_MAPPINGS[self.device['model']]
        self._battery = None
        self._fw_ver = None
        self._li_battery = None
        self._li_battery_temperature = None
        self._lqi = None
        self._voltage = None
        self._state = None
        self._notification = "Unknown"
        self._lock_status = None
        self._latch_status = None

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICONS.get(self._attr)

    @property
    def device_class(self):
        """Return the class of this device."""
        return "lock_state"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {
            ATTR_BATTERY_LEVEL: self._battery,
            ATTR_FW_VER: self._fw_ver,
            ATTR_LQI: self._lqi,
            ATTR_VOLTAGE: self._voltage,
            ATTR_LOCK_STATUS: self._lock_status,
            ATTR_LATCH_STATUS: self._latch_status,
            ATTR_NOTIFICATION: self._notification,
        }
        if self._features & WITH_LI_BATTERY:
            attrs[ATTR_LI_BATTERY] = self._li_battery
            attrs[ATTR_LI_BATTERY_TEMP] = self._li_battery_temperature
        return attrs

    def update(self, data: dict = None):
        """ update lock state """
        # handle available change
        for key, value in data.items():
            if key == BATTERY:
                self._battery = value
            if key == BACK_VERSION:
                self._fw_ver = value
            if key == LI_BATTERY:
                self._li_battery = value
            if key == LI_BATTERY_TEMP:
                self._li_battery_temperature = value / 10
            if key == LQI:
                self._lqi = value
            if key == VOLTAGE:
                self._voltage = format(
                    float(value) / 1000, '.3f') if isinstance(
                    value, (int, float)) else None
            if key == LATCH_STATUS:
                self._latch_status = LATCH_STATUS_TYPE.get(
                    str(value), str(value))
            if key in LOCK_NOTIFICATION:
                notify = LOCK_NOTIFICATION[key]
                self._notification = notify.get(
                    str(value), None) if notify.get(
                    str(value), None) else notify.get("default")
            if key == self._attr:
                self._state = LOCK_STATE.get(str(value), STATE_PROBLEM)
                self._lock_status = LOCK_STATUS_TYPE.get(
                    str(value), str(value))
        self.async_write_ha_state()


class GatewayKeyIDSensor(GatewaySensor):
    """Representation of a Aqara Lock Key ID."""

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICONS.get(self._attr)

    @property
    def device_class(self):
        """Return the class of this device."""
        return None

    def update(self, data: dict = None):
        """ update lock state """
        # handle available change
        for key, value in data.items():
            if (key == self._attr or "unlock by" in key):
                self._state = value
        self.async_write_ha_state()


class GatewayLockEventSensor(GatewaySensor):
    """Representation of a Aqara Lock Event."""

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICONS.get(self._attr)

    @property
    def device_class(self):
        """Return the class of this device."""
        return None

    def update(self, data: dict = None):
        """ update lock state """
        # handle available change
        for key, value in data.items():
            if key in LOCK_NOTIFICATION:
                notify = LOCK_NOTIFICATION[key]
                self._state = notify.get(str(value), None) if notify.get(
                    str(value), None) else notify.get("default")

        self.async_write_ha_state()


class GatewaySleepMonitorSensor(GatewaySensor):
    """Representation of a Aqara Sleep Monitor."""
    # pylint: disable=too-many-instance-attributes

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICONS.get(self._attr)

    @property
    def device_class(self):
        """Return the class of this device."""
        return None

    def update(self, data: dict = None):
        """ update sleep monitor state """
        # handle available change
        for key, value in data.items():
            if key == self._attr:
                self._state = value

        self.async_write_ha_state()


class GatewayMoveSensor(GatewaySensor):
    """Representation of a Aqara Moving Sensor."""
    # pylint: disable=too-many-instance-attributes

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICONS.get(self._attr)

    @property
    def device_class(self):
        """Return the class of this device."""
        return "moving"

    def update(self, data: dict = None):
        """ update move state """
        # handle available change
        for key, value in data.items():
            if key == self._attr:
                self._state = value

        if self._attr in data:
            self._state = data[self._attr]
            self.async_write_ha_state()

            # repeat event from Aqara integration
            self.hass.bus.async_fire('xiaomi_aqara.click', {
                'entity_id': self.entity_id, 'click_type': self._state
            })

        self.schedule_update_ha_state()


class GatewayOccupancyRegionSensor(GatewaySensor):
    """Representation of a Aqara Occupancy Region Sensor."""
    # pylint: disable=too-many-instance-attributes
    def __init__(self, gateway, device, attr):
        """Initialize the Aqara lock device."""
        super().__init__(gateway, device, attr)
        self._chip_temperature = None
        self._lqi = None
        self._state = None
        self._approaching_distance = None
        self._detecting_region = None
        self._exits_entrances_region = None
        self._interference_region = None
        self._monitoring_mode = None
        self._reverted_mode = None

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:square-opacity"

    @property
    def device_class(self):
        """Return the class of this device."""
        return "moving"

    def update(self, data: dict = None):
        """ update move state """
        # handle available change
        for key, value in data.items():
            if key == APPROACHING_DISTANCE:
                self._approaching_distance = value
            if key == DETECTING_REGION:
                self._detecting_region = value
            if key == EXITS_ENTRANCES_REGION:
                self._exits_entrances_region = value
            if key == INTERFERENCE_REGION:
                self._interference_region = value
            if key == MONITORING_MODE:
                self._monitoring_mode = value
            if key == REVERTED_MODE:
                self._reverted_mode = value
            if key == CHIP_TEMPERATURE:
                self._chip_temperature = value
            if key == LQI:
                self._lqi = value
            if key == self._attr:
                self._state = value

        if self._attr in data:
            self._state = data[self._attr]
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {
            ATTR_LQI: self._lqi,
            ATTR_CHIP_TEMPERATURE: self._chip_temperature,
            ATTR_APPROACHING_DISTANCE: self._approaching_distance,
            ATTR_DETECTING_REGION: self._detecting_region,
            ATTR_EXITS_ENTRANCES_REGION: self._exits_entrances_region,
            ATTR_INTERFERENCE_REGION: self._interference_region,
            ATTR_MONITORING_MODE: self._monitoring_mode,
            ATTR_REVERTED_MODE: self._reverted_mode
        }
        return attrs

class GatewaySystemSensor(SensorEntity):
    def __init__(self, gateway, device, attr):
        self.gateway = gateway
        self.device = device
        self.attr = attr

        self._attr_name = f"{device['model']} {attr}"
        self._attr_unique_id = f"{device['did']}_{attr}"

        self._attr_native_value = None
        self._attr_available = True

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._update,
                timedelta(seconds=60),
            )
        )

        await self._update(None)

    async def _update(self, _):

        shell = self.gateway._get_shell(
            Utils.get_device_name(
                self.gateway._model
            ).lower()
        )

        try:
            shell.login()

            if self.attr == "wifi_ip":
                raw = shell.run_command(
                    "ifconfig wlan0 | grep 'inet addr'"
                )

                m = re.search(
                    r"(?:\d{1,3}\.){3}\d{1,3}",
                    raw,
                )

                if m:
                    self._attr_native_value = m.group(0)

            elif self.attr == "temperature":

                raw = shell.run_command(
                    "getprop persist.sys.temperature"
                )

                self._attr_native_value = float(
                    raw.strip()
                )

            elif self.attr == "volume":

                raw = shell.run_command(
                    "getprop persist.sys.volume"
                )

                self._attr_native_value = int(
                    raw.strip()
                )

        except Exception:
            self._attr_available = False

        finally:
            try:
                shell.close()
            except Exception:
                pass

        self.async_write_ha_state()