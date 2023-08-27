# Face Scan Server

Files for three-component server application to send messages to and receive messages from the face scanning AiFace device.

## Description
To facilitate bi-directional communication with the face scanning device, a WebSocket application, a Flask application, and a Redis data store were implemented. The WebSocket application handles communication with the device, the Flask application handles external HTTP requests, and the Redis data store facilitates in-memory data transfer between the two applications. Optionally, a Microsoft SQL (MSSQL) database can be specified, which will insert activity records (e.g., scanning a face on device) into the database.

## Installation
Docker allows for easy installation. A Docker Compose YAML file and Dockerfiles are provided in the repository.

1. Clone the repository.

```bash
git clone https://github.com/fongc123/face.git
```

2. Create a `.env` file, which contains the applications' configuration settings, in the main directory. A sample environment file is provided (`sample.env`).

3. Use Docker Compose to build and run the applications.

```bash
cd face
docker-compose up
```

4. Ensure that the AiFace device is connected to the same network as the server and points to the server's IP address. If successful, a log indicating that the device has successfully registered with the server should appear.

## Usage
Upon starting Docker Compose, both the WebSocket and Flask applications *should* begin listening for WebSocket and HTTP requests. When a user interacts with the device (e.g., scans their face), the AiFace device will send a `sendlog` message to the WebSocket, which will be displayed in the server terminal.

The `/admin/push` endpoint is open to issue JSON commands to the device. By default, the Flask port is set to 5000, as specified in the sample `.env` file. A Bearer authorization key is also required. At the moment, it is simply set to an environment variable with no encryption or renewal. The example below demonstrates how to list all users currently registered in the AiFace device's system.

**Endpoint:** POST /admin/push (with Bearer authorization key)

```json
{
    "sn" : "ZXRB22001001",
    "cmd" : "getuserlist",
    "stn" : true
}
```

**NOTE:** All commands must have `sn` and `cmd` keys. Depending on the command, other key-value pairs may be required.
