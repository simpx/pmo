# PMO - Process Manager Omni

A lightweight process manager inspired by PM2, but designed primarily for development environments.

## Features

- `start`, `stop`, and `restart` services, similar to PM2
- Simple YAML configuration
- Real-time logs with highlight
- Environment variable support
- Automatic `.env` file loading
- Multi-machine support with hostname-specific directories (for shared NAS environments)

## Installation

```bash
pip install pmo
```

## Usage

### Quick Start

1. Create a `pmo.yml` file in your project:

```yaml
# Simple format, just like procfile
web-server: node server.js

# Detailed format
api-server:
  cmd: python api.py
  cwd: ./api
  env:
    NODE_ENV: development
```

2. Optional: Create a `.env` file for shared environment variables:

```
# This will apply to all services
DATABASE_URL=postgres://localhost:5432/mydb
DEBUG=true
```

3. Start your services:

```bash
pmo start
```

4. List your services:

```bash
pmo ls
```

Output:

```plaintext
+---------------------------------------------------------------------------------------------------------------------+
|  id  | name      |        pid |   uptime |   status    |        cpu |        mem |    gpu mem | gpu id | user       |
|------+-----------+------------+----------+-------------+------------+------------+------------+--------+------------|
|  0   | vllm-1    |     482950 |  25m 15s |   running   |       0.0% |        1mb |  20632 MiB |   0    | simpx      |
|  1   | sglang-1  |     482952 |  25m 15s |   running   |       0.0% |        1mb |  20632 MiB |   1    | simpx      |
|  2   | vllm-2    |     482954 |  25m 15s |   running   |       0.0% |        1mb |  20632 MiB |   2    | simpx      |
+---------------------------------------------------------------------------------------------------------------------+
```

### Commands

```
pmo start   [all | service-name | service-id]
pmo stop    [all | service-name | service-id]
pmo restart [all | service-name | service-id]
pmo log     [all | service-name | service-id]
pmo flush   [all | service-name | service-id]
pmo dry-run [all | service-name | service-id]
pmo ls

```

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

### Multi-machine Support

PMO now supports multiple machines sharing the same configuration through a shared filesystem (like NAS). Each machine will store its process information in a hostname-specific directory:

```
.pmo/
  hostname1/
    pids/
    logs/
  hostname2/
    pids/
    logs/
```

This allows processes on different machines to be managed separately even when sharing the same configuration files.

## License

MIT
