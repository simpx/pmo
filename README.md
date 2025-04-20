# SERVLY

A simple process management tool for Linux, similar to PM2, designed to simplify application deployment and management.

## Features

- Start, stop, and restart services defined in a `servly.yml` configuration file
- View real-time logs with service name highlighting
- Automatic process supervision and PID management
- Environment variable support
- Simple YAML configuration

## Installation

```bash
# Using pip
pip install servly

# From source
git clone https://github.com/yourusername/servly.git
cd servly
pip install -e .
```

## Usage

### Quick Start

1. Create a `servly.yml` file in your project:

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
servly start
```

### Core Commands

- **Start Services**:
  ```bash
  servly start [all | service-name]
  ```
  Starts all services or a specific service by name.

- **Stop Services**:
  ```bash
  servly stop [all | service-name]
  ```
  Stops all running services or a specific service by name.

- **Restart Services**:
  ```bash
  servly restart [all | service-name]
  ```
  Restarts all services or a specific service by name.

- **View Service Logs**:
  ```bash
  servly log [all | service-name]
  ```
  Shows logs in real-time (similar to `tail -f`).

- **List Services**:
  ```bash
  servly list
  ```
  Shows status of all configured services.

## Configuration

### servly.yml

The `servly.yml` file supports two formats:

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

**Note**: The name "servly" is reserved and cannot be used as a service name.

### Directory Structure

Servly creates a `.servly` directory to store runtime information:

```
.servly/
├── logs/
│   ├── [service-name]-out.log    # Standard output logs
│   └── [service-name]-error.log  # Error logs
├── pids/
│   └── [service-name].pid        # Process ID files
```

## License

MIT