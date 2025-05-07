import pytest
from pmo.util import substitute_env_vars

def test_basic_var():
    env = {'USER': 'alice', 'HOME': '/home/alice'}
    assert substitute_env_vars('hello $USER', env) == 'hello alice'
    assert substitute_env_vars('home=${HOME}', env) == 'home=/home/alice'
    assert substitute_env_vars('unset=$UNSET', env) == 'unset='

def test_default():
    env = {'USER': 'alice'}
    assert substitute_env_vars('user=${USER:-default}', env) == 'user=alice'
    assert substitute_env_vars('unset=${UNSET:-default}', env) == 'unset=default'
    assert substitute_env_vars('unset=${UNSET-default}', env) == 'unset=default'
    assert substitute_env_vars('empty=${EMPTY:-def}', {'EMPTY': ''}) == 'empty=def'
    assert substitute_env_vars('empty=${EMPTY-def}', {'EMPTY': ''}) == 'empty='

def test_nested_default():
    env = {}
    assert substitute_env_vars('foo=${BAR:-$USER}', {'USER': 'bob'}) == 'foo=bob'
    assert substitute_env_vars('foo=${BAR:-${USER:-nobody}}', {}) == 'foo=nobody'

def test_escape():
    env = {'USER': 'alice'}
    assert substitute_env_vars(r'\$USER', env) == r'\$USER'
    assert substitute_env_vars(r'\${USER}', env) == r'\${USER}'
