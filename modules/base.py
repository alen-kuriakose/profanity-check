from abc import ABC, abstractmethod

class ContentModerationModule(ABC):
    def __init__(self, config):
        self.config = config

    @abstractmethod
    def analyze(self, content_id, content_path):
        pass

    @abstractmethod
    def get_capabilities(self):
        pass

    @abstractmethod
    def get_status(self):
        pass
