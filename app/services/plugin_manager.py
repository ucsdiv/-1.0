from typing import List

from app.plugins.base import PluginBase
from app.plugins.upstream_pansou import UpstreamPanSouPlugin
from app.plugins.pansearch import PanSearchPlugin
from app.plugins.qupansou import QuPanSouPlugin
from app.plugins.quarksoo import QuarksooPlugin
from app.plugins.qupanshe import QuPanShePlugin
from app.plugins.hunhepan import HunhepanPlugin
from app.plugins.panzun import PanzunPlugin


class PluginManager:
    def __init__(self):
        self._plugins: List[PluginBase] = []
        self.register(UpstreamPanSouPlugin())
        self.register(PanSearchPlugin())
        self.register(QuPanSouPlugin())
        self.register(QuarksooPlugin())
        self.register(QuPanShePlugin())
        self.register(HunhepanPlugin())
        self.register(PanzunPlugin())

    def register(self, plugin: PluginBase) -> None:
        self._plugins.append(plugin)

    @property
    def plugins(self) -> List[PluginBase]:
        return [p for p in self._plugins if p.enabled]

    def list_plugin_names(self) -> List[str]:
        return [p.name for p in self.plugins]

    def get_plugin(self, name: str) -> PluginBase | None:
        for p in self.plugins:
            if p.name == name:
                return p
        return None


plugin_manager = PluginManager()
