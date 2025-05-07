import pytest
import yaml
from pathlib import Path
from pmo.service import ServiceManager

EXTENDS_YML = """
http-server-1:
  cmd: python -m http.server ${PORT:-8000}

http-server-2:
  extends: http-server-1
  env:
    PORT: 8001

udp-server:
  extends: http-server-2
  cmd: nc -l -4 -u -p ${PORT}
"""

def test_extends_inheritance(tmp_path):
    config_path = tmp_path / "extends.yml"
    config_path.write_text(EXTENDS_YML)
    manager = ServiceManager(config_path=str(config_path))
    services = manager.services

    # http-server-1
    assert services["http-server-1"]["cmd"] == "python -m http.server ${PORT:-8000}"
    assert "env" not in services["http-server-1"]

    # http-server-2 继承 http-server-1
    assert services["http-server-2"]["cmd"] == "python -m http.server ${PORT:-8000}"
    assert services["http-server-2"]["env"]["PORT"] == 8001

    # udp-server 继承 http-server-2, 覆盖 cmd
    assert services["udp-server"]["cmd"] == "nc -l -4 -u -p ${PORT}"
    assert services["udp-server"]["env"]["PORT"] == 8001
