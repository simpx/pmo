//! Service management functionality for PMO

use crate::util::substitute_env_vars;
use anyhow::{anyhow, Result};
use nix::sys::signal::{kill, Signal};
use nix::unistd::Pid;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

/// Service configuration from YAML
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServiceConfig {
    pub cmd: String,
    #[serde(default)]
    pub cwd: Option<String>,
    #[serde(default)]
    pub env: HashMap<String, String>,
    #[serde(default)]
    pub extends: Option<String>,
    #[serde(default)]
    pub merge_logs: bool,
}

/// Service runtime status
#[derive(Debug, Clone)]
pub struct ServiceStatus {
    pub name: String,
    pub pid: Option<i32>,
    pub running: bool,
    pub uptime: Option<f64>,
    pub cpu_percent: Option<f64>,
    pub memory_mb: Option<f64>,
    pub memory_percent: Option<f64>,
    pub restarts: u32,
    pub gpu_memory: Option<String>,
    pub gpu_id: Option<String>,
}

/// Service Manager - manages processes based on pmo.yml configuration
pub struct ServiceManager {
    pub config_path: PathBuf,
    pub config_dir: PathBuf,
    pub pmo_base_dir: PathBuf,
    pub pmo_dir: PathBuf,
    pub pid_dir: PathBuf,
    pub log_dir: PathBuf,
    pub services: HashMap<String, ServiceConfig>,
    pub start_times: HashMap<String, f64>,
    pub restarts: HashMap<String, u32>,
    pub dotenv_vars: HashMap<String, String>,
}

impl ServiceManager {
    /// Create a new ServiceManager
    pub fn new(config_path: &str, pmo_dir_name: &str) -> Result<Self> {
        let config_path = PathBuf::from(config_path);
        let config_dir = config_path
            .parent()
            .map(|p| p.to_path_buf())
            .unwrap_or_else(|| PathBuf::from("."))
            .canonicalize()
            .unwrap_or_else(|_| PathBuf::from("."));

        let pmo_base_dir = config_dir.join(pmo_dir_name);
        let hostname = hostname::get()
            .map(|h| h.to_string_lossy().to_string())
            .unwrap_or_else(|_| "localhost".to_string());
        let pmo_dir = pmo_base_dir.join(&hostname);
        let pid_dir = pmo_dir.join("pids");
        let log_dir = pmo_dir.join("logs");

        // Create directories
        fs::create_dir_all(&pid_dir)?;
        fs::create_dir_all(&log_dir)?;

        let mut manager = Self {
            config_path,
            config_dir,
            pmo_base_dir,
            pmo_dir,
            pid_dir,
            log_dir,
            services: HashMap::new(),
            start_times: HashMap::new(),
            restarts: HashMap::new(),
            dotenv_vars: HashMap::new(),
        };

        // Load .env file
        manager.load_dotenv();

        // Load service configuration
        manager.services = manager.load_config()?;

        // Load existing start times and restarts
        manager.load_start_times();
        manager.load_restarts();

        Ok(manager)
    }

    /// Load environment variables from .env file
    fn load_dotenv(&mut self) {
        let dotenv_path = self.config_dir.join(".env");
        if dotenv_path.exists() {
            if let Ok(file) = File::open(&dotenv_path) {
                let reader = BufReader::new(file);
                for line in reader.lines().map_while(Result::ok) {
                    let line = line.trim();
                    if line.is_empty() || line.starts_with('#') {
                        continue;
                    }
                    if let Some((key, value)) = line.split_once('=') {
                        let key = key.trim().to_string();
                        let value = value.trim().trim_matches('"').trim_matches('\'').to_string();
                        self.dotenv_vars.insert(key, value);
                    }
                }
            }
        }
    }

    /// Load service configurations from pmo.yml
    fn load_config(&self) -> Result<HashMap<String, ServiceConfig>> {
        if !self.config_path.exists() {
            return Err(anyhow!(
                "Configuration file not found: {:?}",
                self.config_path
            ));
        }

        let content = fs::read_to_string(&self.config_path)?;
        let raw_config: HashMap<String, serde_yaml::Value> = serde_yaml::from_str(&content)?;

        // Step 1: Normalize all service configurations
        let mut normalized: HashMap<String, ServiceConfig> = HashMap::new();

        for (name, value) in raw_config.iter() {
            if name.to_lowercase() == "pmo" {
                continue; // Reserved name
            }

            let config = match value {
                serde_yaml::Value::String(cmd) => ServiceConfig {
                    cmd: cmd.clone(),
                    cwd: None,
                    env: HashMap::new(),
                    extends: None,
                    merge_logs: false,
                },
                serde_yaml::Value::Mapping(map) => {
                    // Handle script alias for cmd
                    let cmd = map
                        .get(&serde_yaml::Value::String("cmd".to_string()))
                        .or_else(|| map.get(&serde_yaml::Value::String("script".to_string())))
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string());

                    let cwd = map
                        .get(&serde_yaml::Value::String("cwd".to_string()))
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string());

                    let env: HashMap<String, String> = map
                        .get(&serde_yaml::Value::String("env".to_string()))
                        .and_then(|v| v.as_mapping())
                        .map(|m| {
                            m.iter()
                                .filter_map(|(k, v)| {
                                    let key = k.as_str()?.to_string();
                                    let value = match v {
                                        serde_yaml::Value::String(s) => s.clone(),
                                        serde_yaml::Value::Number(n) => n.to_string(),
                                        serde_yaml::Value::Bool(b) => b.to_string(),
                                        _ => return None,
                                    };
                                    Some((key, value))
                                })
                                .collect()
                        })
                        .unwrap_or_default();

                    let extends = map
                        .get(&serde_yaml::Value::String("extends".to_string()))
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string());

                    let merge_logs = map
                        .get(&serde_yaml::Value::String("merge_logs".to_string()))
                        .and_then(|v| v.as_bool())
                        .unwrap_or(false);

                    ServiceConfig {
                        cmd: cmd.unwrap_or_default(),
                        cwd,
                        env,
                        extends,
                        merge_logs,
                    }
                }
                _ => continue,
            };

            normalized.insert(name.clone(), config);
        }

        // Step 2: Resolve extends inheritance
        let mut resolved: HashMap<String, ServiceConfig> = HashMap::new();

        fn resolve_extends(
            name: &str,
            normalized: &HashMap<String, ServiceConfig>,
            seen: &mut Vec<String>,
        ) -> Result<ServiceConfig> {
            if seen.contains(&name.to_string()) {
                return Err(anyhow!("Circular extends detected for service '{}'", name));
            }
            seen.push(name.to_string());

            let config = normalized
                .get(name)
                .ok_or_else(|| anyhow!("Service '{}' not found", name))?
                .clone();

            if let Some(parent_name) = &config.extends {
                let parent = resolve_extends(parent_name, normalized, seen)?;

                // Merge: parent values, then child values override
                let mut merged_env = parent.env.clone();
                merged_env.extend(config.env.clone());

                Ok(ServiceConfig {
                    cmd: if config.cmd.is_empty() {
                        parent.cmd
                    } else {
                        config.cmd
                    },
                    cwd: config.cwd.or(parent.cwd),
                    env: merged_env,
                    extends: None,
                    merge_logs: config.merge_logs || parent.merge_logs,
                })
            } else {
                Ok(config)
            }
        }

        for name in normalized.keys() {
            let mut seen = Vec::new();
            match resolve_extends(name, &normalized, &mut seen) {
                Ok(config) => {
                    if !config.cmd.is_empty() {
                        resolved.insert(name.clone(), config);
                    }
                }
                Err(e) => {
                    eprintln!("Error resolving extends for service '{}': {}", name, e);
                }
            }
        }

        Ok(resolved)
    }

    /// Load start times from files
    fn load_start_times(&mut self) {
        for name in self.services.keys() {
            if self.is_running(name) {
                let time_file = self.pid_dir.join(format!("{}.time", name));
                if time_file.exists() {
                    if let Ok(content) = fs::read_to_string(&time_file) {
                        if let Ok(timestamp) = content.trim().parse::<f64>() {
                            self.start_times.insert(name.clone(), timestamp);
                        }
                    }
                }
            }
        }
    }

    /// Load restart counts from files
    fn load_restarts(&mut self) {
        for name in self.services.keys() {
            let restart_file = self.pid_dir.join(format!("{}.restarts", name));
            if restart_file.exists() {
                if let Ok(content) = fs::read_to_string(&restart_file) {
                    if let Ok(count) = content.trim().parse::<u32>() {
                        self.restarts.insert(name.clone(), count);
                    }
                }
            }
        }
    }

    /// Get PID file path for a service
    pub fn get_pid_file(&self, service_name: &str) -> PathBuf {
        self.pid_dir.join(format!("{}.pid", service_name))
    }

    /// Get PID for a running service
    pub fn get_service_pid(&self, service_name: &str) -> Option<i32> {
        let pid_file = self.get_pid_file(service_name);
        if !pid_file.exists() {
            return None;
        }

        let content = fs::read_to_string(&pid_file).ok()?;
        let pid: i32 = content.trim().parse().ok()?;

        if self.is_process_running(pid) {
            Some(pid)
        } else {
            // Clean up stale PID file
            let _ = fs::remove_file(&pid_file);
            let time_file = self.pid_dir.join(format!("{}.time", service_name));
            let _ = fs::remove_file(time_file);
            None
        }
    }

    /// Check if a process is running
    fn is_process_running(&self, pid: i32) -> bool {
        // Try to send signal 0 to check if process exists
        kill(Pid::from_raw(pid), None).is_ok()
    }

    /// Check if a service is running
    pub fn is_running(&self, service_name: &str) -> bool {
        self.get_service_pid(service_name).is_some()
    }

    /// Get list of configured service names
    pub fn get_service_names(&self) -> Vec<String> {
        let mut names: Vec<_> = self.services.keys().cloned().collect();
        names.sort();
        names
    }

    /// Get list of running services
    pub fn get_running_services(&self) -> Vec<String> {
        self.get_service_names()
            .into_iter()
            .filter(|name| self.is_running(name))
            .collect()
    }

    /// Get uptime in seconds
    pub fn get_uptime(&self, service_name: &str) -> Option<f64> {
        if let Some(&start_time) = self.start_times.get(service_name) {
            if self.is_running(service_name) {
                let now = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .map(|d| d.as_secs_f64())
                    .unwrap_or(0.0);
                return Some(now - start_time);
            }
        }
        None
    }

    /// Format uptime to human-readable string
    pub fn format_uptime(&self, uptime_seconds: Option<f64>) -> String {
        match uptime_seconds {
            None => "-".to_string(),
            Some(secs) => {
                let secs = secs as u64;
                let days = secs / 86400;
                let hours = (secs % 86400) / 3600;
                let minutes = (secs % 3600) / 60;
                let seconds = secs % 60;

                if days > 0 {
                    format!("{}d {}h", days, hours)
                } else if hours > 0 {
                    format!("{}h {}m", hours, minutes)
                } else if minutes > 0 {
                    format!("{}m {}s", minutes, seconds)
                } else {
                    format!("{}s", seconds)
                }
            }
        }
    }

    /// Check if command is a Python script
    fn is_python_script(&self, cmd: &str, cwd: Option<&str>) -> bool {
        let cmd_lower = cmd.to_lowercase();
        if cmd_lower.starts_with("python")
            || cmd_lower.contains("/python")
            || cmd_lower.starts_with("python3")
            || cmd_lower.starts_with("python2")
        {
            return true;
        }

        // Check if first argument is a .py file
        if let Some(first_arg) = cmd.split_whitespace().next() {
            let script_path = if Path::new(first_arg).is_absolute() {
                PathBuf::from(first_arg)
            } else if let Some(cwd) = cwd {
                PathBuf::from(cwd).join(first_arg)
            } else {
                PathBuf::from(first_arg)
            };

            if script_path.extension().map(|e| e == "py").unwrap_or(false) {
                return true;
            }
        }

        false
    }

    /// Rotate log file
    fn rotate_log_file(&self, log_path: &Path, max_files: u32) {
        if !log_path.exists() {
            return;
        }

        // Remove oldest file
        let oldest = log_path.with_file_name(format!(
            "{}.{}",
            log_path.file_name().unwrap().to_string_lossy(),
            max_files
        ));
        let _ = fs::remove_file(oldest);

        // Shift existing rotated files
        for i in (1..max_files).rev() {
            let src = log_path.with_file_name(format!(
                "{}.{}",
                log_path.file_name().unwrap().to_string_lossy(),
                i
            ));
            if src.exists() {
                let dest = log_path.with_file_name(format!(
                    "{}.{}",
                    log_path.file_name().unwrap().to_string_lossy(),
                    i + 1
                ));
                let _ = fs::rename(&src, &dest);
            }
        }

        // Rotate current log
        let rotated = log_path.with_file_name(format!(
            "{}.1",
            log_path.file_name().unwrap().to_string_lossy()
        ));
        let _ = fs::rename(log_path, rotated);
    }

    /// Start a service
    pub fn start(&mut self, service_name: &str, dry_run: bool) -> Result<bool> {
        let config = self
            .services
            .get(service_name)
            .ok_or_else(|| anyhow!("Service '{}' not found in configuration", service_name))?
            .clone();

        if !dry_run && self.is_running(service_name) {
            return Ok(true);
        }

        // Prepare environment variables
        let mut env: HashMap<String, String> = std::env::vars().collect();
        env.extend(self.dotenv_vars.clone());
        env.extend(config.env.clone());

        // Substitute environment variables in command
        let cmd = substitute_env_vars(&config.cmd, &env);

        // Check for Python script and enable unbuffered mode
        if self.is_python_script(&cmd, config.cwd.as_deref()) {
            env.insert("PYTHONUNBUFFERED".to_string(), "1".to_string());
        }

        if dry_run {
            let mut cmd_str = String::new();
            if let Some(ref cwd) = config.cwd {
                cmd_str.push_str(&format!("cd {} && ", cwd));
            }
            // Only show service-specific env vars
            for (key, value) in &config.env {
                cmd_str.push_str(&format!("{}={} ", key, value));
            }
            cmd_str.push_str(&cmd);
            println!("{}: {}", service_name, cmd_str);
            return Ok(true);
        }

        // Prepare log files
        let (stdout_log, stderr_log) = if config.merge_logs {
            let merged = self.log_dir.join(format!("{}.log", service_name));
            (merged.clone(), merged)
        } else {
            (
                self.log_dir.join(format!("{}-out.log", service_name)),
                self.log_dir.join(format!("{}-error.log", service_name)),
            )
        };

        // Rotate logs
        self.rotate_log_file(&stdout_log, 30);
        if !config.merge_logs {
            self.rotate_log_file(&stderr_log, 30);
        }

        // Open log files
        let stdout_file = File::create(&stdout_log)?;
        let stderr_file = if config.merge_logs {
            stdout_file.try_clone()?
        } else {
            File::create(&stderr_log)?
        };

        // Write startup message
        let timestamp = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
        {
            let mut f = File::options().append(true).open(&stdout_log)?;
            if config.merge_logs {
                writeln!(
                    f,
                    "\n--- Starting service '{}' at {} (merged logs) ---",
                    service_name, timestamp
                )?;
            } else {
                writeln!(
                    f,
                    "\n--- Starting service '{}' at {} ---",
                    service_name, timestamp
                )?;
            }
        }
        if !config.merge_logs {
            let mut f = File::options().append(true).open(&stderr_log)?;
            writeln!(
                f,
                "\n--- Starting service '{}' at {} ---",
                service_name, timestamp
            )?;
        }

        // Start process
        let mut command = Command::new("sh");
        command
            .arg("-c")
            .arg(&cmd)
            .stdout(Stdio::from(stdout_file))
            .stderr(Stdio::from(stderr_file))
            .envs(&env);

        if let Some(ref cwd) = config.cwd {
            command.current_dir(cwd);
        }

        // Start in new session (detached)
        #[cfg(unix)]
        {
            use std::os::unix::process::CommandExt;
            command.process_group(0);
        }

        let child = command.spawn()?;
        let pid = child.id() as i32;

        // Save PID
        fs::write(self.get_pid_file(service_name), pid.to_string())?;

        // Save start time
        let start_time = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);
        self.start_times.insert(service_name.to_string(), start_time);
        fs::write(
            self.pid_dir.join(format!("{}.time", service_name)),
            start_time.to_string(),
        )?;

        Ok(true)
    }

    /// Get all child PIDs of a process
    fn get_process_tree(&self, pid: i32) -> Vec<i32> {
        let mut pids = vec![pid];

        // Read /proc to find children
        if let Ok(entries) = fs::read_dir("/proc") {
            for entry in entries.flatten() {
                if let Ok(name) = entry.file_name().into_string() {
                    if let Ok(child_pid) = name.parse::<i32>() {
                        let stat_path = format!("/proc/{}/stat", child_pid);
                        if let Ok(content) = fs::read_to_string(&stat_path) {
                            // Parse ppid from stat file
                            let parts: Vec<&str> = content.split_whitespace().collect();
                            if parts.len() > 3 {
                                if let Ok(ppid) = parts[3].parse::<i32>() {
                                    if ppid == pid {
                                        pids.extend(self.get_process_tree(child_pid));
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        pids
    }

    /// Stop a service
    pub fn stop(&mut self, service_name: &str, timeout: u64) -> Result<bool> {
        let pid = match self.get_service_pid(service_name) {
            Some(p) => p,
            None => return Ok(true), // Already stopped
        };

        let process_tree = self.get_process_tree(pid);

        // Try SIGTERM first
        for &p in &process_tree {
            let _ = kill(Pid::from_raw(p), Signal::SIGTERM);
        }

        // Wait for graceful shutdown
        for _ in 0..timeout {
            let remaining: Vec<_> = process_tree
                .iter()
                .filter(|&&p| self.is_process_running(p))
                .collect();
            if remaining.is_empty() {
                break;
            }
            std::thread::sleep(Duration::from_secs(1));
        }

        // Force kill remaining processes
        let remaining: Vec<_> = process_tree
            .iter()
            .filter(|&&p| self.is_process_running(p))
            .collect();

        if !remaining.is_empty() {
            for &&p in &remaining {
                let _ = kill(Pid::from_raw(p), Signal::SIGKILL);
            }
            std::thread::sleep(Duration::from_secs(1));
        }

        // Clean up files
        let _ = fs::remove_file(self.get_pid_file(service_name));
        let _ = fs::remove_file(self.pid_dir.join(format!("{}.time", service_name)));
        self.start_times.remove(service_name);

        Ok(true)
    }

    /// Restart a service
    pub fn restart(&mut self, service_name: &str) -> Result<bool> {
        self.stop(service_name, 5)?;
        let result = self.start(service_name, false)?;

        if result {
            let count = self.restarts.entry(service_name.to_string()).or_insert(0);
            *count += 1;
            fs::write(
                self.pid_dir.join(format!("{}.restarts", service_name)),
                count.to_string(),
            )?;
        }

        Ok(result)
    }

    /// Get restart count for a service
    pub fn get_restarts_count(&self, service_name: &str) -> u32 {
        *self.restarts.get(service_name).unwrap_or(&0)
    }

    /// Get process stats (CPU, memory)
    pub fn get_process_stats(&self, service_name: &str) -> ServiceStatus {
        let pid = self.get_service_pid(service_name);
        let running = pid.is_some();

        ServiceStatus {
            name: service_name.to_string(),
            pid,
            running,
            uptime: self.get_uptime(service_name),
            cpu_percent: None, // Would require sampling over time
            memory_mb: pid.and_then(|p| self.get_memory_mb(p)),
            memory_percent: None,
            restarts: self.get_restarts_count(service_name),
            gpu_memory: None, // Would require nvidia-ml
            gpu_id: None,
        }
    }

    /// Get memory usage in MB for a process
    fn get_memory_mb(&self, pid: i32) -> Option<f64> {
        let status_path = format!("/proc/{}/status", pid);
        if let Ok(content) = fs::read_to_string(&status_path) {
            for line in content.lines() {
                if line.starts_with("VmRSS:") {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if parts.len() >= 2 {
                        if let Ok(kb) = parts[1].parse::<f64>() {
                            return Some(kb / 1024.0);
                        }
                    }
                }
            }
        }
        None
    }

    /// Format CPU percent
    pub fn format_cpu_percent(&self, cpu: Option<f64>) -> String {
        match cpu {
            Some(c) => format!("{:.1}%", c),
            None => "0%".to_string(),
        }
    }

    /// Format memory
    pub fn format_memory(&self, memory_mb: Option<f64>) -> String {
        match memory_mb {
            None => "0b".to_string(),
            Some(mb) => {
                if mb < 1.0 {
                    format!("{}kb", (mb * 1024.0) as u64)
                } else if mb > 1024.0 {
                    format!("{:.1}gb", mb / 1024.0)
                } else {
                    format!("{}mb", mb as u64)
                }
            }
        }
    }

    /// Get all hostnames with services
    pub fn get_all_hostnames(&self) -> Vec<String> {
        let mut hostnames = Vec::new();

        if let Ok(entries) = fs::read_dir(&self.pmo_base_dir) {
            for entry in entries.flatten() {
                if entry.path().is_dir() {
                    let pids_dir = entry.path().join("pids");
                    let logs_dir = entry.path().join("logs");

                    let has_files = pids_dir
                        .exists()
                        .then(|| fs::read_dir(&pids_dir).ok())
                        .flatten()
                        .map(|d| d.count() > 0)
                        .unwrap_or(false)
                        || logs_dir
                            .exists()
                            .then(|| fs::read_dir(&logs_dir).ok())
                            .flatten()
                            .map(|d| d.count() > 0)
                            .unwrap_or(false);

                    if has_files {
                        if let Some(name) = entry.file_name().to_str() {
                            hostnames.push(name.to_string());
                        }
                    }
                }
            }
        }

        hostnames.sort();
        hostnames
    }

    /// Get log directory for remote hostname
    pub fn get_remote_log_dir(&self, hostname: &str) -> PathBuf {
        self.pmo_base_dir.join(hostname).join("logs")
    }

    /// Get remote service names
    pub fn get_remote_service_names(&self, hostname: &str) -> Vec<String> {
        let pid_dir = self.pmo_base_dir.join(hostname).join("pids");
        let mut names = Vec::new();

        if let Ok(entries) = fs::read_dir(&pid_dir) {
            for entry in entries.flatten() {
                if let Some(name) = entry.file_name().to_str() {
                    if name.ends_with(".pid") {
                        names.push(name.trim_end_matches(".pid").to_string());
                    }
                }
            }
        }

        names.sort();
        names
    }
}
