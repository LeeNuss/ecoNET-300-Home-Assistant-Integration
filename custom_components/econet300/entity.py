"""Base econet entity class."""

import logging

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Econet300Api
from .common import EconetDataCoordinator
from .const import (
    DEVICE_INFO_CONTROLLER_NAME,
    DEVICE_INFO_ECOSTER_NAME,
    DEVICE_INFO_LAMBDA_NAME,
    DEVICE_INFO_MANUFACTURER,
    DEVICE_INFO_MIXER_NAME,
    DEVICE_INFO_MODEL,
    DOMAIN,
    EDIT_PARAMS_DATA_SENSOR_MAP,
    INFORMATION_PARAMS_SENSOR_MAP,
)

_LOGGER = logging.getLogger(__name__)


class EconetEntity(CoordinatorEntity):
    """Represents EconetEntity."""

    api: Econet300Api
    entity_description: EntityDescription

    def __init__(self, coordinator: EconetDataCoordinator, api: Econet300Api):
        """Initialize the EconetEntity."""
        super().__init__(coordinator)
        self.api = api

    @property
    def has_entity_name(self):
        """Return if the name of the entity is describing only the entity itself."""
        return True

    @property
    def unique_id(self) -> str | None:
        """Return the unique_id of the entity."""
        return f"{self.api.uid}-{self.entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info of the entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.api.uid)},
            name=DEVICE_INFO_CONTROLLER_NAME,
            manufacturer=DEVICE_INFO_MANUFACTURER,
            model=DEVICE_INFO_MODEL,
            model_id=self.api.model_id,
            configuration_url=self.api.host,
            sw_version=self.api.sw_rev,
            hw_version=self.api.hw_ver,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Update EconetEntity, entity name: %s", self.entity_description.name
        )

        # Safety check: ensure coordinator data exists
        if self.coordinator.data is None:
            _LOGGER.info("Coordinator data is None, skipping update")
            return

        # Debug: Check what's available in each data source
        sys_params = self.coordinator.data.get("sysParams", {})
        reg_params = self.coordinator.data.get("regParams", {})
        params_edits = self.coordinator.data.get("paramsEdits", {})
        edit_params = self.coordinator.data.get("editParams", {})
        information_params = self.coordinator.data.get("informationParams", {})

        # Safety check: ensure all data sources are always dicts
        if sys_params is None:
            sys_params = {}
            _LOGGER.info("sysParams was None, defaulting to empty dict")
        if reg_params is None:
            reg_params = {}
            _LOGGER.info("regParams was None, defaulting to empty dict")
        if params_edits is None:
            params_edits = {}
            _LOGGER.info("paramsEdits was None, defaulting to empty dict")
        if edit_params is None:
            edit_params = {}
            _LOGGER.info("editParams was None, defaulting to empty dict")
        if information_params is None:
            information_params = {}
            _LOGGER.info("informationParams was None, defaulting to empty dict")

        # For informationParams and editParams sensors, map friendly name to parameter ID
        # and determine which data source to use
        lookup_key = self.entity_description.key
        data_source = None  # Track which data source this sensor should use

        if lookup_key in INFORMATION_PARAMS_SENSOR_MAP:
            lookup_key = INFORMATION_PARAMS_SENSOR_MAP[lookup_key]
            data_source = "informationParams"
            _LOGGER.info(
                "Mapped sensor name '%s' to informationParams ID '%s'. informationParams has %d items, contains key: %s",
                self.entity_description.key,
                lookup_key,
                len(information_params),
                lookup_key in information_params
            )
        elif lookup_key in EDIT_PARAMS_DATA_SENSOR_MAP:
            lookup_key = EDIT_PARAMS_DATA_SENSOR_MAP[lookup_key]
            data_source = "editParams"
            _LOGGER.info(
                "Mapped sensor name '%s' to editParams data ID '%s'. editParams has %d items, contains key: %s",
                self.entity_description.key,
                lookup_key,
                len(edit_params),
                lookup_key in edit_params
            )

        _LOGGER.debug(
            "DEBUG: Looking for key '%s' (lookup_key: '%s') in data sources - sysParams: %s, regParams: %s, paramsEdits: %s, editParams: %s, informationParams: %s, forced source: %s",
            self.entity_description.key,
            lookup_key,
            lookup_key in sys_params,
            lookup_key in reg_params,
            lookup_key in params_edits,
            lookup_key in edit_params,
            lookup_key in information_params,
            data_source,
        )

        value = None

        # If sensor is explicitly mapped to informationParams, ONLY check there
        if data_source == "informationParams":
            if lookup_key in information_params:
                info_data = information_params[lookup_key]
                if (
                    isinstance(info_data, list)
                    and len(info_data) > 1
                    and isinstance(info_data[1], list)
                    and len(info_data[1]) > 0
                ):
                    value = info_data[1][0][0]  # Extract actual value
                    _LOGGER.debug(
                        "DEBUG: Found in informationParams: %s (extracted from %s)",
                        value,
                        info_data,
                    )
                else:
                    _LOGGER.warning(
                        "Unexpected informationParams structure for key %s: %s",
                        self.entity_description.key,
                        info_data,
                    )
        # If sensor is explicitly mapped to editParams, ONLY check there
        elif data_source == "editParams":
            if lookup_key in edit_params:
                edit_data = edit_params[lookup_key]
                if isinstance(edit_data, dict) and "value" in edit_data:
                    value = edit_data["value"]
                    _LOGGER.debug(
                        "DEBUG: Found in editParams: %s (extracted from %s)",
                        value,
                        edit_data,
                    )
                else:
                    value = edit_data
                    _LOGGER.debug("DEBUG: Found in editParams: %s", value)
        # Otherwise, check all sources in priority order
        else:
            if lookup_key in sys_params:
                value = sys_params[lookup_key]
                _LOGGER.debug("DEBUG: Found in sysParams: %s", value)
            elif lookup_key in reg_params:
                value = reg_params[lookup_key]
                _LOGGER.debug("DEBUG: Found in regParams: %s", value)
            elif lookup_key in params_edits:
                value = params_edits[lookup_key]
                _LOGGER.debug("DEBUG: Found in paramsEdits: %s", value)
            elif lookup_key in edit_params:
                # editParams has dict structure with 'value' key
                edit_data = edit_params[lookup_key]
                if isinstance(edit_data, dict) and "value" in edit_data:
                    value = edit_data["value"]
                    _LOGGER.debug(
                        "DEBUG: Found in editParams: %s (extracted from %s)",
                        value,
                        edit_data,
                    )
                else:
                    value = edit_data
                    _LOGGER.debug("DEBUG: Found in editParams: %s", value)
            elif lookup_key in information_params:
                # informationParams has structure: [editable_flag, [[value, unit, type]]]
                info_data = information_params[lookup_key]
                if (
                    isinstance(info_data, list)
                    and len(info_data) > 1
                    and isinstance(info_data[1], list)
                    and len(info_data[1]) > 0
                ):
                    value = info_data[1][0][0]  # Extract actual value
                    _LOGGER.debug(
                        "DEBUG: Found in informationParams: %s (extracted from %s)",
                        value,
                        info_data,
                    )
                else:
                    _LOGGER.warning(
                        "Unexpected informationParams structure for key %s: %s",
                        self.entity_description.key,
                        info_data,
                    )

        if value is None:
            _LOGGER.debug("Value for key %s is None", self.entity_description.key)
            return

        _LOGGER.debug(
            "Updating state for key: %s with value: %s",
            self.entity_description.key,
            value,
        )
        # Call _sync_state to update entity state
        self._sync_state(value)

    async def async_added_to_hass(self):
        """Handle added to hass."""
        _LOGGER.debug("Entering async_added_to_hass method")
        _LOGGER.debug("Added to HASS: %s", self.entity_description)
        _LOGGER.debug("Coordinator: %s", self.coordinator)

        # Check if the coordinator has a 'data' attributes
        if "data" not in dir(self.coordinator):
            _LOGGER.error("Coordinator object does not have a 'data' attribute")
            return

        # Safety check: ensure coordinator data exists
        if self.coordinator.data is None:
            _LOGGER.info("Coordinator data is None, skipping setup")
            return

        # Retrieve all data sources
        sys_params = self.coordinator.data.get("sysParams", {})
        reg_params = self.coordinator.data.get("regParams", {})
        params_edits = self.coordinator.data.get("paramsEdits", {})
        edit_params = self.coordinator.data.get("editParams", {})
        information_params = self.coordinator.data.get("informationParams", {})

        # Safety check: ensure all data sources are always dicts
        if sys_params is None:
            sys_params = {}
        if reg_params is None:
            reg_params = {}
        if params_edits is None:
            params_edits = {}
        if edit_params is None:
            edit_params = {}
        if information_params is None:
            information_params = {}

        # For informationParams and editParams sensors, map friendly name to parameter ID
        # and determine which data source to use
        lookup_key = self.entity_description.key
        data_source = None  # Track which data source this sensor should use

        if lookup_key in INFORMATION_PARAMS_SENSOR_MAP:
            lookup_key = INFORMATION_PARAMS_SENSOR_MAP[lookup_key]
            data_source = "informationParams"
            _LOGGER.debug(
                "async_added_to_hass: Mapped sensor name '%s' to informationParams ID '%s'",
                self.entity_description.key,
                lookup_key,
            )
        elif lookup_key in EDIT_PARAMS_DATA_SENSOR_MAP:
            lookup_key = EDIT_PARAMS_DATA_SENSOR_MAP[lookup_key]
            data_source = "editParams"
            _LOGGER.debug(
                "async_added_to_hass: Mapped sensor name '%s' to editParams data ID '%s'",
                self.entity_description.key,
                lookup_key,
            )

        # Retrieve the value from the appropriate data source
        value = None

        # If sensor is explicitly mapped to informationParams, ONLY check there
        if data_source == "informationParams":
            if lookup_key in information_params:
                info_data = information_params[lookup_key]
                if (
                    isinstance(info_data, list)
                    and len(info_data) > 1
                    and isinstance(info_data[1], list)
                    and len(info_data[1]) > 0
                ):
                    value = info_data[1][0][0]  # Extract actual value
                    _LOGGER.debug(
                        "async_added_to_hass: Found in informationParams: %s (extracted from %s)",
                        value,
                        info_data,
                    )
                else:
                    _LOGGER.warning(
                        "async_added_to_hass: Unexpected informationParams structure for key %s: %s",
                        self.entity_description.key,
                        info_data,
                    )
        # If sensor is explicitly mapped to editParams, ONLY check there
        elif data_source == "editParams":
            if lookup_key in edit_params:
                edit_data = edit_params[lookup_key]
                if isinstance(edit_data, dict) and "value" in edit_data:
                    value = edit_data["value"]
                    _LOGGER.debug(
                        "async_added_to_hass: Found in editParams: %s (extracted from %s)",
                        value,
                        edit_data,
                    )
                else:
                    value = edit_data
                    _LOGGER.debug("async_added_to_hass: Found in editParams: %s", value)
        # Otherwise, check all sources in priority order
        else:
            if lookup_key in sys_params:
                value = sys_params[lookup_key]
                _LOGGER.debug("async_added_to_hass: Found in sysParams: %s", value)
            elif lookup_key in reg_params:
                value = reg_params[lookup_key]
                _LOGGER.debug("async_added_to_hass: Found in regParams: %s", value)
            elif lookup_key in params_edits:
                value = params_edits[lookup_key]
                _LOGGER.debug("async_added_to_hass: Found in paramsEdits: %s", value)

        if value is None:
            _LOGGER.debug(
                "async_added_to_hass: Value for key %s (lookup_key: %s) is None",
                self.entity_description.key,
                lookup_key,
            )
            return

        # Synchronize with HASS
        await super().async_added_to_hass()
        # Call _sync_state to update entity state
        self._sync_state(value)

    def _sync_state(self, value) -> None:
        """Update entity state with the provided value.

        This method is called when the coordinator provides new data.
        Child classes should override this to handle entity-specific state updates.
        """
        # Base implementation does nothing - child classes handle state updates


class MixerEntity(EconetEntity):
    """Represents MixerEntity."""

    def __init__(
        self,
        description: EntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        idx: int,
    ):
        """Initialize the MixerEntity."""
        self.entity_description = description
        self.api = api
        self._idx = idx
        super().__init__(coordinator, api)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info of the entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.api.uid}-mixer-{self._idx}")},
            name=f"{DEVICE_INFO_MIXER_NAME}{self._idx}",
            manufacturer=DEVICE_INFO_MANUFACTURER,
            model=DEVICE_INFO_MODEL,
            model_id=self.api.model_id,
            configuration_url=self.api.host,
            sw_version=self.api.sw_rev,
            via_device=(DOMAIN, self.api.uid),
        )


class LambdaEntity(EconetEntity):
    """Initialize the LambdaEntity."""

    def __init__(
        self,
        description: EntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
    ):
        """Initialize the LambdaEntity."""
        self.entity_description = description
        self.api = api
        super().__init__(coordinator, api)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info of the entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.api.uid}lambda")},
            name=f"{DEVICE_INFO_LAMBDA_NAME}",
            manufacturer=DEVICE_INFO_MANUFACTURER,
            model=DEVICE_INFO_MODEL,
            configuration_url=self.api.host,
            sw_version=self.api.sw_rev,
            via_device=(DOMAIN, self.api.uid),
        )


class EcoSterEntity(EconetEntity):
    """Represents EcoSterEntity."""

    def __init__(
        self,
        description: EntityDescription,
        coordinator: EconetDataCoordinator,
        api: Econet300Api,
        idx: int,
    ):
        """Initialize the EcoSterEntity."""
        self.entity_description = description
        self.api = api
        self._idx = idx
        super().__init__(coordinator, api)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info of the entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.api.uid}-ecoster-{self._idx}")},
            name=f"{DEVICE_INFO_ECOSTER_NAME} {self._idx}",
            manufacturer=DEVICE_INFO_MANUFACTURER,
            model=DEVICE_INFO_MODEL,
            model_id=self.api.model_id,
            configuration_url=self.api.host,
            sw_version=self.api.sw_rev,
            via_device=(DOMAIN, self.api.uid),
        )
