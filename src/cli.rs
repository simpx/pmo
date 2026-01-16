//! Command-line interface for PMO process manager

use crate::logs::{
    print_error, print_info, print_service_table, print_success, print_warning,
    LogManager, ServiceTableRow,
};
use crate::service::ServiceManager;
use anyhow::Result;
use clap::{Parser, Subcommand};
use colored::*;
use std::collections::HashMap;

/// PMO - Modern process manager
#[derive(Parser)]
#[command(name = "pmo")]
#[command(about = "🔧 PMO - Modern process manager", long_about = None)]
pub struct Cli {
    /// Config file path
    #[arg(short = 'f', long, default_value = "pmo.yml")]
    pub config: String,

    #[command(subcommand)]
    pub command: Option<Commands>,
}

#[derive(Subcommand)]
pub enum Commands {
    /// 🟢 Start services
    Start {
        /// Service names or IDs (multiple allowed) or "all"
        #[arg(value_name = "SERVICE")]
        service: Vec<String>,
        /// Show commands without executing
        #[arg(long)]
        dry_run: bool,
    },
    /// ℹ️ Show commands without running (alias for start --dry-run)
    DryRun {
        /// Service names or IDs (multiple allowed) or "all"
        #[arg(value_name = "SERVICE")]
        service: Vec<String>,
    },
    /// 🔴 Stop services
    Stop {
        /// Service names or IDs (multiple allowed) or "all"
        #[arg(value_name = "SERVICE")]
        service: Vec<String>,
    },
    /// 🔄 Restart services
    Restart {
        /// Service names or IDs (multiple allowed) or "all"
        #[arg(value_name = "SERVICE")]
        service: Vec<String>,
    },
    /// 📝 View service logs
    #[command(alias = "log")]
    Logs {
        /// Service names or IDs (multiple allowed) or "all"
        #[arg(value_name = "SERVICE", default_value = "all")]
        service: Vec<String>,
        /// Do not follow logs in real-time
        #[arg(short = 'n', long)]
        no_follow: bool,
        /// Number of lines to show initially
        #[arg(short = 'l', long)]
        lines: Option<usize>,
    },
    /// 📝 Clear service logs
    Flush {
        /// Service names or IDs (multiple allowed) or "all"
        #[arg(value_name = "SERVICE", default_value = "all")]
        service: Vec<String>,
    },
    /// List services
    Ls,
    /// ℹ️ Show detailed service status
    #[command(alias = "st")]
    Status {
        /// Service names or IDs (multiple allowed) or "all"
        #[arg(value_name = "SERVICE", default_value = "all")]
        service: Vec<String>,
    },
}

/// Resolve service ID or name to actual service name
fn resolve_service_id(manager: &ServiceManager, service_id: &str) -> Option<String> {
    if service_id == "all" {
        return Some("all".to_string());
    }

    // Try to parse as numeric ID
    if let Ok(id_num) = service_id.parse::<usize>() {
        let names = manager.get_service_names();
        if id_num >= 1 && id_num <= names.len() {
            return Some(names[id_num - 1].clone());
        }
        print_error(&format!("Invalid service ID: {}", service_id));
        return None;
    }

    // Treat as service name
    if manager.services.contains_key(service_id) {
        return Some(service_id.to_string());
    }

    print_error(&format!("Service not found: '{}'", service_id));
    None
}

/// Resolve multiple service specifications to service names
fn resolve_multiple_services(manager: &ServiceManager, service_specs: &[String]) -> Vec<String> {
    if service_specs.is_empty() {
        return vec![];
    }

    if service_specs.contains(&"all".to_string()) {
        return manager.get_service_names();
    }

    let mut resolved = Vec::new();
    for spec in service_specs {
        if let Some(name) = resolve_service_id(manager, spec) {
            if !resolved.contains(&name) {
                resolved.push(name);
            }
        }
    }
    resolved
}

/// Show prompt when no service specified
fn show_service_prompt(manager: &ServiceManager, command: &str) {
    print_warning(&format!(
        "Please specify a service name or 'all' to {} all services.",
        command
    ));
    print_info(&format!(
        "Usage: pmo {} <service-name> or pmo {} all",
        command, command
    ));
    let names = manager.get_service_names();
    if !names.is_empty() {
        print_info(&format!("Available services: {}", names.join(", ")));
    }
}

/// Handle start command
pub fn handle_start(
    manager: &mut ServiceManager,
    service_specs: &[String],
    dry_run: bool,
) -> Result<bool> {
    if service_specs.is_empty() {
        show_service_prompt(manager, "start");
        return Ok(false);
    }

    let service_names = resolve_multiple_services(manager, service_specs);
    if service_names.is_empty() {
        print_warning("No valid services specified for starting.");
        return Ok(false);
    }

    if service_specs.contains(&"all".to_string()) {
        if dry_run {
            println!(
                "{}",
                "ℹ️ Commands to execute (dry run):".cyan()
            );
        } else {
            println!("{}", "🟢 Starting all services...".green());
        }
    } else if service_names.len() > 1 {
        if dry_run {
            println!(
                "{}",
                "ℹ️ Commands to execute for selected services (dry run):".cyan()
            );
        } else {
            println!("{}", "🟢 Starting selected services...".green());
        }
    }

    let mut success = true;
    for name in &service_names {
        match manager.start(name, dry_run) {
            Ok(true) => {
                if !dry_run {
                    print_success(&format!("Service '{}' started", name));
                }
            }
            Ok(false) | Err(_) => {
                print_error(&format!("Failed to start '{}'", name));
                success = false;
            }
        }
    }

    if service_names.len() > 1 {
        if success && !dry_run {
            print_success("All specified services started successfully!");
        } else if !success && !dry_run {
            print_warning("Some services failed to start, check logs for details.");
        }
    }

    Ok(success)
}

/// Handle stop command
pub fn handle_stop(manager: &mut ServiceManager, service_specs: &[String]) -> Result<bool> {
    if service_specs.is_empty() {
        show_service_prompt(manager, "stop");
        return Ok(false);
    }

    let service_names = if service_specs.contains(&"all".to_string()) {
        let running = manager.get_running_services();
        if running.is_empty() {
            println!("{}", "ℹ️ No services are running.".dimmed());
            return Ok(true);
        }
        println!("{}", "🔴 Stopping all services...".yellow());
        running
    } else {
        let mut names = Vec::new();
        for spec in service_specs {
            if let Some(name) = resolve_service_id(manager, spec) {
                if manager.is_running(&name) {
                    if !names.contains(&name) {
                        names.push(name);
                    }
                } else {
                    println!(
                        "{}",
                        format!("ℹ️ Service '{}' is not running.", name).dimmed()
                    );
                }
            }
        }

        if names.is_empty() {
            print_warning("No running services specified for stopping.");
            return Ok(true);
        }

        if names.len() > 1 {
            println!("{}", "🔴 Stopping selected services...".yellow());
        }
        names
    };

    let mut success = true;
    for name in &service_names {
        match manager.stop(name, 5) {
            Ok(true) => {
                println!("{}", format!("⛔ Service '{}' stopped", name).bright_black());
            }
            Ok(false) | Err(_) => {
                print_error(&format!("Failed to stop '{}'", name));
                success = false;
            }
        }
    }

    if service_names.len() > 1 {
        if success {
            println!(
                "\n{}",
                "⛔ All specified services stopped successfully!".yellow()
            );
        } else {
            print_warning("Some services failed to stop, check logs for details.");
        }
    }

    Ok(success)
}

/// Handle restart command
pub fn handle_restart(manager: &mut ServiceManager, service_specs: &[String]) -> Result<bool> {
    if service_specs.is_empty() {
        show_service_prompt(manager, "restart");
        return Ok(false);
    }

    let service_names = resolve_multiple_services(manager, service_specs);
    if service_names.is_empty() {
        print_warning("No valid services specified for restarting.");
        return Ok(false);
    }

    if service_specs.contains(&"all".to_string()) {
        println!("{}", "🔄 Restarting all services...".magenta());
    } else if service_names.len() > 1 {
        println!("{}", "🔄 Restarting selected services...".magenta());
    }

    let mut success = true;
    for name in &service_names {
        match manager.restart(name) {
            Ok(true) => {
                println!("{}", format!("✅ Service '{}' restarted", name).magenta());
            }
            Ok(false) | Err(_) => {
                print_error(&format!("Failed to restart '{}'", name));
                success = false;
            }
        }
    }

    if service_names.len() > 1 {
        if success {
            print_success("All specified services restarted successfully!");
        } else {
            print_warning("Some services failed to restart, check logs for details.");
        }
    }

    Ok(success)
}

/// Handle log command
pub fn handle_log(
    manager: &ServiceManager,
    log_manager: &LogManager,
    service_specs: &[String],
    follow: bool,
    lines: Option<usize>,
) -> Result<bool> {
    let service_specs = if service_specs.is_empty() {
        vec!["all".to_string()]
    } else {
        service_specs.to_vec()
    };

    let lines = lines.unwrap_or_else(|| {
        if service_specs == vec!["all".to_string()] {
            15
        } else {
            30
        }
    });

    let service_names = resolve_multiple_services(manager, &service_specs);

    // Create service ID map
    let all_services = manager.get_service_names();
    let service_id_map: HashMap<String, String> = all_services
        .iter()
        .enumerate()
        .map(|(i, n)| (n.clone(), (i + 1).to_string()))
        .collect();

    // Create merge_logs config map
    let merge_logs_map: HashMap<String, bool> = manager
        .services
        .iter()
        .map(|(k, v)| (k.clone(), v.merge_logs))
        .collect();

    log_manager.tail_logs(
        &service_names,
        follow,
        Some(lines),
        Some(&service_id_map),
        None,
        Some(&merge_logs_map),
    );

    Ok(true)
}

/// Handle flush command
pub fn handle_flush(
    manager: &ServiceManager,
    log_manager: &LogManager,
    service_specs: &[String],
) -> Result<bool> {
    let service_specs = if service_specs.is_empty() {
        vec!["all".to_string()]
    } else {
        service_specs.to_vec()
    };

    let running_services = manager.get_running_services();

    if service_specs.contains(&"all".to_string()) {
        println!("{}", "📝 Flushing all logs...".yellow());
        let result = log_manager.flush_logs(None, &running_services);
        if let Some(r) = result.get("_all") {
            if r.deleted > 0 || r.cleared > 0 {
                if r.deleted > 0 {
                    print_success(&format!(
                        "Successfully deleted {} log files for non-running services",
                        r.deleted
                    ));
                }
                if r.cleared > 0 {
                    print_success(&format!(
                        "Successfully cleared content of {} log files for running services",
                        r.cleared
                    ));
                }
            } else {
                print_warning("No log files found to flush");
            }
        }
    } else {
        let service_names = resolve_multiple_services(manager, &service_specs);

        if service_names.len() > 1 {
            println!("{}", "📝 Flushing logs for selected services...".yellow());
        }

        let result = log_manager.flush_logs(Some(&service_names), &running_services);

        for name in &service_names {
            if let Some(r) = result.get(name) {
                if r.deleted > 0 {
                    print_success(&format!(
                        "Successfully deleted {} log files for '{}'",
                        r.deleted, name
                    ));
                }
                if r.cleared > 0 {
                    print_success(&format!(
                        "Successfully cleared content of {} log files for '{}'",
                        r.cleared, name
                    ));
                }
                if r.deleted == 0 && r.cleared == 0 {
                    print_warning(&format!("No log files found for '{}'", name));
                }
            } else {
                print_warning(&format!("No log files found for '{}'", name));
            }
        }
    }

    Ok(true)
}

/// Handle list command
pub fn handle_list(manager: &ServiceManager) -> Result<bool> {
    let service_names = manager.get_service_names();

    if service_names.is_empty() {
        print_warning("No services defined in config.");
        return Ok(true);
    }

    let mut rows: Vec<ServiceTableRow> = Vec::new();

    for (i, name) in service_names.iter().enumerate() {
        let running = manager.is_running(name);
        let pid = manager.get_service_pid(name);
        let uptime = if running {
            manager.format_uptime(manager.get_uptime(name))
        } else {
            "0".to_string()
        };

        let stats = manager.get_process_stats(name);

        rows.push(ServiceTableRow {
            id: (i + 1).to_string(),
            name: name.clone(),
            pid: pid.map(|p| p.to_string()).unwrap_or_else(|| "0".to_string()),
            uptime,
            status: if running {
                "running".to_string()
            } else {
                "stopped".to_string()
            },
            cpu: manager.format_cpu_percent(stats.cpu_percent),
            memory: manager.format_memory(stats.memory_mb),
            gpu_memory: stats.gpu_memory.unwrap_or_else(|| "-".to_string()),
            gpu_id: stats.gpu_id.unwrap_or_else(|| "-".to_string()),
            restarts: stats.restarts.to_string(),
        });
    }

    print_service_table(&rows);

    println!(
        "{}",
        format!("Config: {}", manager.config_path.display()).dimmed()
    );
    println!(
        "{}",
        format!(
            "Running: {}/{}",
            manager.get_running_services().len(),
            service_names.len()
        )
        .dimmed()
    );

    let hostnames = manager.get_all_hostnames();
    if !hostnames.is_empty() {
        println!(
            "{}",
            format!("Hostnames with services: {}", hostnames.join(", ")).dimmed()
        );
    }
    println!();

    Ok(true)
}

/// Handle status command
pub fn handle_status(manager: &ServiceManager, service_specs: &[String]) -> Result<bool> {
    let service_specs = if service_specs.is_empty() {
        vec!["all".to_string()]
    } else {
        service_specs.to_vec()
    };

    let service_names = resolve_multiple_services(manager, &service_specs);
    if service_names.is_empty() {
        print_warning("No valid services specified for status.");
        return Ok(false);
    }

    for name in &service_names {
        print_service_status(manager, name);
    }

    Ok(true)
}

/// Print detailed status for a single service
fn print_service_status(manager: &ServiceManager, service_name: &str) {
    let config = manager.services.get(service_name);
    let running = manager.is_running(service_name);
    let pid = manager.get_service_pid(service_name);
    let stats = manager.get_process_stats(service_name);

    println!("\n{}", "═".repeat(60).cyan());
    println!("{}", format!("  Service Info: {}", service_name).cyan().bold());
    println!("{}", "═".repeat(60).cyan());

    println!(
        "  {:<15} {}",
        "Service Name:".cyan(),
        service_name
    );
    println!(
        "  {:<15} {}",
        "Status:".cyan(),
        if running {
            "🟢 Running".green().to_string()
        } else {
            "🔴 Stopped".red().to_string()
        }
    );
    println!(
        "  {:<15} {}",
        "Config Path:".cyan(),
        manager.config_path.display()
    );

    if let Some(config) = config {
        println!("  {:<15} {}", "Command:".cyan(), config.cmd);
        if let Some(ref cwd) = config.cwd {
            println!("  {:<15} {}", "Working Dir:".cyan(), cwd);
        }
    }

    if let Some(p) = pid {
        println!("  {:<15} {}", "Main PID:".cyan(), p);
    }

    println!(
        "  {:<15} {}",
        "Uptime:".cyan(),
        manager.format_uptime(manager.get_uptime(service_name))
    );
    println!(
        "  {:<15} {}",
        "CPU:".cyan(),
        manager.format_cpu_percent(stats.cpu_percent)
    );
    println!(
        "  {:<15} {}",
        "Memory:".cyan(),
        manager.format_memory(stats.memory_mb)
    );
    println!(
        "  {:<15} {}",
        "Restarts:".cyan(),
        stats.restarts
    );

    if let Some(gpu_mem) = &stats.gpu_memory {
        println!("  {:<15} {}", "GPU Memory:".cyan(), gpu_mem);
    }
    if let Some(gpu_id) = &stats.gpu_id {
        println!("  {:<15} {}", "GPU ID:".cyan(), gpu_id);
    }

    println!();
}

/// Main entry point
pub fn run() -> Result<i32> {
    let cli = Cli::parse();

    let Some(command) = cli.command else {
        Cli::parse_from(["pmo", "--help"]);
        return Ok(1);
    };

    let mut manager = match ServiceManager::new(&cli.config, ".pmo") {
        Ok(m) => m,
        Err(e) => {
            print_error(&format!("Error loading config file: {}", e));
            return Ok(1);
        }
    };

    let log_manager = LogManager::new(manager.log_dir.clone());

    let result = match command {
        Commands::Start { service, dry_run } => handle_start(&mut manager, &service, dry_run),
        Commands::DryRun { service } => {
            let service = if service.is_empty() {
                vec!["all".to_string()]
            } else {
                service
            };
            handle_start(&mut manager, &service, true)
        }
        Commands::Stop { service } => handle_stop(&mut manager, &service),
        Commands::Restart { service } => handle_restart(&mut manager, &service),
        Commands::Logs {
            service,
            no_follow,
            lines,
        } => handle_log(&manager, &log_manager, &service, !no_follow, lines),
        Commands::Flush { service } => handle_flush(&manager, &log_manager, &service),
        Commands::Ls => handle_list(&manager),
        Commands::Status { service } => handle_status(&manager, &service),
    };

    match result {
        Ok(true) => Ok(0),
        Ok(false) => Ok(1),
        Err(e) => {
            print_error(&format!("Error executing command: {}", e));
            Ok(1)
        }
    }
}
