# PMO

A lightweight process manager for Linux inspired by PM2, but using YAML configuration and designed primarily for development environments.

## Features

- Simple YAML configuration
- Start, stop, and restart services
- Real-time logs with service name highlighting
- Basic process supervision
- Environment variable support

## Installation

```bash
# Using pip
pip install pmo
```

## Usage

### Quick Start

1. Create a `pmo.yml` file in your project:

```yaml
# Simple format
web-server: node server.js

# Detailed format
api:
  cmd: python api.py
  cwd: ./api
  env:
    NODE_ENV: development
```

2. Start your services:

```bash
pmo start
```

### Commands

- **Start**: `pmo start [all | service-name]`
- **Stop**: `pmo stop [all | service-name]`
- **Restart**: `pmo restart [all | service-name]`
- **Logs**: `pmo log [all | service-name]`
- **List**: `pmo ps`

## Configuration

The `pmo.yml` file supports two formats:

1. **Simple**: `service-name: command`
2. **Detailed**:
   ```yaml
   service-name:
     cmd: command
     cwd: working directory (optional)
     env:
       KEY: value
   ```

PMO manages runtime data in the `.pmo` directory with logs and PID files.

## License

MIT