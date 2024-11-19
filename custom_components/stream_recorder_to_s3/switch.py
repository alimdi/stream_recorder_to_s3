"""Module handles camera stream recording and storage to an AWS S3 bucket."""

import asyncio
import io
import json
import logging
import subprocess
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, STREAM_LENGTH

_LOGGER = logging.getLogger(__name__)


class SwitchRecordCameraEntity(SwitchEntity):
    """Entity representing a switch for camera stream."""

    def __init__(
        self,
        stream_name: str,
        stream_url: str,
        aws_access_key: str,
        aws_secret_key: str,
        aws_region: str,
        bucket_name: str,
    ) -> None:
        """Initialize entity configuration."""
        self._attr_has_entity_name = True
        self._attr_unique_id = f"record_{stream_name}"
        self._attr_name = self._attr_unique_id

        self.stream_url = stream_url
        self.stream_name = stream_name
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.aws_region = aws_region
        self.bucket_name = bucket_name
        self._attr_is_on = False

        self.ffmpeg_command = (
            f"ffmpeg -hide_banner -y -loglevel error -rtsp_transport tcp -t {STREAM_LENGTH} "
            f"-use_wallclock_as_timestamps 1 -i {self.stream_url} -vcodec copy "
            "-acodec copy -f mp4 -movflags frag_keyframe+empty_moov pipe:1"
        )
        _LOGGER.info("SwitchRecordCameraEntity created: %s", self._attr_unique_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start recording and set the switch state to on."""
        if not self._attr_is_on:
            _LOGGER.info("Starting recording for %s", self._attr_name)
            await self.start_stream_to_s3()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop recording and set the switch state to off."""
        self.stop_stream_to_s3()

    def upload_to_s3_sync(self):
        """Stream capture and S3 upload."""
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=self.aws_region,
        )
        while self._attr_is_on:
            now = datetime.now()
            output_key = (
                now.strftime("%Y/%m/%d/%Y%m%d%H%M%S_") + f"{self.stream_name}.mp4"
            )

            response = s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=output_key,
                ContentType="video/mp4",
            )
            upload_id = response["UploadId"]
            parts = []
            part_number = 1

            try:
                with subprocess.Popen(
                    self.ffmpeg_command.split(" "),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=False,
                ) as process:
                    _LOGGER.debug("FFmpeg process started for %s", self.stream_name)

                    with io.BytesIO() as buffer:
                        while self._attr_is_on:
                            chunk = process.stdout.read(1024 * 1024)
                            if not chunk:
                                break
                            buffer.write(chunk)

                            if buffer.tell() > 5 * 1024 * 1024:
                                buffer.seek(0)
                                part_response = s3_client.upload_part(
                                    Bucket=self.bucket_name,
                                    Key=output_key,
                                    PartNumber=part_number,
                                    UploadId=upload_id,
                                    Body=buffer,
                                )
                                parts.append(
                                    {
                                        "PartNumber": part_number,
                                        "ETag": part_response["ETag"],
                                    }
                                )
                                buffer.seek(0)
                                buffer.truncate(0)
                                part_number += 1

                        if buffer.tell() > 0:
                            buffer.seek(0)
                            part_response = s3_client.upload_part(
                                Bucket=self.bucket_name,
                                Key=output_key,
                                PartNumber=part_number,
                                UploadId=upload_id,
                                Body=buffer,
                            )
                            parts.append(
                                {
                                    "PartNumber": part_number,
                                    "ETag": part_response["ETag"],
                                }
                            )

                    s3_client.complete_multipart_upload(
                        Bucket=self.bucket_name,
                        Key=output_key,
                        UploadId=upload_id,
                        MultipartUpload={"Parts": parts},
                    )
                    _LOGGER.info("Completed upload to S3 for %s", self.stream_name)

            except (ClientError, BotoCoreError) as e:
                _LOGGER.error("S3 upload error: %s", e)
                s3_client.abort_multipart_upload(
                    Bucket=self.bucket_name, Key=output_key, UploadId=upload_id
                )
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                _LOGGER.error("Unexpected error during reading stream: %s", e)
                self.stop_stream_to_s3()
            finally:
                process.terminate()
                process.wait()
                _LOGGER.debug("FFmpeg process terminated for %s", self.stream_name)

    async def start_stream_to_s3(self):
        """Start recording stream and uploading to S3."""
        if not self._attr_is_on:
            self._attr_is_on = True
            self.schedule_update_ha_state()
            try:
                await self.hass.async_add_executor_job(self.upload_to_s3_sync)
            except (ClientError, BotoCoreError) as boto_error:
                _LOGGER.error("Boto3 error during stream-to-S3: %s", boto_error)
            except subprocess.SubprocessError as subprocess_error:
                _LOGGER.error("Error in FFmpeg subprocess: %s", subprocess_error)
            except OSError as io_error:
                _LOGGER.error("I/O error during upload: %s", io_error)
            except RuntimeError as runtime_error:
                _LOGGER.error("Runtime error during stream-to-S3: %s", runtime_error)
            except asyncio.CancelledError:
                _LOGGER.warning("Streaming task was cancelled")
            finally:
                self.stop_stream_to_s3()

    def stop_stream_to_s3(self):
        """Stop the recording."""
        if self._attr_is_on:
            _LOGGER.info("Stopping recording for %s", self.stream_name)
            self._attr_is_on = False
            self.schedule_update_ha_state()
        else:
            _LOGGER.info("Stream already stopped for %s", self.stream_name)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the camera stream recorder from a config entry."""
    _LOGGER.info("Setting up Stream Recorder integration")

    config = entry.data
    aws_access_key = config["aws_access_key"]
    aws_secret_key = config["aws_secret_key"]
    aws_region = config["aws_region"]
    bucket_name = config["bucket_name"]
    streams = json.loads(config["streams"])

    entities = [
        SwitchRecordCameraEntity(
            stream_name=stream["name"],
            stream_url=stream["url"],
            aws_access_key=aws_access_key,
            aws_secret_key=aws_secret_key,
            aws_region=aws_region,
            bucket_name=bucket_name,
        )
        for stream in streams
    ]
    async_add_entities(entities, update_before_add=True)
    hass.data[DOMAIN][entry.entry_id]["entities"] = entities
