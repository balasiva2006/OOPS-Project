"""Hall Management Centre: a Python package organised by responsibility."""

def create_app(test_config=None):
    """Create the Flask application without starting a server on import."""
    from .web.application import create_app as factory
    return factory(test_config)

__all__ = ['create_app']
