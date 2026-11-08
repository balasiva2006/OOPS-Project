"""Start with: python -m hmc_system."""
from . import create_app

if __name__ == '__main__':
    create_app().run(debug=True)
