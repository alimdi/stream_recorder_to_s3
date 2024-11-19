"""Config flow for Camera Stream to S3 integration."""

from __future__ import annotations

import json
import logging
from typing import Any

import boto3
import voluptuous as vol
from botocore.exceptions import EndpointConnectionError, NoCredentialsError
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("aws_access_key"): str,
        vol.Required("aws_secret_key"): str,
        vol.Required("aws_region"): str,
        vol.Required("bucket_name"): str,
        vol.Required("streams"): TextSelector(
            TextSelectorConfig(multiline=True, type=TextSelectorType.TEXT)
        ),
    }
)


def raise_error(
    exception_class: type[Exception], message: str, cause: Exception | None = None
) -> None:
    """Raise an exception with optional cause."""
    if cause:
        raise exception_class(message) from cause
    raise exception_class(message)


def validate_bucket_sync(
    aws_access_key: str,
    aws_secret_key: str,
    aws_region: str,
    bucket_name: str,
) -> None:
    """Validate the S3 bucket connection."""
    session = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region,
    )
    try:
        session.head_bucket(Bucket=bucket_name)
        _LOGGER.info("AWS bucket connection validated")
    except NoCredentialsError as err:
        raise_error(InvalidAuth, "Invalid AWS credentials", err)
    except EndpointConnectionError as err:
        raise_error(CannotConnect, "Failed to connect to AWS S3 endpoint", err)
    except Exception as err:
        _LOGGER.exception("Unexpected exception during S3 validation")
        raise_error(CannotConnect, "AWS S3 operation failed", err)


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect to AWS S3 and test the stream URL."""

    # Validate AWS credentials
    aws_access_key = data["aws_access_key"]
    aws_secret_key = data["aws_secret_key"]
    aws_region = data["aws_region"]
    bucket_name = data["bucket_name"]
    _LOGGER.info(data["streams"])
    try:
        streams = json.loads(data["streams"])
    except Exception as e:
        _LOGGER.exception("Streams json not valid")
        raise_error(InvalidStreamURL, "Invalid json for streams.", e)

    # Validate the bucket connection
    await hass.async_add_executor_job(
        validate_bucket_sync, aws_access_key, aws_secret_key, aws_region, bucket_name
    )

    # Validate streams
    for stream in streams:
        url: str = stream.get("url")
        if not url.startswith("rtsp://") and not url.startswith("rtmp://"):
            raise_error(
                InvalidStreamURL,
                "The stream URL is invalid. It should be either RTSP or RTMP.",
            )
    _LOGGER.info("URL format valid")
    return {"title": DOMAIN}


class StremRecorderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Camera Stream to S3."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidStreamURL:
                errors["base"] = "invalid_stream_url"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to AWS or validate the stream URL."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid AWS authentication."""


class InvalidStreamURL(HomeAssistantError):
    """Error to indicate the stream URL is invalid."""
