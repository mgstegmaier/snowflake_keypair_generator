# Snowflake Key Pair Generator

A web-based application for generating Snowflake key pairs with a user-friendly interface.

## Features
- Generate encrypted or unencrypted key pairs
- Automatic file downloads
- Copy Snowflake ALTER USER command to clipboard
- Option to create processed key file
- Secure passphrase storage
- Automatic cleanup of temporary files
- Modern, responsive UI

## Installation

### Quick Start
Simply run:
```bash
python3 setup.py
python3 app.py
```
This will:
1. Check and install required packages if needed
2. Start the application
3. Automatically open your default web browser

### Manual Installation
If you prefer to install manually:

1. Create a virtual environment (optional but recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python3 app.py
```

2. The application will automatically open in your default web browser at `http://localhost:5001`

3. Follow the on-screen instructions to generate your key pair:
   - Enter your Snowflake username
   - Choose whether to encrypt the private key
   - Enter a passphrase if encryption is enabled
   - Choose whether to create a processed key file
   - Click "Generate Key Pair"
   - Download the generated files using the download buttons

## Requirements
- Python 3.6 or higher
- OpenSSL (for key generation)
- Modern web browser

## Security Notes
- Generated keys are stored in a temporary directory
- Files are automatically cleaned up after use
- Passphrases are never stored on disk
- All operations are performed locally on your machine
