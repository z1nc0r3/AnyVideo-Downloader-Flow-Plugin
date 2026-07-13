import sys
import os

plugindir = os.path.abspath(os.path.dirname(__file__))
for path in (
    plugindir,
    os.path.join(plugindir, "lib"),
    os.path.join(plugindir, "plugin"),
):
    if path not in sys.path:
        sys.path.insert(0, path)


if __name__ == "__main__":
    from plugin.main import plugin
    plugin.run()
