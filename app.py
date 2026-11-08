"""Compatibility launcher. Also available as: python -m hmc_system."""
from hmc_system import create_app

if __name__ == '__main__':
    create_app().run(debug=True)
