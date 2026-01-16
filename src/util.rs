//! Environment variable substitution utilities
//! Supports $VAR, ${VAR}, ${VAR:-default}, ${VAR-default} syntax

use regex::Regex;
use std::collections::HashMap;

/// Substitute environment variables in a string
/// Supports:
/// - $VAR - simple variable
/// - ${VAR} - braced variable
/// - ${VAR:-default} - default if empty or unset
/// - ${VAR-default} - default if unset
pub fn substitute_env_vars(s: &str, env: &HashMap<String, String>) -> String {
    let simple_re = Regex::new(r"(?P<escape>\\)?\$(?P<var>[A-Za-z0-9_]+)").unwrap();
    let extended_re =
        Regex::new(r"(?P<escape>\\)?\$\{(?P<var>[A-Za-z0-9_]+)(?P<default_spec>(?P<op>:?-)(?P<default>[^}]*))?\}")
            .unwrap();

    let mut result = s.to_string();
    let mut prev = String::new();

    // Recursively substitute until no changes
    while prev != result {
        prev = result.clone();

        // First handle ${...} expressions
        result = extended_re
            .replace_all(&result, |caps: &regex::Captures| {
                // Check for escape
                if caps.name("escape").is_some() {
                    // Return the original without the backslash
                    let var = &caps["var"];
                    if let Some(default_spec) = caps.name("default_spec") {
                        format!("${{{}{}}}", var, default_spec.as_str())
                    } else {
                        format!("${{{}}}", var)
                    }
                } else {
                    let var_name = &caps["var"];

                    if caps.name("default_spec").is_some() {
                        let op = caps.name("op").map(|m| m.as_str()).unwrap_or("");
                        let default = caps.name("default").map(|m| m.as_str()).unwrap_or("");

                        // Recursively substitute in default value
                        let default_subst = substitute_env_vars(default, env);

                        match op {
                            ":-" => {
                                // Use default if empty or unset
                                match env.get(var_name) {
                                    Some(val) if !val.is_empty() => val.clone(),
                                    _ => default_subst,
                                }
                            }
                            "-" => {
                                // Use default only if unset
                                env.get(var_name).cloned().unwrap_or(default_subst)
                            }
                            _ => caps[0].to_string(),
                        }
                    } else {
                        env.get(var_name).cloned().unwrap_or_default()
                    }
                }
            })
            .to_string();

        // Then handle simple $VAR expressions
        result = simple_re
            .replace_all(&result, |caps: &regex::Captures| {
                if caps.name("escape").is_some() {
                    format!("${}", &caps["var"])
                } else {
                    let var_name = &caps["var"];
                    env.get(var_name).cloned().unwrap_or_default()
                }
            })
            .to_string();
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_var() {
        let mut env = HashMap::new();
        env.insert("HOME".to_string(), "/home/user".to_string());

        assert_eq!(substitute_env_vars("$HOME", &env), "/home/user");
        assert_eq!(substitute_env_vars("${HOME}", &env), "/home/user");
    }

    #[test]
    fn test_default_value() {
        let mut env = HashMap::new();
        env.insert("EXISTS".to_string(), "value".to_string());
        env.insert("EMPTY".to_string(), "".to_string());

        // ${VAR:-default} - use default if empty or unset
        assert_eq!(substitute_env_vars("${EXISTS:-default}", &env), "value");
        assert_eq!(substitute_env_vars("${EMPTY:-default}", &env), "default");
        assert_eq!(substitute_env_vars("${UNSET:-default}", &env), "default");

        // ${VAR-default} - use default only if unset
        assert_eq!(substitute_env_vars("${EXISTS-default}", &env), "value");
        assert_eq!(substitute_env_vars("${EMPTY-default}", &env), "");
        assert_eq!(substitute_env_vars("${UNSET-default}", &env), "default");
    }

    #[test]
    fn test_nested_default() {
        let mut env = HashMap::new();
        env.insert("FALLBACK".to_string(), "fallback_value".to_string());

        assert_eq!(
            substitute_env_vars("${UNSET:-$FALLBACK}", &env),
            "fallback_value"
        );
    }
}
