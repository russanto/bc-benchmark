import yaml

class DockerImagesNameResolver:
    class __DockerImagesNameResolver:
        def __init__(self):
            with open("dinr.yaml") as dinr_file:
                self.storage = yaml.load(dinr_file)
                #TODO check that when there is the registry key, also the image key is present
        
        def resolve(self, key):
            if isinstance(self.storage["images"][key], dict):
                return "{registry}/{image}".format_map(self.storage["images"][key])
            else:
                return "{0}/{1}".format(self.storage["registry"], self.storage["images"][key])
        
        def set_global_registry(self, registry):
            self.storage["registry"] = registry

        def set_key_registry(self, key, registry):
            if isinstance(self.storage["images"][key], dict):
                self.storage["images"][key]["registry"] = registry
            else:
                image = self.storage["images"][key]
                self.storage["images"][key] = {
                    "registry": registry,
                    "image": image
                }

    instance = None

    def __init__(self):
        if DockerImagesNameResolver.instance == None:
            DockerImagesNameResolver.instance = DockerImagesNameResolver.__DockerImagesNameResolver()

    def __getattr__(self, name):
        return getattr(self.instance, name)