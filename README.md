

# Stream Recorder to AWS S3 for Home Assistant
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](LICENSE)

Home Assistant integration to record camera streams to AWS S3.

## Features
- Network streams : rtsp, rtmp, etc.
- Turn on and off each recorder switch

## 🚀 Quick Start

### 📦 Using HACS (Recommended)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alimdi&repository=stream_recorder_to_s3&category=integration)

1. Add this repository to HACS:
   - Manually: `https://github.com/alimdi/stream_recorder_to_s3` (category: `integration`)
   - Or use the button above
2. Search for "Camera Stream to S3" in HACS and install
3. Restart Home Assistant

### ⚙️ Manual Installation
1. Download the `custom_components/stream_recorder_to_s3` directory to your Home Assistant configuration directory
2. Restart Home Assistant

## 🔧 Setup
[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=stream_recorder)

1. Go to the Integrations page in Home Assistant
2. Click "Add Integration" and search for "Camera Stream to S3"
3. Enter AWS credentials and a list of streams :
    [
        {
            "name": "cam1",
            "url": "rtsp://user:password@ip1:port"
        },
        {
            "name": "cam2",
            "url": "rtsp://user:password@ip1:port"
        }
    ]
4. Integration will be ready within a few seconds

## ❓ Troubleshooting

If you encounter any issues:
1. Verify AWS credentials
2. Double-check that the streams URLs are correct
3. Check Home Assistant logs for any error details


## 🤝 Contributing

Contributions are welcome! Feel free to:
- 🐛 Report bugs
- 💡 Suggest improvements
- 🔀 Submit pull requests

## 📄 License

This project is licensed under the Apache License. See the [LICENSE](LICENSE) file for details.

---

If you find this integration helpful, please consider giving it a ⭐️ on GitHub!