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
    NUMBER_MAP_KEY,
    SELECT_MAP_KEY,
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

    def _get_value(
        self,
    ):
        # Safety check: ensure coordinator data exists
        if self.coordinator.data is None:
            _LOGGER.info("Coordinator data is None")
            return None

        # Debug: Check what's available in each data source
        sys_params = self.coordinator.data.get("sysParams", {})
        reg_params = self.coordinator.data.get("regParams", {})
        params_edits = self.coordinator.data.get("paramsEdits", {})
        edit_params = self.coordinator.data.get("editParams", {})
        information_params = self.coordinator.data.get("informationParams", {})

        entity_key = self.entity_description.key

        _LOGGER.debug(
            "Looking for parameter ID '%s' in data sources - sysParams: %s, regParams: %s, paramsEdits: %s, editParams: %s, informationParams: %s",
            entity_key,
            entity_key in sys_params,
            entity_key in reg_params,
            entity_key in params_edits,
            entity_key in edit_params,
            entity_key in information_params,
        )

        value = None

        controller_id = sys_params.get("controllerID", "")
        number_key = NUMBER_MAP_KEY.get(controller_id, NUMBER_MAP_KEY["_default"]).get(
            entity_key
        )
        select_key = SELECT_MAP_KEY.get(controller_id, SELECT_MAP_KEY["_default"]).get(
            entity_key
        )
        if select_key:
            select_key = select_key[0]
        edit_params_key = EDIT_PARAMS_DATA_SENSOR_MAP.get(entity_key)
        inform_params_key = INFORMATION_PARAMS_SENSOR_MAP.get(entity_key)

        # Check all sources in priority order
        if entity_key in sys_params:
            value = sys_params[entity_key]
            _LOGGER.debug("Found in sysParams: %s", value)
        elif entity_key in reg_params:
            value = reg_params[entity_key]
            _LOGGER.debug("Found in regParams: %s", value)
        elif entity_key in params_edits:
            value = params_edits[entity_key]
            _LOGGER.debug("Found in paramsEdits: %s", value)
        elif number_key in edit_params or select_key in edit_params:
            data_key = number_key if number_key else select_key
            value = edit_params[data_key]
            _LOGGER.debug(
                "Found in editParams (NUMBER entity, passing full dict): %s", value
            )
        elif edit_params_key in edit_params:
            edit_data = edit_params[edit_params_key]
            if isinstance(edit_data, dict) and "value" in edit_data:
                value = edit_data["value"]  # Extract value for sensors
                _LOGGER.debug(
                    "Found in editParams via EDIT_PARAMS_DATA_SENSOR_MAP (sensor, extracting value): %s from %s",
                    value,
                    edit_data,
                )
            else:
                value = edit_data
                _LOGGER.debug(
                    "Found in editParams via EDIT_PARAMS_DATA_SENSOR_MAP (direct value): %s",
                    value,
                )
        elif inform_params_key in information_params:
            _LOGGER.debug(
                "Found in informationParams via INFORMATION_PARAMS_SENSOR_MAP (sensor %s -> param %s)",
                entity_key,
                inform_params_key,
            )
            # informationParams has structure: [editable_flag, [[value, unit, type]]]
            info_data = information_params[inform_params_key]
            value = info_data[1][0][0]  # Extract actual value
            _LOGGER.debug(
                "Found in informationParams (extracting value): %s from %s",
                value,
                info_data,
            )

        if value is None:
            _LOGGER.debug("Value for key %s is None", self.entity_description.key)
        else:
            _LOGGER.debug(
                "Updating state for key: %s with value: %s",
                self.entity_description.key,
                value,
            )

        return value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Update EconetEntity, entity name: %s", self.entity_description.name
        )

        value = self._get_value()

        # Call _sync_state to update entity state
        self._sync_state(value)

    async def async_added_to_hass(self):
        """Handle added to hass."""
        _LOGGER.debug("Entering async_added_to_hass method")
        _LOGGER.debug("Added to HASS: %s", self.entity_description)
        _LOGGER.debug("Coordinator: %s", self.coordinator)

        value = self._get_value()

        if value is None:
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
