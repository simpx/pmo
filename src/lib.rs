//! PMO - A simple process manager
//!
//! This module provides both a native Rust API and Python bindings via PyO3.

pub mod cli;
pub mod logs;
pub mod service;
pub mod util;

use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

/// Python wrapper for ServiceManager
#[pyclass(name = "ServiceManager")]
pub struct PyServiceManager {
    inner: service::ServiceManager,
}

#[pymethods]
impl PyServiceManager {
    #[new]
    #[pyo3(signature = (config_path="pmo.yml", pmo_dir=".pmo"))]
    fn new(config_path: &str, pmo_dir: &str) -> PyResult<Self> {
        let inner = service::ServiceManager::new(config_path, pmo_dir)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(Self { inner })
    }

    /// Get the configuration file path
    #[getter]
    fn config_path(&self) -> String {
        self.inner.config_path.to_string_lossy().to_string()
    }

    /// Get the log directory path
    #[getter]
    fn log_dir(&self) -> String {
        self.inner.log_dir.to_string_lossy().to_string()
    }

    /// Get list of configured service names
    fn get_service_names(&self) -> Vec<String> {
        self.inner.get_service_names()
    }

    /// Get list of running services
    fn get_running_services(&self) -> Vec<String> {
        self.inner.get_running_services()
    }

    /// Check if a service is running
    fn is_running(&self, service_name: &str) -> bool {
        self.inner.is_running(service_name)
    }

    /// Get PID for a running service
    fn get_service_pid(&self, service_name: &str) -> Option<i32> {
        self.inner.get_service_pid(service_name)
    }

    /// Get uptime in seconds
    fn get_uptime(&self, service_name: &str) -> Option<f64> {
        self.inner.get_uptime(service_name)
    }

    /// Format uptime to human-readable string
    #[pyo3(signature = (uptime_seconds=None))]
    fn format_uptime(&self, uptime_seconds: Option<f64>) -> String {
        self.inner.format_uptime(uptime_seconds)
    }

    /// Start a service
    #[pyo3(signature = (service_name, dry_run=false))]
    fn start(&mut self, service_name: &str, dry_run: bool) -> PyResult<bool> {
        self.inner
            .start(service_name, dry_run)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    }

    /// Stop a service
    #[pyo3(signature = (service_name, timeout=5))]
    fn stop(&mut self, service_name: &str, timeout: u64) -> PyResult<bool> {
        self.inner
            .stop(service_name, timeout)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    }

    /// Restart a service
    fn restart(&mut self, service_name: &str) -> PyResult<bool> {
        self.inner
            .restart(service_name)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    }

    /// Get restart count
    fn get_restarts_count(&self, service_name: &str) -> u32 {
        self.inner.get_restarts_count(service_name)
    }

    /// Get process stats as dict
    fn get_process_stats<'py>(&self, py: Python<'py>, service_name: &str) -> PyResult<Bound<'py, PyDict>> {
        let stats = self.inner.get_process_stats(service_name);
        let dict = PyDict::new_bound(py);
        dict.set_item("name", stats.name)?;
        dict.set_item("pid", stats.pid)?;
        dict.set_item("running", stats.running)?;
        dict.set_item("uptime", stats.uptime)?;
        dict.set_item("cpu_percent", stats.cpu_percent)?;
        dict.set_item("memory_mb", stats.memory_mb)?;
        dict.set_item("memory_percent", stats.memory_percent)?;
        dict.set_item("restarts", stats.restarts)?;
        dict.set_item("gpu_memory", stats.gpu_memory)?;
        dict.set_item("gpu_id", stats.gpu_id)?;
        Ok(dict)
    }

    /// Format CPU percent
    #[pyo3(signature = (cpu=None))]
    fn format_cpu_percent(&self, cpu: Option<f64>) -> String {
        self.inner.format_cpu_percent(cpu)
    }

    /// Format memory
    #[pyo3(signature = (memory_mb=None))]
    fn format_memory(&self, memory_mb: Option<f64>) -> String {
        self.inner.format_memory(memory_mb)
    }

    /// Get all hostnames with services
    fn get_all_hostnames(&self) -> Vec<String> {
        self.inner.get_all_hostnames()
    }

    /// Get remote log directory
    fn get_remote_log_dir(&self, hostname: &str) -> String {
        self.inner
            .get_remote_log_dir(hostname)
            .to_string_lossy()
            .to_string()
    }

    /// Get remote service names
    fn get_remote_service_names(&self, hostname: &str) -> Vec<String> {
        self.inner.get_remote_service_names(hostname)
    }

    /// Get services configuration
    fn get_services<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let dict = PyDict::new_bound(py);
        for (name, config) in &self.inner.services {
            let service_dict = PyDict::new_bound(py);
            service_dict.set_item("cmd", &config.cmd)?;
            service_dict.set_item("cwd", &config.cwd)?;

            let env_dict = PyDict::new_bound(py);
            for (k, v) in &config.env {
                env_dict.set_item(k, v)?;
            }
            service_dict.set_item("env", &env_dict)?;
            service_dict.set_item("merge_logs", config.merge_logs)?;

            dict.set_item(name, &service_dict)?;
        }
        Ok(dict)
    }
}

/// Python wrapper for LogManager
#[pyclass(name = "LogManager")]
pub struct PyLogManager {
    inner: logs::LogManager,
}

#[pymethods]
impl PyLogManager {
    #[new]
    fn new(log_dir: &str) -> Self {
        Self {
            inner: logs::LogManager::new(std::path::PathBuf::from(log_dir)),
        }
    }

    /// Flush logs
    #[pyo3(signature = (service_names=None, running_services=None))]
    fn flush_logs<'py>(
        &self,
        py: Python<'py>,
        service_names: Option<Vec<String>>,
        running_services: Option<Vec<String>>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let running = running_services.unwrap_or_default();
        let result = self
            .inner
            .flush_logs(service_names.as_deref(), &running);

        let dict = PyDict::new_bound(py);
        for (name, r) in result {
            let r_dict = PyDict::new_bound(py);
            r_dict.set_item("deleted", r.deleted)?;
            r_dict.set_item("cleared", r.cleared)?;
            dict.set_item(name, &r_dict)?;
        }
        Ok(dict)
    }

    /// Tail logs (blocking, use with caution in Python)
    #[pyo3(signature = (service_names, follow=true, lines=None, service_id_map=None, hostname=None, service_configs=None))]
    fn tail_logs(
        &self,
        service_names: Vec<String>,
        follow: bool,
        lines: Option<usize>,
        service_id_map: Option<HashMap<String, String>>,
        hostname: Option<&str>,
        service_configs: Option<HashMap<String, bool>>,
    ) {
        self.inner.tail_logs(
            &service_names,
            follow,
            lines,
            service_id_map.as_ref(),
            hostname,
            service_configs.as_ref(),
        );
    }
}

/// Substitute environment variables in a string
#[pyfunction]
#[pyo3(signature = (s, env=None))]
fn substitute_env_vars(s: &str, env: Option<HashMap<String, String>>) -> String {
    let env = env.unwrap_or_else(|| std::env::vars().collect());
    util::substitute_env_vars(s, &env)
}

/// Run the CLI
#[pyfunction]
fn main() -> i32 {
    cli::run().unwrap_or(1)
}

/// Get version
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// PMO Python module
#[pymodule]
fn _pmo_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyServiceManager>()?;
    m.add_class::<PyLogManager>()?;
    m.add_function(wrap_pyfunction!(substitute_env_vars, m)?)?;
    m.add_function(wrap_pyfunction!(main, m)?)?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
