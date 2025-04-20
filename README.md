# PMO - Process Manager Omni

A lightweight process manager inspired by PM2, but designed primarily for development environments.

## Features

- `start`, `stop`, and `restart` services, similar to PM2
- Simple YAML configuration
- Real-time logs with highlight
- Environment variable support

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

2. Start your services:

```bash
pmo start
```

3. List your services:

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

- **Start**: `pmo start [all | service-name]`
- **Stop**: `pmo stop [all | service-name]`
- **Restart**: `pmo restart [all | service-name]`
- **Logs**: `pmo log [all | service-name]`
- **List**: `pmo ls`

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