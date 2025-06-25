import importlib.resources as resources


def get_resource_path(path, resource_name):
    # Access the resources directory using importlib.resources.path
    with resources.path(path, resource_name) as resource_path:
        return str(resource_path)  # Convert to string for path use
