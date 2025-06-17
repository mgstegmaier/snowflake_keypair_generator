from flask import Flask, render_template, request, jsonify, send_from_directory,session, redirect, url_for
import backend.oauth as oauth
import os
import subprocess
import tempfile
import shutil
import webbrowser
from threading import Timer
from functools import wraps
import backend.snowflake_client as sfc
from dotenv import load_dotenv
from backend import security as sec
import time
import logging
from snowflake.connector import errors as sf_errors

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

# ---------- Logging setup ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('snowflake-admin-app')

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
        
        # Also create files array for consistency with rotate endpoint
        files_array = [
            {'filename': f"{username}_rsa_key.p8", 'label': 'private_key'},
            {'filename': f"{username}_rsa_key.pub", 'label': 'public_key'}
        ]
        if create_processed:
            files_array.append({'filename': f"{username}_rsa_key_processed.p8", 'label': 'processed_key'})
        results['files_array'] = files_array
        
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

def require_oauth(f):
    """Decorator to ensure the user has a valid Snowflake OAuth token in session."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not oauth.authenticated():
            return jsonify({'error': 'Not authenticated'}), 401

        now = time.time()
        last = session.get('last_activity', now)
        if (now - last) > sec.INACTIVITY_TIMEOUT_SECONDS:
            session.clear()
            return jsonify({'error': 'Session expired due to inactivity'}), 401
        session['last_activity'] = now
        return f(*args, **kwargs)
    return wrapper

# --------------------- Utility helpers ---------------------

# Mask tokens for logs
def _redact(token: str, show: int = 4) -> str:
    if not token:
        return '<empty>'
    return token[:show] + '…' + f'({len(token)} chars)'

# ----------------------- Routes ----------------------------

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

# User info route
@app.route('/auth/userinfo')
@require_oauth
def userinfo():
    ident = oauth.current_identity()
    if not ident:
        return jsonify({'success': False, 'error': 'Unable to decode token'}), 500
    can_grant = ident['role'] in oauth.ALLOW_GRANT_ROLES
    return jsonify({'success': True, 'user': ident['user'], 'role': ident['role'], 'can_grant': can_grant})

# Example protected endpoint (will be replaced with real ones later)
@app.route('/admin/ping')
@require_oauth
def admin_ping():
    return jsonify({'success': True})

# Public liveness endpoint
@app.route('/ping')
def ping():
    return 'pong', 200

# ------------------ Grant Permissions API (Phase 2 Stub) ------------------

# In a real implementation, these will query Snowflake ACCOUNT_USAGE views.

@app.route('/databases')
@require_oauth
def list_databases():
    ensure_sf_conn()
    try:
        dbs = sfc.client.list_databases()
        return jsonify({"success": True, "data": dbs})
    except Exception as e:
        return error_response(e)

@app.route('/schemas')
@require_oauth
def list_schemas():
    db = request.args.get('db')
    if not db:
        return jsonify({"success": False, "error": "db param required"}), 400
    ensure_sf_conn()
    try:
        schemas = sfc.client.list_schemas(db)
        return jsonify({"success": True, "data": schemas})
    except Exception as e:
        return error_response(e)

@app.route('/roles')
@require_oauth
def list_roles():
    ensure_sf_conn()
    try:
        roles = sfc.client.list_roles()
        return jsonify({"success": True, "data": roles})
    except Exception as e:
        return error_response(e)

@app.route('/roles/detailed')
@require_oauth
def list_roles_detailed():
    """Get detailed role information for the roles table."""
    ensure_sf_conn()
    try:
        roles = sfc.client.list_roles_detailed()
        return jsonify({"success": True, "data": roles})
    except Exception as e:
        return error_response(e)

@app.route('/roles/<role_name>/privileges')
@require_oauth
def get_role_privileges(role_name):
    """Get privileges granted to a specific role."""
    ensure_sf_conn()
    try:
        privileges = sfc.client.get_role_privileges(role_name)
        return jsonify({"success": True, "data": privileges})
    except Exception as e:
        return error_response(e)

@app.route('/roles/<role_name>/grants')
@require_oauth
def get_role_grants(role_name):
    """Get users and roles that have been granted a specific role."""
    ensure_sf_conn()
    try:
        grants = sfc.client.get_role_grants(role_name)
        return jsonify({"success": True, "data": grants})
    except Exception as e:
        return error_response(e)

@app.route('/grant_permissions', methods=['POST'])
@require_oauth
def grant_permissions():
    payload = request.json or {}
    ensure_sf_conn()
    try:
        perm_type = payload.get('perm_type')
        db = payload.get('db')
        schema = payload.get('schema')
        role = payload.get('role')
        warehouse = payload.get('warehouse')

        # Validate required fields
        if not warehouse:
            return jsonify({'success': False, 'error': 'Warehouse is required'}), 400

        # Enhanced logging
        print(f"Grant request: {perm_type} on {db}.{schema} to role {role} using warehouse {warehouse}")

        # Set the warehouse before executing stored procedure
        sfc.client.set_warehouse(warehouse)

        proc_map = {
            'read_grant_schema': ('UPLAND_MAINTENANCE.SECURITY.sp_grant_read_perms', [db, schema, role]),
            'read_revoke_schema': ('UPLAND_MAINTENANCE.SECURITY.sp_revoke_read_perms', [db, schema, role]),
            'readwrite_grant_schema': ('UPLAND_MAINTENANCE.SECURITY.sp_grant_readwrite_perms', [db, schema, role, False]),
            'readwrite_revoke_schema': ('UPLAND_MAINTENANCE.SECURITY.sp_revoke_readwrite_perms', [db, schema, role, False]),
            'readwrite_grant_database': ('UPLAND_MAINTENANCE.SECURITY.sp_grant_readwrite_perms', [db, None, role, True]),
            'readwrite_revoke_database': ('UPLAND_MAINTENANCE.SECURITY.sp_revoke_readwrite_perms', [db, None, role, True])
        }

        if perm_type not in proc_map:
            return jsonify({'success': False, 'error': f'Unknown permission type: {perm_type}'}), 400

        proc_name, args = proc_map[perm_type]
        print(f"Executing stored procedure: {proc_name} with args: {args}")
        
        result = sfc.client.call_stored_procedure(proc_name, args)
        return jsonify({'success': True, 'message': f'Permissions {"granted" if "grant" in perm_type else "revoked"} successfully', 'details': result})
    except Exception as e:
        error_msg = str(e)
        print(f"Detailed error in grant_permissions: {error_msg}")
        
        # Check for specific permission-related errors
        if "Insufficient privileges" in error_msg:
            return jsonify({
                'success': False, 
                'error': f'Insufficient privileges: Your current role may not have permission to grant access to the role "{role}". You may need SECURITYADMIN or higher privileges to grant permissions to other roles.',
                'details': error_msg
            }), 403
        
        return error_response(e)

@app.route('/warehouses')
@require_oauth
def list_warehouses():
    ensure_sf_conn()
    try:
        whs = sfc.client.list_warehouses()
        return jsonify({"success": True, "data": whs})
    except Exception as e:
        return error_response(e)

@app.route('/keys/users')
@require_oauth
def list_users_with_keys():
    """List all users with enhanced key information for key management."""
    ensure_sf_conn()
    try:
        users = sfc.client.list_users_with_keys_optimized()
        return jsonify({"success": True, "data": users})
    except Exception as e:
        return error_response(e)

@app.route('/keys/users/<username>/details')
@require_oauth
def get_user_key_details(username):
    """Get detailed key information for a specific user."""
    ensure_sf_conn()
    try:
        details = sfc.client.get_user_details(username)
        return jsonify({"success": True, "data": details})
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg.lower():
            return jsonify({
                'success': False, 
                'error': f'User "{username}" does not exist'
            }), 404
        return error_response(e)

@app.route('/keys/users/<username>/set', methods=['POST'])
@require_oauth
def set_user_public_key(username):
    """Set or update RSA public key for a user."""
    ensure_sf_conn()
    try:
        payload = request.json or {}
        public_key = payload.get('public_key')
        key_number = payload.get('key_number', 1)
        
        if not public_key:
            return jsonify({'success': False, 'error': 'Public key is required'}), 400
        
        if key_number not in [1, 2]:
            return jsonify({'success': False, 'error': 'Key number must be 1 or 2'}), 400
        
        result = sfc.client.set_user_public_key(username, public_key, key_number)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg.lower():
            return jsonify({
                'success': False, 
                'error': f'User "{username}" does not exist'
            }), 404
        return error_response(e)

@app.route('/keys/users/<username>/unset', methods=['POST'])
@require_oauth
def unset_user_public_key(username):
    """Remove RSA public key from a user."""
    ensure_sf_conn()
    try:
        payload = request.json or {}
        key_number = payload.get('key_number', 1)
        
        if key_number not in [1, 2]:
            return jsonify({'success': False, 'error': 'Key number must be 1 or 2'}), 400
        
        result = sfc.client.unset_user_public_key(username, key_number)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg.lower():
            return jsonify({
                'success': False, 
                'error': f'User "{username}" does not exist'
            }), 404
        return error_response(e)

@app.route('/debug/procedures')
@require_oauth
def debug_procedures():
    ensure_sf_conn()
    try:
        procs = sfc.client.list_stored_procedures('UPLAND_MAINTENANCE.SECURITY')
        return jsonify({"success": True, "procedures": procs})
    except Exception as e:
        return error_response(e)

@app.route('/users')
@require_oauth
def list_users():
    """List all users with their details."""
    ensure_sf_conn()
    try:
        users = sfc.client.list_users()
        return jsonify({"success": True, "data": users})
    except Exception as e:
        return error_response(e)

@app.route('/users/<username>/unlock', methods=['POST'])
@require_oauth
def unlock_user(username):
    """Unlock a user account."""
    ensure_sf_conn()
    try:
        # Set warehouse before calling stored procedure
        if hasattr(sfc.client, '_warehouse') and sfc.client._warehouse:
            sfc.client.set_warehouse(sfc.client._warehouse)
        
        result = sfc.client.call_stored_procedure(
            'UPLAND_MAINTENANCE.SECURITY.sp_unlock_user', 
            [username]
        )
        return jsonify({
            "success": True, 
            "message": f"User {username} unlocked successfully",
            "details": result
        })
    except Exception as e:
        error_msg = str(e)
        print(f"Error unlocking user {username}: {error_msg}")
        
        if "does not exist" in error_msg.lower():
            return jsonify({
                'success': False, 
                'error': f'User "{username}" does not exist'
            }), 404
        
        return error_response(e)

@app.route('/users/<username>/reset_password', methods=['POST'])
@require_oauth
def reset_user_password(username):
    """Reset a user's password."""
    ensure_sf_conn()
    try:
        payload = request.json or {}
        new_password = payload.get('new_password')
        
        if not new_password:
            return jsonify({'success': False, 'error': 'New password is required'}), 400
        
        # Set warehouse before calling stored procedure
        if hasattr(sfc.client, '_warehouse') and sfc.client._warehouse:
            sfc.client.set_warehouse(sfc.client._warehouse)
        
        result = sfc.client.call_stored_procedure(
            'UPLAND_MAINTENANCE.SECURITY.sp_reset_password', 
            [username, new_password]
        )
        return jsonify({
            "success": True, 
            "message": f"Password reset for user {username}",
            "details": result
        })
    except Exception as e:
        error_msg = str(e)
        print(f"Error resetting password for user {username}: {error_msg}")
        
        if "does not exist" in error_msg.lower():
            return jsonify({
                'success': False, 
                'error': f'User "{username}" does not exist'
            }), 404
        
        return error_response(e)

@app.route('/users/<username>/unset_password', methods=['POST'])
@require_oauth
def unset_user_password(username):
    """Unset a user's password."""
    ensure_sf_conn()
    try:
        # Set warehouse before calling stored procedure
        if hasattr(sfc.client, '_warehouse') and sfc.client._warehouse:
            sfc.client.set_warehouse(sfc.client._warehouse)
        
        result = sfc.client.call_stored_procedure(
            'UPLAND_MAINTENANCE.SECURITY.sp_unset_password', 
            [username]
        )
        return jsonify({
            "success": True, 
            "message": f"Password unset for user {username}",
            "details": result
        })
    except Exception as e:
        error_msg = str(e)
        print(f"Error unsetting password for user {username}: {error_msg}")
        
        if "does not exist" in error_msg.lower():
            return jsonify({
                'success': False, 
                'error': f'User "{username}" does not exist'
            }), 404
        
        return error_response(e)

@app.route('/debug/clear-cache', methods=['POST'])
@require_oauth
def clear_cache():
    """Clear the user cache to force fresh data load."""
    ensure_sf_conn()
    try:
        sfc.client.clear_users_cache()
        return jsonify({"success": True, "message": "User cache cleared"})
    except Exception as e:
        return error_response(e)

@app.route('/keys/generate-and-rotate', methods=['POST'])
@require_oauth
def generate_and_rotate_key():
    """Generate encrypted RSA key pair and optionally set in Snowflake."""
    try:
        payload = request.json or {}
        username = payload.get('username')
        passphrase = payload.get('passphrase')
        set_in_snowflake = payload.get('set_in_snowflake', False)
        
        if not username:
            return jsonify({'success': False, 'error': 'Username is required'}), 400
        if not passphrase:
            return jsonify({'success': False, 'error': 'Passphrase is required'}), 400
        
        # Generate the key pair using the existing function
        result = generate_key_pair(username, encrypted=True, passphrase=passphrase, create_processed=True)
        
        if not result.get('success', False):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Key generation failed')
            }), 400
        
        # Convert files dict to array format for frontend
        files_array = []
        if 'files' in result and isinstance(result['files'], dict):
            for file_type, filename in result['files'].items():
                files_array.append({
                    'filename': filename,
                    'label': file_type
                })
        
        response_data = {
            'success': True,
            'username': username,
            'passphrase': passphrase,
            'files': files_array,
            'snowflake_attempted': set_in_snowflake,
            'snowflake_success': False,
            'snowflake_command': None,
            'snowflake_error': None
        }
        
        # Optionally set in Snowflake
        if set_in_snowflake:
            try:
                print(f"Attempting to set key in Snowflake for user: {username}")
                ensure_sf_conn()
                
                # Get the public key content from the generated file
                public_key_filename = result['files'].get('public_key')
                print(f"Public key filename: {public_key_filename}")
                
                if public_key_filename:
                    public_key_path = os.path.join(app.config['UPLOAD_FOLDER'], username, public_key_filename)
                    print(f"Looking for public key at: {public_key_path}")
                    
                    if os.path.exists(public_key_path):
                        with open(public_key_path, 'r') as f:
                            public_key_content = f.read().strip()
                        print(f"Successfully read public key content ({len(public_key_content)} chars)")
                        
                        # Set the key in Snowflake
                        print(f"Calling set_user_public_key for {username}")
                        sf_result = sfc.client.set_user_public_key(username, public_key_content, 1)
                        print(f"Snowflake set_user_public_key result: {sf_result}")
                        
                        if sf_result.get('success'):
                            response_data['snowflake_success'] = True
                            print("✓ Successfully set public key in Snowflake")
                        else:
                            # Generate manual command for fallback
                            response_data['snowflake_command'] = f"ALTER USER {username} SET RSA_PUBLIC_KEY='{public_key_content}';"
                            # Extract error from either 'error' or 'message' field
                            error_msg = sf_result.get('error') or sf_result.get('message', 'Unknown error')
                            response_data['snowflake_error'] = error_msg
                            print(f"✗ Failed to set public key in Snowflake: {error_msg}")
                    else:
                        # Still provide a fallback command even if file not found
                        response_data['snowflake_command'] = f"-- Could not find generated public key file: {public_key_filename}\n-- Please download the public key file and run:\n-- ALTER USER {username} SET RSA_PUBLIC_KEY='<public_key_content>';"
                        response_data['snowflake_error'] = 'Public key file not found'
                        print(f"✗ Public key file not found at: {public_key_path}")
                else:
                    response_data['snowflake_command'] = f"-- No public key file generated for {username}\n-- Please ensure key generation completed successfully"
                    response_data['snowflake_error'] = 'No public key in generation result'
                    print("✗ No public key file in generation result")
                    
            except Exception as sf_error:
                print(f"Exception while setting key in Snowflake: {str(sf_error)}")
                # Generate manual command for fallback
                public_key_content = "-- Replace with actual public key content --"
                try:
                    # Try to get the public key content if available
                    public_key_filename = result['files'].get('public_key')
                    if public_key_filename:
                        public_key_path = os.path.join(app.config['UPLOAD_FOLDER'], username, public_key_filename)
                        if os.path.exists(public_key_path):
                            with open(public_key_path, 'r') as f:
                                public_key_content = f.read().strip()
                except Exception:
                    pass
                
                response_data['snowflake_command'] = f"ALTER USER {username} SET RSA_PUBLIC_KEY='{public_key_content}';"
                response_data['snowflake_error'] = str(sf_error)
                print("✗ Generated fallback command due to exception")
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in generate_and_rotate_key: {str(e)}")
        return error_response(e)

# helper to ensure connection
def ensure_sf_conn():
    # Skip connection during unit tests
    if app.config.get('TESTING'):
        return
    if sfc.client._conn is not None:
        return
    token = oauth.get_access_token()
    if not token:
        raise RuntimeError('No OAuth token in session')
    account_raw = os.getenv('SNOWFLAKE_ACCOUNT', 'UPLAND-EDP')
    account = account_raw.split('.')[0]
    user = os.getenv('SNOWFLAKE_USER', 'ADMIN_MSTEGMAIER')
    warehouse = os.getenv('SNOWFLAKE_WAREHOUSE', 'UPLAND_ENGINEERING')
    role = os.getenv('SNOWFLAKE_ROLE', 'SYSADMIN')
    logger.info('Opening Snowflake connection as %s role=%s warehouse=%s token=%s', user, role, warehouse, _redact(token))
    sfc.client.connect(pat=token, account=account, user=user, warehouse=warehouse, role=role)

# Standard JSON error envelope
def error_response(exc: Exception, status: int = 500):
    if isinstance(exc, sf_errors.Error):
        msg = exc.msg or str(exc)
    else:
        msg = str(exc)
    logger.error('API error: %s', msg)
    return jsonify({'success': False, 'error': msg}), status

# -------------------------------------------------------------------------

if __name__ == '__main__':
    # Open browser after a short delay
    Timer(1.5, open_browser).start()
    # Run on port 5001 to match OAuth redirect URI
    app.run(host='127.0.0.1', port=5001, debug=True) 