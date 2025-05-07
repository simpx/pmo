import re
from typing import Mapping, Optional

def substitute_env_vars(s: str, env: Optional[Mapping[str, str]] = None) -> str:
    """
    替换字符串中的 $VAR, ${VAR}, ${VAR:-default}, ${VAR-default} 变量。
    env: 用于替换的变量字典，默认为os.environ。
    """
    import os
    if env is None:
        env = os.environ

    _simple_re = re.compile(r'(?<!\\)\$([A-Za-z0-9_]+)')
    _extended_re = re.compile(r'(?<!\\)\$\{([A-Za-z0-9_]+)((:?-)([^}]+))?\}')

    def _resolve_var(var_name, default=None):
        return env.get(var_name, default)

    def _repl_simple_env_var(m):
        var_name = m.group(1)
        return _resolve_var(var_name, '')

    def _repl_extended_env_var(m):
        var_name = m.group(1)
        default_spec = m.group(2)
        if default_spec:
            default = m.group(4)
            # 递归替换 default
            default = substitute_env_vars(default, env)
            if m.group(3) == ':-':
                env_var = _resolve_var(var_name)
                if env_var:
                    return env_var
                else:
                    return default
            elif m.group(3) == '-':
                return _resolve_var(var_name, default)
            else:
                return m.group(0)
        else:
            return _resolve_var(var_name, '')

    # 递归替换直到不再变化，支持嵌套
    prev = None
    result = s
    # 先处理大括号表达式，再处理简单表达式，递归直到不变
    while prev != result:
        prev = result
        # 先处理 ${...}，再处理 $VAR
        b = _extended_re.sub(_repl_extended_env_var, result)
        a = _simple_re.sub(_repl_simple_env_var, b)
        result = a
    return result
