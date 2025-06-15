from flask import Flask, render_template, request, jsonify, send_file, send_from_directory,session, redirect, url_for
import backend.oauth as oauth
import os
import subprocess
import tempfile
from werkzeug.utils import secure_filename
import json
from pathlib import Path
import shutil
import webbrowser
from threading import Timer
from functools import wraps
import backend.snowflake_client as sfc
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# Use a fixed secret key for development
app.config['SECRET_KEY'] = 'dev-secret-key-123'  # In production, use a secure random key
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
app.config['UPLOAD_FOLDER'] = os.path.join(tempfile.gettempdir(), 'snowflake_keys')

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def open_browser():
    """Open the browser after the server has started."""
    # Only open browser if not already opened
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
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
    authed = oauth.authenticated()
    return render_template('index.html', authenticated=authed)

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

@app.route('/process_key', methods=['POST'])
def process_key():
    """Process an existing private key according to requested options."""
    data = request.json or {}
    key_content = data.get('key', '')
    remove_line_breaks = data.get('remove_line_breaks', False)
    base64_encoding = data.get('base64_encoding', False)

    if not key_content or (not remove_line_breaks and not base64_encoding):
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    results = {'success': True}

    if remove_line_breaks:
        # Replace actual newlines with literal \n to mimic previous behaviour
        results['processed_key'] = key_content.replace('\n', '\\n')

    if base64_encoding:
        import base64
        encoded = base64.b64encode(key_content.encode('utf-8')).decode('utf-8')
        results['base64_encoded'] = encoded

    return jsonify(results)

def require_pat(f):
    """Decorator to ensure Authorization header is present for protected endpoints."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid PAT'}), 401
        # In Phase-1 we trust the presence; later phases can validate.
        return f(*args, **kwargs)
    return wrapper

# Test route
@app.route('/test')
def test():
    print("Test route hit")
    return jsonify({'status': 'ok', 'message': 'Server is responding'})

# OAuth routes
@app.route('/login')
def login():
    # Add debug logging
    print("Login route hit")
    print("OAuth Configuration:")
    print(f"OAUTH_CLIENT_ID: {oauth.OAUTH_CLIENT_ID}")
    print(f"OAUTH_AUTH_URL: {oauth.OAUTH_AUTH_URL}")
    print(f"OAUTH_TOKEN_URL: {oauth.OAUTH_TOKEN_URL}")
    print(f"OAUTH_REDIRECT_URI: {oauth.OAUTH_REDIRECT_URI}")
    print(f"OAUTH_SCOPE: {oauth.OAUTH_SCOPE}")
    
    try:
        if not oauth.OAUTH_CLIENT_ID:
            print("Error: OAUTH_CLIENT_ID not set")
            return jsonify({'error': 'OAuth client ID not configured'}), 500
        if not oauth.OAUTH_AUTH_URL:
            print("Error: OAUTH_AUTH_URL not set")
            return jsonify({'error': 'OAuth auth URL not configured'}), 500
        if not oauth.OAUTH_TOKEN_URL:
            print("Error: OAUTH_TOKEN_URL not set")
            return jsonify({'error': 'OAuth token URL not configured'}), 500
            
        auth_url = oauth.build_authorize_url()
        print(f"Generated auth URL: {auth_url}")
        # Redirect user to Snowflake OAuth authorize URL
        return redirect(auth_url)
    except Exception as e:
        print(f"Error in login route: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/oauth/callback')
def oauth_callback():
    # Handle redirect from Snowflake OAuth
    print("OAuth callback received")
    code = request.args.get('code')
    state = request.args.get('state')
    print(f"Code: {code}")
    print(f"State: {state}")
    
    if not code:
        print("Error: No code received")
        return "No authorization code received.", 400
        
    if not state:
        print("Error: No state received")
        return "No state parameter received.", 400
        
    print("Attempting to exchange code for token")
    if not oauth.exchange_code(code):
        print("Token exchange failed")
        return "OAuth token exchange failed.", 400
        
    print("OAuth flow completed successfully")
    return redirect(url_for('index'))

@app.route('/auth/status')
def auth_status():
    authed = oauth.authenticated()
    print('auth_status called; authenticated=', authed)
    # Optional: print session keys for debugging (omit token values for brevity)
    print('Session keys:', list(session.keys()))
    return jsonify({'authenticated': authed})

@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    oauth.logout()
    return jsonify({'success': True})

# Example protected endpoint (will be replaced with real ones later)
@app.route('/admin/ping')
@require_pat
def admin_ping():
    return jsonify({'success': True})

# Public liveness endpoint
@app.route('/ping')
def ping():
    return 'pong', 200

# ------------------ Grant Permissions API (Phase 2 Stub) ------------------

# In a real implementation, these will query Snowflake ACCOUNT_USAGE views.

@app.route('/databases')
@require_pat
def list_databases():
    pat = request.headers.get('Authorization')[7:]
    ensure_sf_conn(pat)
    try:
        dbs = sfc.client.list_databases()
        return jsonify({"success": True, "data": dbs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/schemas')
@require_pat
def list_schemas():
    db = request.args.get('db')
    if not db:
        return jsonify({"success": False, "error": "db param required"}), 400
    pat = request.headers.get('Authorization')[7:]
    ensure_sf_conn(pat)
    try:
        schemas = sfc.client.list_schemas(db)
        return jsonify({"success": True, "data": schemas})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/roles')
@require_pat
def list_roles():
    pat = request.headers.get('Authorization')[7:]
    ensure_sf_conn(pat)
    try:
        roles = sfc.client.list_roles()
        return jsonify({"success": True, "data": roles})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/grant_permissions', methods=['POST'])
@require_pat
def grant_permissions():
    payload = request.json or {}
    pat = request.headers.get('Authorization')[7:]
    ensure_sf_conn(pat)
    try:
        perm_type = payload.get('perm_type')
        db = payload.get('db')
        schema = payload.get('schema')
        role = payload.get('role')
        if perm_type == 'read':
            result = sfc.client.call_stored_procedure('UPLAND_MAINTENANCE.SECURITY.sp_grant_read_perms', [db, schema, role])
        elif perm_type == 'readwrite':
            result = sfc.client.call_stored_procedure('UPLAND_MAINTENANCE.SECURITY.sp_grant_readwrite_perms', [db, schema, role, False])
        elif perm_type == 'dbwide':
            result = sfc.client.call_stored_procedure('UPLAND_MAINTENANCE.SECURITY.sp_grant_readwrite_perms', [db, '', role, True])
        else:
            return jsonify({'success': False, 'error': 'Invalid permission type'}), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# helper to ensure connection
def ensure_sf_conn(pat: str):
    if sfc.client._conn is not None:
        return
    account_raw = os.getenv('SNOWFLAKE_ACCOUNT', 'UPLAND-EDP')
    account = account_raw.split('.')[0]  # strip domain if provided
    user = os.getenv('SNOWFLAKE_USER', 'ADMIN_MSTEGMAIER')
    warehouse = os.getenv('SNOWFLAKE_WAREHOUSE', 'UPLAND_ENGINEERING')
    role = os.getenv('SNOWFLAKE_ROLE', 'SYSADMIN')
    sfc.client.connect(pat=pat, account=account, user=user, warehouse=warehouse, role=role)

# -------------------------------------------------------------------------

if __name__ == '__main__':
    # Open browser after a short delay
    Timer(1.5, open_browser).start()
    # Run on port 5001 to match OAuth redirect URI
    app.run(host='127.0.0.1', port=5001, debug=True) 