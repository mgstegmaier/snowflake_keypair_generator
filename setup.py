#!/usr/bin/env python3

import subprocess
import sys
import pkg_resources

def check_requirements():
    """Check if required packages are installed and install if missing."""
    required = {'flask', 'werkzeug', 'python-dotenv'}
    installed = {pkg.key for pkg in pkg_resources.working_set}
    missing = required - installed

    if missing:
        print("Installing required packages...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', *missing])
            print("✅ All required packages installed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error installing packages: {e}")
            sys.exit(1)
    else:
        print("✅ All required packages are already installed!")

if __name__ == '__main__':
    check_requirements() 