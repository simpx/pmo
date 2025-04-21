# PMO Testing Plan

This document outlines the testing strategy for PMO (Process Manager Omni), a lightweight process manager designed for development environments. The test plan covers both unit tests (using mocks) and integration tests to ensure the application functions correctly.

## 1. Testing Components

### 1.1 Unit Tests

Unit tests focus on individual components with dependencies mocked. These tests provide fast feedback and validate the core logic of each component.

### 1.2 Integration Tests

Integration tests validate the interaction between components and real system resources, ensuring the application works correctly in a production-like environment.

### 1.3 Test Organization

Tests are organized in the `tests/` directory:
- `conftest.py`: Test fixtures and setup
- `test_config.py`: Configuration parsing tests
- `test_logs.py`: Log management tests
- `test_service_management.py`: Service lifecycle management tests
- `test_advanced.py`: Tests for advanced features
- `test_integration.py`: End-to-end integration tests

## 2. Unit Test Plan

### 2.1 ServiceManager Tests

#### 2.1.1 Configuration Loading

| Test ID | Description | Mock/Setup | Expected Result |
|---------|-------------|-----------|----------------|
| UT-CFG-001 | Load valid simple configuration | Mock YAML file | Config parsed correctly with services in normalized format |
| UT-CFG-002 | Load valid detailed configuration | Mock YAML file | Config parsed correctly with full service details |
| UT-CFG-003 | Load mixed format configuration | Mock YAML file | Both formats normalized correctly |
| UT-CFG-004 | Handle reserved name "pmo" | Mock config with "pmo" service | Service ignored, warning logged |
| UT-CFG-005 | Handle invalid configuration | Mock malformed YAML | Empty config returned, error logged |
| UT-CFG-006 | Load .env variables | Mock .env file | Environment variables loaded correctly |
| UT-CFG-007 | Handle missing config file | Non-existent file path | Empty config returned, error logged |
| UT-CFG-008 | Handle UTF-8 characters in config | Config with UTF-8 chars | Config parsed correctly with UTF-8 support |
| UT-CFG-009 | Handle special chars in service names | Config with special chars | Service names preserved correctly |
| UT-CFG-010 | Handle relative path resolution | Config with relative paths | Paths resolved against config directory |
| UT-CFG-011 | Handle empty .env file | Empty .env file | No errors, no environment variables added |

#### 2.1.2 Service Lifecycle Management

| Test ID | Description | Mock/Setup | Expected Result |
|---------|-------------|-----------|----------------|
| UT-SVC-001 | Start service | Mock subprocess.Popen | Service started, PID file created, start time recorded |
| UT-SVC-002 | Start service with env variables | Mock subprocess, env vars | Env vars passed to process |
| UT-SVC-003 | Start service with working dir | Mock subprocess, cwd | Working directory set correctly |
| UT-SVC-004 | Start already running service | Mock is_running to return True | No action, log message |
| UT-SVC-005 | Stop running service | Mock os.kill, is_process_running | Process sent SIGTERM, PID file removed |
| UT-SVC-006 | Stop service with SIGKILL | Mock process not responding to SIGTERM | SIGKILL sent after timeout |
| UT-SVC-007 | Stop non-running service | Mock get_service_pid to return None | No action, log message |
| UT-SVC-008 | Restart service | Mock stop and start methods | Service stopped and started, restart count incremented |
| UT-SVC-009 | Test is_running detection | Mock pid file and process check | Return correct status |
| UT-SVC-010 | Test service stop timeout boundary | Mock with freezegun | Correct timeout handling |
| UT-SVC-011 | Handle command with spaces/quotes | Mock subprocess with complex cmd | Command parsed and executed correctly |
| UT-SVC-012 | Multiple service operations | Mock concurrent operations | All operations complete correctly |

#### 2.1.3 Process Monitoring

| Test ID | Description | Mock/Setup | Expected Result |
|---------|-------------|-----------|----------------|
| UT-MON-001 | Get process statistics | Mock psutil.Process | Return CPU, memory usage |
| UT-MON-002 | Format CPU percentage | Mock values | Correctly formatted strings |
| UT-MON-003 | Format memory usage | Mock values | Correctly formatted KB/MB/GB strings |
| UT-MON-004 | Get uptime | Mock start_times | Correct uptime calculation |
| UT-MON-005 | Format uptime | Various uptime values | Correct display format (e.g., "1h 30m") |
| UT-MON-006 | Get GPU statistics via pynvml | Mock pynvml | Correct GPU memory and ID |
| UT-MON-007 | Get GPU statistics via nvidia-smi | Mock subprocess, no pynvml | Correct GPU memory and ID |
| UT-MON-008 | Get process tree | Mock psutil | Return main process and children PIDs |
| UT-MON-009 | Handle missing GPU tools | Mock import/command errors | Return default values |

### 2.2 LogManager Tests

| Test ID | Description | Mock/Setup | Expected Result |
|---------|-------------|-----------|----------------|
| UT-LOG-001 | Get log file paths | - | Correct stdout and stderr paths |
| UT-LOG-002 | Parse log line with timestamp | Sample log lines | Extracted timestamp and content |
| UT-LOG-003 | Parse log line without timestamp | Sample log lines | Default timestamp added, content preserved |
| UT-LOG-004 | Flush logs for running service | Mock file operations | Files cleared but not deleted |
| UT-LOG-005 | Flush logs for stopped service | Mock file operations | Log files deleted |
| UT-LOG-006 | Display recent logs | Mock file read | Correct number of lines displayed |
| UT-LOG-007 | Follow logs | Mock file handlers | Real-time log updates displayed |
| UT-LOG-008 | Handle missing log files | Mock non-existent files | Warning message, continue with available logs |
| UT-LOG-009 | Handle multi-line log entries | Log with multi-line entries | Proper parsing and display of multi-line logs |
| UT-LOG-010 | Log large file behavior | Mock large log file | Efficient handling without memory issues |
| UT-LOG-011 | Parse various timestamp formats | Logs with different formats | All timestamp formats correctly parsed |
| UT-LOG-012 | Color output formatting | Mock console output | Correct styling applied to different log types |

### 2.3 CLI Interface Tests

| Test ID | Description | Mock/Setup | Expected Result |
|---------|-------------|-----------|----------------|
| UT-CLI-001 | Parse valid command arguments | Mock argv | Correctly parsed args |
| UT-CLI-002 | Handle missing subcommand | Mock argv | Help displayed |
| UT-CLI-003 | List command | Mock ServiceManager | Display service table |
| UT-CLI-004 | Start command | Mock ServiceManager | Services started correctly |
| UT-CLI-005 | Stop command | Mock ServiceManager | Services stopped correctly |
| UT-CLI-006 | Restart command | Mock ServiceManager | Services restarted correctly |
| UT-CLI-007 | Log command | Mock LogManager | Log viewing initialized correctly |
| UT-CLI-008 | Flush command | Mock LogManager | Logs flushed correctly |
| UT-CLI-009 | Handle custom config path (-f) | Mock argv with -f | Config path passed to ServiceManager |
| UT-CLI-010 | Handle non-existent service | Mock invalid service name | Error message displayed |

## 3. Integration Test Plan

### 3.1 Basic Functionality Tests

| Test ID | Description | Setup | Expected Result |
|---------|-------------|-------|----------------|
| IT-BAS-001 | Load default config file | Valid pmo.yml | Config loaded, services available |
| IT-BAS-002 | Load custom config file | Test config file | Custom config loaded instead of default |
| IT-BAS-003 | Parse mixed format config | Config with both formats | All services available and normalized |
| IT-BAS-004 | Directory structure creation | Fresh environment | .pmo/logs and .pmo/pids directories created |

### 3.2 Service Management Tests

| Test ID | Description | Setup | Expected Result |
|---------|-------------|-------|----------------|
| IT-SVC-001 | Start single service | Test service | Service process running, PID file exists |
| IT-SVC-002 | Start all services | Multiple test services | All services running, all PID files exist |
| IT-SVC-003 | Stop single service | Running test service | Process terminated, PID file removed |
| IT-SVC-004 | Stop all services | Multiple running services | All processes terminated, PID files removed |
| IT-SVC-005 | Restart single service | Running test service | Service stopped then started, PID changed |
| IT-SVC-006 | Restart all services | Multiple running services | All services restarted, PIDs changed |
| IT-SVC-007 | Start service with env vars | Service with env config | Process has access to configured variables |
| IT-SVC-008 | Start service with custom working dir | Service with cwd config | Process running in specified directory |
| IT-SVC-009 | PID file cleanup on abnormal termination | Kill service process manually | PID file removed when status checked |
| IT-SVC-010 | Service recovery after crash | Service configured and crashed | Service state accurately reflects crash |
| IT-SVC-011 | Graceful shutdown timing | Service with shutdown delay | SIGTERM sent, wait for timeout, then SIGKILL |
| IT-SVC-012 | Zombie process handling | Create zombie process | Properly identified and cleaned up |
| IT-SVC-013 | Child process management | Service spawning children | All child processes terminated on stop |
| IT-SVC-014 | Service start time tracking | Start service, wait, check | Accurate uptime calculation |
| IT-SVC-015 | Service restart count | Restart service multiple times | Correct restart counter incremented |
| IT-SVC-016 | Multiple service instance prevention | Try to start running service | Prevented duplicate start, logged warning |
| IT-SVC-017 | Service PID file integrity | Corrupt PID file manually | Graceful recovery and correction |
| IT-SVC-018 | Service stop sequence | Stop service with multiple children | Proper process group termination order |
| IT-SVC-019 | Process detection accuracy | External termination of service | PMO detects termination on next status check |
| IT-SVC-020 | Service state persistence | Restart PMO with running services | State properly recovered |

### 3.3 Log Management Tests

| Test ID | Description | Setup | Expected Result |
|---------|-------------|-------|----------------|
| IT-LOG-001 | Log file creation | Start test service | stdout and stderr logs created |
| IT-LOG-002 | View service logs | Service with output | Logs displayed correctly |
| IT-LOG-003 | View all services logs | Multiple services | Combined logs with service indicators |
| IT-LOG-004 | Follow logs | Service with continuous output | Real-time log updates displayed |
| IT-LOG-005 | Display limited lines | Service with many log lines | Only specified number of lines displayed |
| IT-LOG-006 | Flush running service logs | Running service with logs | Logs cleared but files exist |
| IT-LOG-007 | Flush stopped service logs | Stopped service with logs | Log files deleted |
| IT-LOG-008 | Log timestamps | Service with timed output | Timestamps displayed correctly |

### 3.4 Environment Variables Tests

| Test ID | Description | Setup | Expected Result |
|---------|-------------|-------|----------------|
| IT-ENV-001 | Load .env file variables | .env file with test vars | Variables available to all services |
| IT-ENV-002 | Service-specific variables | Config with env vars | Variables available to specific service |
| IT-ENV-003 | Service variables override .env | Conflicting variables | Service config takes precedence |
| IT-ENV-004 | Inherit parent env variables | Set env var before starting PMO | Variables inherited by managed processes |

### 3.5 Error Handling Tests

| Test ID | Description | Setup | Expected Result |
|---------|-------------|-------|----------------|
| IT-ERR-001 | Start non-existent service | Invalid service name | Error message, no action |
| IT-ERR-002 | Stop non-existent service | Invalid service name | Error message, no action |
| IT-ERR-003 | Invalid config syntax | Malformed YAML | Error message, no services loaded |
| IT-ERR-004 | Service with invalid command | Config with bad command | Error on start, appropriate message |
| IT-ERR-005 | Invalid service name pattern | Reserved "pmo" name | Warning, service ignored |

### 3.6 Long-Running Tests

| Test ID | Description | Setup | Expected Result |
|---------|-------------|-------|----------------|
| IT-LNG-001 | Service stability | Long-running test service | Remains operational, stats correct |
| IT-LNG-002 | Resource monitoring accuracy | CPU/memory intensive service | Usage statistics match system tools |
| IT-LNG-003 | Log rotation handling | Service with verbose logging | Continues working with large log files |

## 4. Test Implementation Guidelines

### 4.1 Unit Test Tools

- `pytest`: Test framework
- `unittest.mock`: For mocking dependencies
- `pytest-mock`: For fixture-based mocking
- `pytest-cov`: For coverage reporting
- `freezegun`: For time-related testing (freezing time)

### 4.2 Mocking Strategies

- File operations: Mock `open()`, `Path` operations
- Process operations: Mock `subprocess.Popen`, `os.kill`, `psutil.Process`
- Time operations: Use `freezegun.freeze_time()` for predictable time-based tests
- YAML operations: Mock `yaml.safe_load` for configuration testing

### 4.3 Time-Based Testing with freezegun

For predictable time-based testing:

```python
from freezegun import freeze_time

@freeze_time("2025-04-21 12:00:00")
def test_uptime_calculation():
    # Time is frozen at 2025-04-21 12:00:00
    service_manager = ServiceManager()
    # Set a service start time to 1 hour ago
    service_manager.start_times["test-service"] = time.time() - 3600
    # Assert uptime is exactly 1 hour
    assert service_manager.get_uptime("test-service") == 3600
```

Key time-based test scenarios:
- Service uptime calculation
- Timestamp parsing in logs
- Service stop timeout behavior
- Log rotation timing

### 4.4 Test Fixtures

Define fixtures in `conftest.py` for:
- Sample configuration files (simple and complex formats)
- Mock service processes
- Temporary directories for .pmo structure
- Sample log files with different formats
- Common mock setups for dependencies

### 4.5 Continuous Integration

- Run unit tests on every commit
- Run integration tests before releases
- Generate coverage reports
- Enforce minimum coverage threshold

## 5. Expected Coverage

- **Unit Tests**: Aim for >90% code coverage
- **Integration Tests**: Cover all main user workflows
- **Focus Areas**: 
  - Configuration parsing
  - Process lifecycle management
  - Error handling
  - Resource monitoring
  - Log management

## 6. Known Limitations

- GPU testing requires NVIDIA hardware or advanced mocking
- Some OS-specific behaviors may need conditional tests
- Process monitoring accuracy may vary across environments