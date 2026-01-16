//! Log management functionality for PMO

use colored::*;
use regex::Regex;
use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Seek, SeekFrom, Write};
use std::path::PathBuf;
use std::thread;
use std::time::Duration;

/// Log manager for service logs
pub struct LogManager {
    pub log_dir: PathBuf,
    pub default_tail_lines: usize,
}

impl LogManager {
    /// Create a new LogManager
    pub fn new(log_dir: PathBuf) -> Self {
        Self {
            log_dir,
            default_tail_lines: 15,
        }
    }

    /// Get log file paths for a service
    pub fn get_log_files(&self, service_name: &str, merge_logs: bool) -> HashMap<String, PathBuf> {
        let mut files = HashMap::new();

        if merge_logs {
            let merged = self.log_dir.join(format!("{}.log", service_name));
            files.insert("stdout".to_string(), merged.clone());
            files.insert("stderr".to_string(), merged);
        } else {
            files.insert(
                "stdout".to_string(),
                self.log_dir.join(format!("{}-out.log", service_name)),
            );
            files.insert(
                "stderr".to_string(),
                self.log_dir.join(format!("{}-error.log", service_name)),
            );
        }

        files
    }

    /// Get all possible log files for a service (for flushing)
    pub fn get_all_possible_log_files(&self, service_name: &str) -> Vec<PathBuf> {
        let mut files = Vec::new();

        // Merged logs
        files.extend(
            glob::glob(&format!("{}/{}.log*", self.log_dir.display(), service_name))
                .ok()
                .into_iter()
                .flatten()
                .filter_map(|r| r.ok()),
        );

        // Separate logs
        files.extend(
            glob::glob(&format!(
                "{}/{}-out.log*",
                self.log_dir.display(),
                service_name
            ))
            .ok()
            .into_iter()
            .flatten()
            .filter_map(|r| r.ok()),
        );

        files.extend(
            glob::glob(&format!(
                "{}/{}-error.log*",
                self.log_dir.display(),
                service_name
            ))
            .ok()
            .into_iter()
            .flatten()
            .filter_map(|r| r.ok()),
        );

        files
    }

    /// Flush (clear) log files
    pub fn flush_logs(
        &self,
        service_names: Option<&[String]>,
        running_services: &[String],
    ) -> HashMap<String, FlushResult> {
        let mut result = HashMap::new();
        let rotated_re = Regex::new(r"\.log\.\d+$").unwrap();

        match service_names {
            None => {
                // Flush all logs
                let mut deleted = 0;
                let mut cleared = 0;

                if let Ok(entries) = fs::read_dir(&self.log_dir) {
                    for entry in entries.flatten() {
                        let path = entry.path();
                        if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                            if !name.contains(".log") {
                                continue;
                            }

                            // Extract service name
                            let service_name = if name.contains("-out.log") {
                                name.split("-out.log").next()
                            } else if name.contains("-error.log") {
                                name.split("-error.log").next()
                            } else {
                                name.split(".log").next()
                            };

                            let is_rotated = rotated_re.is_match(name);

                            if let Some(service_name) = service_name {
                                if running_services.contains(&service_name.to_string())
                                    && !is_rotated
                                {
                                    // Clear content but keep file
                                    if let Ok(mut f) = File::create(&path) {
                                        let timestamp =
                                            chrono::Local::now().format("%Y-%m-%d %H:%M:%S");
                                        let _ =
                                            writeln!(f, "--- Log flushed at {} ---", timestamp);
                                        cleared += 1;
                                    }
                                } else {
                                    // Delete file
                                    if fs::remove_file(&path).is_ok() {
                                        deleted += 1;
                                    }
                                }
                            }
                        }
                    }
                }

                result.insert(
                    "_all".to_string(),
                    FlushResult {
                        deleted,
                        cleared,
                    },
                );
            }
            Some(names) => {
                for service_name in names {
                    let files = self.get_all_possible_log_files(service_name);
                    let mut deleted = 0;
                    let mut cleared = 0;

                    for path in files {
                        if path.exists() {
                            let is_rotated = path
                                .file_name()
                                .and_then(|n| n.to_str())
                                .map(|n| rotated_re.is_match(n))
                                .unwrap_or(false);

                            if running_services.contains(service_name) && !is_rotated {
                                if let Ok(mut f) = File::create(&path) {
                                    let timestamp =
                                        chrono::Local::now().format("%Y-%m-%d %H:%M:%S");
                                    let _ = writeln!(f, "--- Log flushed at {} ---", timestamp);
                                    cleared += 1;
                                }
                            } else {
                                if fs::remove_file(&path).is_ok() {
                                    deleted += 1;
                                }
                            }
                        }
                    }

                    result.insert(service_name.clone(), FlushResult { deleted, cleared });
                }
            }
        }

        result
    }

    /// Display recent log lines
    fn display_recent_logs(
        &self,
        log_files: &[(String, String, PathBuf, String)],
        lines: usize,
        hostname: Option<&str>,
    ) {
        for (service, log_type, log_path, service_id) in log_files {
            println!(
                "\n{} last {} lines:",
                log_path.display().to_string().dimmed(),
                lines
            );

            if let Ok(file) = File::open(log_path) {
                let reader = BufReader::new(file);
                let all_lines: Vec<_> = reader.lines().filter_map(|l| l.ok()).collect();
                let start = if all_lines.len() > lines {
                    all_lines.len() - lines
                } else {
                    0
                };

                for line in &all_lines[start..] {
                    let style = if log_type == "stderr" {
                        "red"
                    } else {
                        "green"
                    };

                    let prefix = if let Some(host) = hostname {
                        format!("{} | {}:{} | ", service_id, host, service)
                    } else {
                        format!("{} | {} | ", service_id, service)
                    };

                    match style {
                        "red" => println!("{}{}", prefix.red(), line),
                        _ => println!("{}{}", prefix.green(), line),
                    }
                }
            }
        }
    }

    /// Follow logs in real-time
    fn follow_logs(
        &self,
        log_files: &[(String, String, PathBuf, String)],
        hostname: Option<&str>,
    ) {
        let mut file_handlers: HashMap<(String, String), (File, String)> = HashMap::new();

        // Open all files and seek to end
        for (service, log_type, log_path, service_id) in log_files {
            if let Ok(mut file) = File::open(log_path) {
                let _ = file.seek(SeekFrom::End(0));
                file_handlers.insert(
                    (service.clone(), log_type.clone()),
                    (file, service_id.clone()),
                );
            }
        }

        println!("\n{}", "Following logs... (Press Ctrl+C to stop)".dimmed());

        loop {
            let mut has_new_data = false;

            for ((service, log_type), (file, service_id)) in file_handlers.iter_mut() {
                let mut reader = BufReader::new(file.try_clone().unwrap());
                let mut line = String::new();

                while reader.read_line(&mut line).unwrap_or(0) > 0 {
                    has_new_data = true;
                    let message = line.trim_end();

                    let style = if log_type == "stderr" {
                        "red"
                    } else {
                        "green"
                    };

                    let prefix = if let Some(host) = hostname {
                        format!("{} | {}:{} | ", service_id, host, service)
                    } else {
                        format!("{} | {} | ", service_id, service)
                    };

                    match style {
                        "red" => println!("{}{}", prefix.red(), message),
                        _ => println!("{}{}", prefix.green(), message),
                    }

                    line.clear();
                }
            }

            if !has_new_data {
                thread::sleep(Duration::from_millis(50));
            }
        }
    }

    /// Tail logs for services
    pub fn tail_logs(
        &self,
        service_names: &[String],
        follow: bool,
        lines: Option<usize>,
        service_id_map: Option<&HashMap<String, String>>,
        hostname: Option<&str>,
        service_configs: Option<&HashMap<String, bool>>, // service_name -> merge_logs
    ) {
        let lines = lines.unwrap_or(self.default_tail_lines);

        if service_names.is_empty() {
            println!("{} No services specified for log viewing.", "⚠️".yellow());
            return;
        }

        let default_id_map: HashMap<String, String> = service_names
            .iter()
            .enumerate()
            .map(|(i, n)| (n.clone(), i.to_string()))
            .collect();
        let id_map = service_id_map.unwrap_or(&default_id_map);

        // Collect log files
        let mut log_files: Vec<(String, String, PathBuf, String)> = Vec::new();

        for service in service_names {
            let merge_logs = service_configs
                .and_then(|c| c.get(service))
                .copied()
                .unwrap_or(false);

            let service_logs = self.get_log_files(service, merge_logs);
            let service_id = id_map.get(service).cloned().unwrap_or_default();

            if merge_logs {
                let log_path = service_logs.get("stdout").unwrap();
                if log_path.exists() {
                    log_files.push((
                        service.clone(),
                        "merged".to_string(),
                        log_path.clone(),
                        service_id,
                    ));
                } else {
                    let msg = if let Some(host) = hostname {
                        format!("No merged log found for {}:{}", host, service)
                    } else {
                        format!("No merged log found for {}", service)
                    };
                    println!("{} {}", "⚠️".yellow(), msg.yellow());
                }
            } else {
                for (log_type, log_path) in &service_logs {
                    if log_path.exists() {
                        log_files.push((
                            service.clone(),
                            log_type.clone(),
                            log_path.clone(),
                            service_id.clone(),
                        ));
                    } else {
                        let msg = if let Some(host) = hostname {
                            format!("No {} log found for {}:{}", log_type, host, service)
                        } else {
                            format!("No {} log found for {}", log_type, service)
                        };
                        println!("{} {}", "⚠️".yellow(), msg.yellow());
                    }
                }
            }
        }

        if log_files.is_empty() {
            println!(
                "{} No log files found for specified services.",
                "⚠️".yellow()
            );
            return;
        }

        if follow {
            self.display_recent_logs(&log_files, lines, hostname);
            self.follow_logs(&log_files, hostname);
        } else {
            self.display_recent_logs(&log_files, lines, hostname);
        }
    }
}

/// Result of flush operation
#[derive(Debug, Clone)]
pub struct FlushResult {
    pub deleted: u32,
    pub cleared: u32,
}

/// Print service status table
pub fn print_service_table(services: &[ServiceTableRow]) {
    use comfy_table::{Cell, Color as TableColor, Table};

    let mut table = Table::new();
    table.set_header(vec![
        "id", "name", "pid", "uptime", "status", "cpu", "mem", "gpu mem", "gpu id", "user",
    ]);

    let user = std::env::var("USER").unwrap_or_else(|_| "unknown".to_string());

    for service in services {
        let status_color = if service.status == "running" {
            TableColor::Green
        } else {
            TableColor::DarkGrey
        };

        table.add_row(vec![
            Cell::new(&service.id).fg(status_color),
            Cell::new(&service.name).fg(status_color),
            Cell::new(&service.pid).fg(status_color),
            Cell::new(&service.uptime).fg(status_color),
            Cell::new(&service.status).fg(status_color),
            Cell::new(&service.cpu).fg(status_color),
            Cell::new(&service.memory).fg(status_color),
            Cell::new(&service.gpu_memory).fg(status_color),
            Cell::new(&service.gpu_id).fg(status_color),
            Cell::new(&user).fg(status_color),
        ]);
    }

    println!("{table}");
    println!();
}

/// Row data for service table
#[derive(Debug, Clone)]
pub struct ServiceTableRow {
    pub id: String,
    pub name: String,
    pub pid: String,
    pub uptime: String,
    pub status: String,
    pub cpu: String,
    pub memory: String,
    pub gpu_memory: String,
    pub gpu_id: String,
    pub restarts: String,
}

/// Print info message
pub fn print_info(message: &str) {
    println!("{} {}", "ℹ️".green(), message.green());
}

/// Print warning message
pub fn print_warning(message: &str) {
    println!("{} {}", "⚠️".yellow(), message.yellow());
}

/// Print error message
pub fn print_error(message: &str) {
    println!("{} {}", "❌".red(), message.red());
}

/// Print success message
pub fn print_success(message: &str) {
    println!("{} {}", "✅".green(), message.green());
}
