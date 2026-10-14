from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import sys
from unittest.mock import Mock


def test_plugin_registers_bundled_operating_guide():
    root = Path(__file__).resolve().parents[1]
    name = '_notion_plugin_guide_test'
    spec = spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        ctx = Mock()
        module.register(ctx)
        assert ctx.register_skill.call_count == 2
        names = set()
        for call in ctx.register_skill.call_args_list:
            kwargs = call.kwargs
            names.add(kwargs['name'])
            path = Path(kwargs['path'])
            assert path == root / 'skills' / kwargs['name'] / 'SKILL.md'
            assert path.is_file()
            assert len(kwargs['description']) <= 60
            assert kwargs['description'].endswith('.')
        assert names == {'use', 'profile-setup'}
    finally:
        for key in list(sys.modules):
            if key == name or key.startswith(name + '.'):
                sys.modules.pop(key)
