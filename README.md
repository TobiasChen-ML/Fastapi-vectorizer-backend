# FastAPI Vectorizer Backend

A lightweight, production-ready backend that turns user-uploaded raster images into scalable SVG vectors inside a WeChat Service Account.

## Features
- **WeChat server validation & image reception**
- **On-the-fly PNG/JPG → SVG conversion** (via Potrace or your own engine)
- **Cloud storage upload** (Tencent COS) and signed-url delivery
- **JSAPI payment flow** for “per-image credits”
- **Real-time quota management** after successful payments

## Overview
Deploy once, and users can chat an image to your service, pay for credits, and receive a download link to the generated SVG—all within the 48-hour WeChat message window.


## Usage
