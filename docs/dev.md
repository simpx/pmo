# PMO Technical Development Guide

PMO (Process Manager Omni) is a lightweight process management tool inspired by PM2, designed for efficient application deployment and monitoring in development environments.

## Architecture Overview

PMO operates with the following core components:

- **ServiceManager**: Handles process lifecycle management (start, stop, restart)
- **LogManager**: Manages service logs with real-time monitoring capabilities
- **CLI**: Provides a user-friendly command-line interface

### Directory Structure

The PMO runtime uses a `.pmo` directory that maintains the following structure:

```
.pmo/
├── logs/
│   ├── [service-name]-out.log    # Standard output logs
│   └── [service-name]-error.log  # Error logs
├── pids/
│   ├── [service-name].pid        # Process ID files
│   ├── [service-name].time       # Service start time records
│   └── [service-name].restarts   # Restart count tracking
```

## Core Components

### 1. ServiceManager

The ServiceManager (`pmo/service.py`) is responsible for:

- Parsing the `pmo.yml` configuration file
- Managing process lifecycle (start, stop, restart)
- Tracking service status and resource usage
- Monitoring CPU, memory, and GPU usage for running processes
- Maintaining process metadata (PIDs, uptime, restart counts)

#### Process Control Implementation

Services are started as detached processes with:
- Output redirected to log files
- Process group isolation for clean termination
- Environment variable inheritance and customization
- Working directory control

The stop sequence uses a graceful shutdown approach:
1. Send SIGTERM for graceful termination
2. Wait for process to terminate (configurable timeout)
3. Send SIGKILL if process doesn't respond to SIGTERM
4. Clean up PID and metadata files

### 2. LogManager

The LogManager (`pmo/logs.py`) handles:

- Real-time log monitoring with formatting
- Log file management and cleanup
- Combining multiple log streams for parallel viewing
- Extracting and displaying timestamps

### 3. CLI Interface

The CLI (`pmo/cli.py`) provides:

- Command parsing with extensive options
- Rich terminal output with status indicators
- Service table display with resource usage statistics
- Interactive log viewing

## Configuration Format

PMO supports two configuration styles in the `pmo.yml` file:

### Simple Format

```yaml
# Direct command specification
service-name: command to execute
```

### Detailed Format

```yaml
service-name:
  cmd: "command to execute"
  cwd: "./working/directory"  # Optional
  env:                        # Optional
    ENV_VAR1: value1
    ENV_VAR2: value2
```

### Environment Variables from .env Files

PMO automatically loads environment variables from a `.env` file located in the same directory as `pmo.yml`. These variables are applied to all services, with service-specific environment variables taking precedence if the same variable is defined in both places.

The `.env` file follows standard dotenv format:

```
# Comments are supported
DATABASE_URL=postgres://localhost:5432/mydb
API_KEY=secret-key-value
DEBUG=true
```

Implementation details:
- PMO uses the `python-dotenv` library to parse the `.env` file
- Variables loaded from `.env` are applied to all services
- Service-specific environment variables (defined in `pmo.yml`) override variables from `.env` 
- Environment variables inherited from the parent process are preserved

This is particularly useful for:
- Storing sensitive credentials (API keys, passwords) outside of version control
- Sharing common environment configuration across multiple services
- Setting development-specific variables without modifying service definitions

## Resource Monitoring

PMO monitors:

- **CPU Usage**: Per-process CPU percentage
- **Memory Usage**: Physical memory consumption (RSS) in human-readable format
- **GPU Resources**: For NVIDIA GPUs, tracks memory usage and device allocation
  - Automatic detection via pynvml (if available) or nvidia-smi

## Implementation Notes

### Process Isolation

Each managed process runs in its own process group, allowing PMO to properly terminate not just the main process but all of its children when stopping a service.

### Graceful Shutdown

The stop sequence follows best practices by:
1. Attempting graceful termination with SIGTERM
2. Waiting for a configurable timeout period
3. Force termination with SIGKILL if necessary

### GPU Detection

GPU resource monitoring works through multiple methods:
- Primary: pynvml library (if available)
- Fallback: nvidia-smi command-line interface

### Log File Handling

When a service is running, log files are preserved but can be cleared.
For stopped services, log files can be either preserved or deleted based on configuration.

## Technical References

- Python subprocess: Used for process creation and management
- psutil: For process monitoring and resource usage statistics
- Rich: Terminal UI rendering and formatting
- PyYAML: Configuration file parsing
- pynvml: NVIDIA GPU monitoring (optional dependency)