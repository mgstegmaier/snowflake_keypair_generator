from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import os
import subprocess
import tempfile
from werkzeug.utils import secure_filename
import json
from pathlib import Path
import shutil
import webbrowser
from threading import Timer

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['UPLOAD_FOLDER'] = os.path.join(tempfile.gettempdir(), 'snowflake_keys')

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def open_browser():
    """Open the browser after the server has started."""
    webbrowser.open('http://127.0.0.1:5001')

def run_command(command):
    """Run a shell command and return its output."""
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"

def generate_key_pair(username, encrypted=True, passphrase=None, create_processed=True):
    """Generate key pair and return the results."""
    results = {
        'success': False,
        'messages': [],
        'files': {},
        'snowflake_command': None
    }
    
    try:
        # Create a temporary directory for this session
        session_dir = os.path.join(app.config['UPLOAD_FOLDER'], username)
        os.makedirs(session_dir, exist_ok=True)
        
        # Generate private key
        private_key_path = os.path.join(session_dir, f"{username}_rsa_key.p8")
        if encrypted:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
                temp.write(passphrase)
                temp_path = temp.name
            
            try:
                command = f"openssl genrsa 2048 | openssl pkcs8 -topk8 -v2 des3 -inform PEM -out {private_key_path} -passout file:{temp_path}"
                run_command(command)
                results['messages'].append("✅ Encrypted private key generated")
            finally:
                os.unlink(temp_path)
        else:
            command = f"openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out {private_key_path} -nocrypt"
            run_command(command)
            results['messages'].append("✅ Unencrypted private key generated")
        
        # Generate public key
        public_key_path = os.path.join(session_dir, f"{username}_rsa_key.pub")
        if encrypted:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
                temp.write(passphrase)
                temp_path = temp.name
            
            try:
                command = f"openssl rsa -in {private_key_path} -passin file:{temp_path} -pubout -out {public_key_path}"
                run_command(command)
            finally:
                os.unlink(temp_path)
        else:
            command = f"openssl rsa -in {private_key_path} -pubout -out {public_key_path}"
            run_command(command)
        
        results['messages'].append("✅ Public key generated")
        
        # Process private key if requested
        if create_processed:
            processed_key_path = os.path.join(session_dir, f"{username}_rsa_key_processed.p8")
            with open(private_key_path, 'r') as f:
                content = f.read()
            processed_content = content.replace('\n', '\\n')
            with open(processed_key_path, 'w') as f:
                f.write(processed_content)
            results['messages'].append("✅ Processed private key generated")
            results['files']['processed_key'] = f"{username}_rsa_key_processed.p8"
        
        # Generate Snowflake command
        with open(public_key_path, 'r') as f:
            content = f.read()
        lines = content.strip().split('\n')
        if len(lines) > 2:
            key_content = ''.join(lines[1:-1])
            snowflake_command = f"""ALTER USER {username} SET RSA_PUBLIC_KEY='{key_content}';

DESC USER {username};"""
            results['snowflake_command'] = snowflake_command
        
        results['files']['private_key'] = f"{username}_rsa_key.p8"
        results['files']['public_key'] = f"{username}_rsa_key.pub"
        results['success'] = True
        results['session_dir'] = session_dir
        
    except Exception as e:
        results['messages'].append(f"Error: {str(e)}")
    
    return results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    username = data.get('username')
    encrypted = data.get('encrypted', True)
    passphrase = data.get('passphrase')
    create_processed = data.get('create_processed', True)
    
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    if encrypted and not passphrase:
        return jsonify({'error': 'Passphrase is required for encrypted keys'}), 400
    
    results = generate_key_pair(
        username=username,
        encrypted=encrypted,
        passphrase=passphrase,
        create_processed=create_processed
    )
    
    return jsonify(results)

@app.route('/download/<username>/<filename>')
def download_file(username, filename):
    session_dir = os.path.join(app.config['UPLOAD_FOLDER'], username)
    return send_from_directory(session_dir, filename, as_attachment=True)

@app.route('/cleanup/<username>')
def cleanup(username):
    session_dir = os.path.join(app.config['UPLOAD_FOLDER'], username)
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir)
    return jsonify({'success': True})

if __name__ == '__main__':
    Timer(1.5, open_browser).start()
    app.run(host='127.0.0.1', port=5001, debug=True) 