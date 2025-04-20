# PMO

A simple process management tool for Linux, similar to PM2, designed to simplify application deployment and management.

## Features

- Start, stop, and restart services defined in a `pmo.yml` configuration file
- View real-time logs with service name highlighting
- Automatic process supervision and PID management
- Environment variable support
- Simple YAML configuration

## Installation

```bash
# Using pip
pip install pmo

# From source
git clone https://github.com/yourusername/pmo.git
cd pmo
pip install -e .
```

## Usage

### Quick Start

1. Create a `pmo.yml` file in your project:

```yaml
# Basic format: service-name: command
web-server: node server.js

# Detailed format
api:
  cmd: python api.py
  cwd: ./api
  env:
    NODE_ENV: production
```

2. Start your services:

```bash
pmo start
```

### Core Commands

- **Start Services**:
  ```bash
  pmo start [all | service-name]
  ```
  Starts all services or a specific service by name.

- **Stop Services**:
  ```bash
  pmo stop [all | service-name]
  ```
  Stops all running services or a specific service by name.

- **Restart Services**:
  ```bash
  pmo restart [all | service-name]
  ```
  Restarts all services or a specific service by name.

- **View Service Logs**:
  ```bash
  pmo log [all | service-name]
  ```
  Shows logs in real-time (similar to `tail -f`).

- **List Services**:
  ```bash
  pmo ps
  ```
  Shows status of all configured services.

## Configuration

### pmo.yml

The `pmo.yml` file supports two formats:

1. **Simple format**:
   ```yaml
   service-name: command to run
   ```

2. **Detailed format**:
   ```yaml
   service-name:
     cmd: command to run
     cwd: working directory (optional)
     env:
       ENV_VAR1: value1
       ENV_VAR2: value2
   ```

**Note**: The name "pmo" is reserved and cannot be used as a service name.

### Directory Structure

PMO creates a `.pmo` directory to store runtime information:

```
.pmo/
├── logs/
│   ├── [service-name]-out.log    # Standard output logs
│   └── [service-name]-error.log  # Error logs
├── pids/
│   └── [service-name].pid        # Process ID files
```

## License

MIT