# PMO Development Guide

PMO is a process management tool similar to PM2, designed to simplify application deployment and management.

## Overview

PMO manages processes based on:
- Configuration in `pmo.yml` file in the current directory
- Environment variables from `.env` file
- Runtime information stored in `.pmo` directory

## Directory Structure

The `.pmo` directory stores all runtime information:

```
.pmo/
├── logs/
│   ├── [service-name]-out.log    # Standard output logs
│   └── [service-name]-error.log  # Error logs
├── pids/
│   └── [service-name].pid        # Process ID files
```

## Core Commands

### Starting Services

```bash
pmo start [all | service-name]
```

Starts all services defined in `pmo.yml` or a specific service by name.

### Stopping Services

```bash
pmo stop [all | service-name]
```

Stops all running services or a specific service by name.

### Viewing Logs

```bash
pmo log [all | service-name]
```

Displays logs in real-time (similar to `tail -f`):
- For a specific service: shows only that service's logs
- For `all`: combines multiple log streams into a single view (similar to PM2)

### Restarting Services

```bash
pmo restart [all | service-name]
```

Restarts all services or a specific service by name.

## Configuration

### pmo.yml

PMO supports both simple command format and detailed configuration:

```yaml
# Basic usage - directly specify command
app1: python app.py

# Detailed configuration
app2:
  script: "python app.py"
  cwd: "./service1"
  env:
    NODE_ENV: production
```

The basic format `app-name: command` allows for quick and simple service definition without additional configuration.

**Note:** The name "pmo" is reserved and cannot be used as an application name, to avoid conflicts with internal configuration directives.

Examples:

```yaml
# Valid configurations
web-server: node server.js
api: python api.py

# Invalid - using reserved name
pmo: node app.js  # This will not work as expected
```

### Environment Variables

Environment variables in `.env` file are automatically loaded and available to all managed processes.

## Development Workflow

1. Define services in `pmo.yml`
2. Set environment variables in `.env` if needed
3. Use `pmo start` to launch services
4. Monitor with `pmo log`
5. Restart or stop as needed