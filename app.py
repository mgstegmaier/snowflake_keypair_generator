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
from backend import audit
import time
import logging
import datetime
from snowflake.connector import errors as sf_errors

load_dotenv()

# ---------- Logging setup ----------
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Add file handler for application logs
app_log_file = os.path.join(LOG_DIR, 'app.log')
file_handler = RotatingFileHandler(
    app_log_file,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

# Add error log file handler
error_log_file = os.path.join(LOG_DIR, 'error.log')
error_handler = RotatingFileHandler(
    error_log_file,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

logger = logging.getLogger('snowflake-admin-app')
logger.addHandler(file_handler)
logger.addHandler(error_handler)

# Configure Werkzeug (Flask's WSGI server) logging
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_log_file = os.path.join(LOG_DIR, 'access.log')
werkzeug_handler = RotatingFileHandler(
    werkzeug_log_file,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
werkzeug_handler.setLevel(logging.INFO)
werkzeug_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
werkzeug_logger.addHandler(werkzeug_handler)

app = Flask(__name__)
# Use environment variable for secret key
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') or os.getenv('SECRET_KEY', 'dev-secret-key-123')
if app.config['SECRET_KEY'] == 'dev-secret-key-123':
    logger.warning('Using default development secret key. Set FLASK_SECRET_KEY environment variable for production.')
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

def run_command(command_args):
    """Run a shell command safely using argument array."""
    try:
        # Ensure command_args is a list for safe execution
        if isinstance(command_args, str):
            raise ValueError("Command must be provided as a list of arguments, not a string")
        result = subprocess.run(command_args, check=True, capture_output=True, text=True)
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
                # Generate private key with encryption - use two-step process for security
                temp_private = os.path.join(session_dir, f"{username}_temp_rsa.pem")
                
                # Step 1: Generate RSA key
                run_command(['openssl', 'genrsa', '-out', temp_private, '2048'])
                
                # Step 2: Convert to PKCS8 format with encryption
                run_command(['openssl', 'pkcs8', '-topk8', '-v2', 'des3', '-in', temp_private, 
                           '-out', private_key_path, '-passout', f'file:{temp_path}'])
                
                # Clean up temporary unencrypted key
                os.unlink(temp_private)
                results['messages'].append("✅ Encrypted private key generated")
            finally:
                os.unlink(temp_path)
        else:
            # Generate unencrypted private key in PKCS8 format
            temp_private = os.path.join(session_dir, f"{username}_temp_rsa.pem")
            
            # Step 1: Generate RSA key
            run_command(['openssl', 'genrsa', '-out', temp_private, '2048'])
            
            # Step 2: Convert to PKCS8 format without encryption
            run_command(['openssl', 'pkcs8', '-topk8', '-in', temp_private, '-out', private_key_path, '-nocrypt'])
            
            # Clean up temporary key
            os.unlink(temp_private)
            results['messages'].append("✅ Unencrypted private key generated")
        
        # Generate public key
        public_key_path = os.path.join(session_dir, f"{username}_rsa_key.pub")
        if encrypted:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
                temp.write(passphrase)
                temp_path = temp.name
            
            try:
                run_command(['openssl', 'rsa', '-in', private_key_path, '-passin', f'file:{temp_path}', 
                           '-pubout', '-out', public_key_path])
            finally:
                os.unlink(temp_path)
        else:
            run_command(['openssl', 'rsa', '-in', private_key_path, '-pubout', '-out', public_key_path])
        
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
    user, user_role = get_audit_identity()
    
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
            'read_grant_database': ('UPLAND_MAINTENANCE.SECURITY.sp_grant_read_perms', [db, '', role, True]),
            'read_revoke_schema': ('UPLAND_MAINTENANCE.SECURITY.sp_revoke_read_perms', [db, schema, role]),
            'readwrite_grant_schema': ('UPLAND_MAINTENANCE.SECURITY.sp_grant_readwrite_perms', [db, schema, role, False]),
            'readwrite_revoke_schema': ('UPLAND_MAINTENANCE.SECURITY.sp_revoke_readwrite_perms', [db, schema, role, False]),
            'readwrite_grant_database': ('UPLAND_MAINTENANCE.SECURITY.sp_grant_readwrite_perms', [db, '', role, True]),
            'readwrite_revoke_database': ('UPLAND_MAINTENANCE.SECURITY.sp_revoke_readwrite_perms', [db, '', role, True])
        }

        if perm_type not in proc_map:
            return jsonify({'success': False, 'error': f'Unknown permission type: {perm_type}'}), 400

        proc_name, args = proc_map[perm_type]
        print(f"Executing stored procedure: {proc_name} with args: {args}")
        
        result = sfc.client.call_stored_procedure(proc_name, args)
        
        # Log successful action
        action_name = 'permission_grant' if 'grant' in perm_type else 'permission_revoke'
        audit.log_action(
            action=action_name,
            user=user,
            role=user_role,
            target_type='permission',
            target_id=f"{db}.{schema if schema else 'DATABASE'}.{role}",
            details={
                'permission_type': perm_type,
                'database': db,
                'schema': schema or 'DATABASE-WIDE',
                'target_role': role
            },
            success=True
        )
        
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
    """Set or update RSA public key for a user using enhanced stored procedure."""
    ensure_sf_conn()
    user, role = get_audit_identity()
    
    try:
        payload = request.json or {}
        public_key = payload.get('public_key')
        key_number = payload.get('key_number', 1)
        unset_password = payload.get('unset_password', False)
        new_type = payload.get('new_type')
        
        if not public_key:
            return jsonify({'success': False, 'error': 'Public key is required'}), 400
        
        if key_number not in [1, 2]:
            return jsonify({'success': False, 'error': 'Key number must be 1 or 2'}), 400
        
        # If key_number is 2, fall back to old method (stored proc only handles primary key)
        if key_number == 2:
            result = sfc.client.set_user_public_key(username, public_key, key_number)
        else:
            # Use enhanced stored procedure for primary key
            result = sfc.client.update_user_rsa_key(
                username, 
                public_key, 
                unset_password, 
                new_type if new_type and new_type != 'NULL' else None
            )
        
        if result['success']:
            # Log successful action
            audit.log_action(
                action='key_set',
                user=user,
                role=role,
                target_type='user',
                target_id=username,
                details={'key_number': key_number, 'unset_password': unset_password},
                success=True
            )
            return jsonify(result)
        else:
            # Log failed action
            audit.log_action(
                action='key_set',
                user=user,
                role=role,
                target_type='user',
                target_id=username,
                details={'key_number': key_number},
                success=False,
                error_message=result.get('error', 'Unknown error')
            )
            return jsonify(result), 400
            
    except Exception as e:
        error_msg = str(e)
        # Log failed action
        audit.log_action(
            action='key_set',
            user=user,
            role=role,
            target_type='user',
            target_id=username,
            details={},
            success=False,
            error_message=error_msg
        )
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
    user, role = get_audit_identity()
    
    try:
        payload = request.json or {}
        key_number = payload.get('key_number', 1)
        
        if key_number not in [1, 2]:
            return jsonify({'success': False, 'error': 'Key number must be 1 or 2'}), 400
        
        result = sfc.client.unset_user_public_key(username, key_number)
        
        if result['success']:
            # Log successful action
            audit.log_action(
                action='key_unset',
                user=user,
                role=role,
                target_type='user',
                target_id=username,
                details={'key_number': key_number},
                success=True
            )
            return jsonify(result)
        else:
            # Log failed action
            audit.log_action(
                action='key_unset',
                user=user,
                role=role,
                target_type='user',
                target_id=username,
                details={'key_number': key_number},
                success=False,
                error_message=result.get('error', 'Unknown error')
            )
            return jsonify(result), 400
            
    except Exception as e:
        error_msg = str(e)
        # Log failed action
        audit.log_action(
            action='key_unset',
            user=user,
            role=role,
            target_type='user',
            target_id=username,
            details={},
            success=False,
            error_message=error_msg
        )
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
    ident = oauth.current_identity()
    user = ident.get('user', 'unknown') if ident else 'unknown'
    role = ident.get('role', 'unknown') if ident else 'unknown'
    
    try:
        # Set warehouse before calling stored procedure
        if hasattr(sfc.client, '_warehouse') and sfc.client._warehouse:
            sfc.client.set_warehouse(sfc.client._warehouse)
        
        result = sfc.client.call_stored_procedure(
            'UPLAND_MAINTENANCE.SECURITY.sp_unlock_user', 
            [username]
        )
        
        # Log successful action
        audit.log_action(
            action='user_unlock',
            user=user,
            role=role,
            target_type='user',
            target_id=username,
            details={'result': result},
            success=True
        )
        
        return jsonify({
            "success": True, 
            "message": f"User {username} unlocked successfully",
            "details": result
        })
    except Exception as e:
        error_msg = str(e)
        print(f"Error unlocking user {username}: {error_msg}")
        
        # Log failed action
        audit.log_action(
            action='user_unlock',
            user=user,
            role=role,
            target_type='user',
            target_id=username,
            details={},
            success=False,
            error_message=error_msg
        )
        
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
    user, role = get_audit_identity()
    
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
        
        # Log successful action
        audit.log_action(
            action='password_reset',
            user=user,
            role=role,
            target_type='user',
            target_id=username,
            details={},
            success=True
        )
        
        return jsonify({
            "success": True, 
            "message": f"Password reset for user {username}",
            "details": result
        })
    except Exception as e:
        error_msg = str(e)
        print(f"Error resetting password for user {username}: {error_msg}")
        
        # Log failed action
        audit.log_action(
            action='password_reset',
            user=user,
            role=role,
            target_type='user',
            target_id=username,
            details={},
            success=False,
            error_message=error_msg
        )
        
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
    user, role = get_audit_identity()
    
    try:
        # Set warehouse before calling stored procedure
        if hasattr(sfc.client, '_warehouse') and sfc.client._warehouse:
            sfc.client.set_warehouse(sfc.client._warehouse)
        
        result = sfc.client.call_stored_procedure(
            'UPLAND_MAINTENANCE.SECURITY.sp_unset_password', 
            [username]
        )
        
        # Log successful action
        audit.log_action(
            action='password_unset',
            user=user,
            role=role,
            target_type='user',
            target_id=username,
            details={},
            success=True
        )
        
        return jsonify({
            "success": True, 
            "message": f"Password unset for user {username}",
            "details": result
        })
    except Exception as e:
        error_msg = str(e)
        print(f"Error unsetting password for user {username}: {error_msg}")
        
        # Log failed action
        audit.log_action(
            action='password_unset',
            user=user,
            role=role,
            target_type='user',
            target_id=username,
            details={},
            success=False,
            error_message=error_msg
        )
        
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

def parse_log_line(line):
    """Parse a log line into structured components."""
    import re
    # Try to match standard log format: YYYY-MM-DD HH:MM:SS LEVEL logger_name: message
    # Format: 2024-01-01 12:00:00 INFO snowflake-admin-app: message here
    pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\w+)\s+([^:]+):\s+(.+)$'
    match = re.match(pattern, line.strip())
    
    if match:
        timestamp_str, level, source, message = match.groups()
        # Convert timestamp to include milliseconds for consistency
        try:
            timestamp = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        except:
            pass
        return {
            'timestamp': timestamp_str,
            'level': level,
            'source': source.strip(),
            'message': message,
            'full_entry': line.strip()
        }
    
    # Fallback: try to extract at least timestamp and level
    parts = line.strip().split(' ', 3)
    if len(parts) >= 3:
        timestamp_str = f"{parts[0]} {parts[1]}"
        level = parts[2] if len(parts) > 2 else 'INFO'
        message = parts[3] if len(parts) > 3 else line.strip()
        source = 'unknown'
        return {
            'timestamp': timestamp_str,
            'level': level,
            'source': source,
            'message': message,
            'full_entry': line.strip()
        }
    
    # Last resort: return as-is
    return {
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3],
        'level': 'INFO',
        'source': 'unknown',
        'message': line.strip(),
        'full_entry': line.strip()
    }

def read_log_file(filepath, max_lines=None):
    """Read log file and return parsed entries."""
    entries = []
    if not os.path.exists(filepath):
        return entries
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            # Read from end of file (most recent logs first)
            if max_lines:
                lines = lines[-max_lines:]
            
            for line in lines:
                if line.strip():
                    parsed = parse_log_line(line)
                    if parsed:
                        entries.append(parsed)
    except Exception as e:
        logger.error(f"Error reading log file {filepath}: {e}")
    
    return entries

@app.route('/logs')
@require_oauth
def get_server_logs():
    """Get server logs with filtering options from actual log files."""
    try:
        lines = request.args.get('lines', '100', type=int)
        level_filter = request.args.get('level', '')
        search_term = request.args.get('search', '')
        
        # Get log entries from actual log files
        log_entries = []
        
        try:
            # Read from multiple log sources
            log_files = [
                ('app.log', 'app'),
                ('error.log', 'app'),
                ('access.log', 'werkzeug')
            ]
            
            all_entries = []
            for log_filename, source_prefix in log_files:
                log_filepath = os.path.join(LOG_DIR, log_filename)
                entries = read_log_file(log_filepath, max_lines=lines * 2)  # Read more to account for filtering
                all_entries.extend(entries)
            
            # If no log files exist yet, provide a helpful message
            if not all_entries:
                # Check if log directory exists but files are empty
                if os.path.exists(LOG_DIR):
                    log_entries = [{
                        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3],
                        'level': 'INFO',
                        'source': 'app',
                        'message': 'No log entries found. Logs will appear here as the application runs.',
                        'full_entry': 'INFO app: No log entries found. Logs will appear here as the application runs.'
                    }]
                else:
                    log_entries = [{
                        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3],
                        'level': 'INFO',
                        'source': 'app',
                        'message': 'Log directory not found. Logs will be created automatically.',
                        'full_entry': 'INFO app: Log directory not found. Logs will be created automatically.'
                    }]
            else:
                # Apply filters
                for entry in all_entries:
                    # Level filter
                    if level_filter and entry.get('level', '').upper() != level_filter.upper():
                        continue
                    
                    # Search filter
                    if search_term:
                        search_lower = search_term.lower()
                        if (search_lower not in entry.get('message', '').lower() and
                            search_lower not in entry.get('source', '').lower() and
                            search_lower not in entry.get('full_entry', '').lower()):
                            continue
                    
                    log_entries.append(entry)
                
                # Sort by timestamp (newest first)
                try:
                    log_entries.sort(key=lambda x: datetime.datetime.strptime(
                        x['timestamp'].split(',')[0], '%Y-%m-%d %H:%M:%S'
                    ), reverse=True)
                except:
                    # If timestamp parsing fails, keep original order
                    pass
                
                # Limit to requested number of lines
                log_entries = log_entries[:lines]
            
        except Exception as e:
            logger.error(f"Error reading log entries: {e}")
            log_entries = [{
                'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3],
                'level': 'ERROR',
                'source': 'app',
                'message': f'Failed to read server logs: {str(e)}',
                'full_entry': f'ERROR app: Failed to read server logs: {str(e)}'
            }]
        
        return jsonify({
            'success': True,
            'logs': log_entries,
            'total_lines': len(log_entries),
            'filters': {
                'level': level_filter,
                'search': search_term,
                'lines': lines
            },
            'timestamp': datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'logs': [],
            'total_lines': 0
        }), 500

def export_to_csv(data, headers):
    """Convert data to CSV format."""
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in data:
        writer.writerow([row.get(h, '') for h in headers])
    return output.getvalue()

def export_to_json(data):
    """Convert data to JSON format."""
    import json
    return json.dumps(data, indent=2, default=str)

@app.route('/export/users')
@require_oauth
def export_users():
    """Export users data in CSV or JSON format."""
    format_type = request.args.get('format', 'json').lower()
    ensure_sf_conn()
    try:
        users = sfc.client.list_users_with_keys_optimized()
        
        if format_type == 'csv':
            # Flatten user data for CSV
            headers = ['name', 'login_name', 'display_name', 'email', 'disabled', 
                      'snowflake_lock', 'must_change_password', 'has_rsa_public_key',
                      'has_password', 'has_mfa', 'default_role', 'default_warehouse',
                      'created_on', 'last_success_login']
            csv_data = []
            for user in users:
                csv_data.append({
                    'name': user.get('name', ''),
                    'login_name': user.get('login_name', ''),
                    'display_name': user.get('display_name', ''),
                    'email': user.get('email', ''),
                    'disabled': 'Yes' if user.get('disabled') else 'No',
                    'snowflake_lock': 'Yes' if user.get('snowflake_lock') else 'No',
                    'must_change_password': 'Yes' if user.get('must_change_password') else 'No',
                    'has_rsa_public_key': 'Yes' if user.get('has_rsa_public_key') else 'No',
                    'has_password': 'Yes' if user.get('has_password') else 'No',
                    'has_mfa': 'Yes' if user.get('has_mfa') else 'No',
                    'default_role': user.get('default_role', ''),
                    'default_warehouse': user.get('default_warehouse', ''),
                    'created_on': str(user.get('created_on', '')),
                    'last_success_login': str(user.get('last_success_login', ''))
                })
            csv_content = export_to_csv(csv_data, headers)
            from flask import Response
            return Response(
                csv_content,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=users_export_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
            )
        else:
            # JSON export
            json_content = export_to_json(users)
            from flask import Response
            return Response(
                json_content,
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment; filename=users_export_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'}
            )
    except Exception as e:
        return error_response(e)

@app.route('/export/roles')
@require_oauth
def export_roles():
    """Export roles data in CSV or JSON format."""
    format_type = request.args.get('format', 'json').lower()
    ensure_sf_conn()
    try:
        roles = sfc.client.list_roles_detailed()
        
        if format_type == 'csv':
            headers = ['name', 'type', 'owner', 'comment', 'created_on']
            csv_data = []
            for role in roles:
                csv_data.append({
                    'name': role.get('name', ''),
                    'type': role.get('type', ''),
                    'owner': role.get('owner', ''),
                    'comment': role.get('comment', ''),
                    'created_on': str(role.get('created_on', ''))
                })
            csv_content = export_to_csv(csv_data, headers)
            from flask import Response
            return Response(
                csv_content,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=roles_export_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
            )
        else:
            json_content = export_to_json(roles)
            from flask import Response
            return Response(
                json_content,
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment; filename=roles_export_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'}
            )
    except Exception as e:
        return error_response(e)

@app.route('/export/logs')
@require_oauth
def export_logs():
    """Export logs data in text or JSON format."""
    format_type = request.args.get('format', 'json').lower()
    lines = request.args.get('lines', '1000', type=int)
    level_filter = request.args.get('level', '')
    search_term = request.args.get('search', '')
    
    try:
        # Reuse the log reading logic
        log_entries = []
        log_files = [
            ('app.log', 'app'),
            ('error.log', 'app'),
            ('access.log', 'werkzeug')
        ]
        
        all_entries = []
        for log_filename, source_prefix in log_files:
            log_filepath = os.path.join(LOG_DIR, log_filename)
            entries = read_log_file(log_filepath, max_lines=lines * 2)
            all_entries.extend(entries)
        
        # Apply filters
        for entry in all_entries:
            if level_filter and entry.get('level', '').upper() != level_filter.upper():
                continue
            if search_term:
                search_lower = search_term.lower()
                if (search_lower not in entry.get('message', '').lower() and
                    search_lower not in entry.get('source', '').lower() and
                    search_lower not in entry.get('full_entry', '').lower()):
                    continue
            log_entries.append(entry)
        
        # Sort by timestamp (newest first)
        try:
            log_entries.sort(key=lambda x: datetime.datetime.strptime(
                x['timestamp'].split(',')[0], '%Y-%m-%d %H:%M:%S'
            ), reverse=True)
        except:
            pass
        
        log_entries = log_entries[:lines]
        
        if format_type == 'txt' or format_type == 'text':
            # Text export (one line per log entry)
            text_content = '\n'.join([entry.get('full_entry', '') for entry in log_entries])
            from flask import Response
            return Response(
                text_content,
                mimetype='text/plain',
                headers={'Content-Disposition': f'attachment; filename=logs_export_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'}
            )
        else:
            # JSON export
            json_content = export_to_json(log_entries)
            from flask import Response
            return Response(
                json_content,
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment; filename=logs_export_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'}
            )
    except Exception as e:
        return error_response(e)

@app.route('/audit/logs')
@require_oauth
def get_audit_logs():
    """Get audit log entries with optional filtering."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        action_filter = request.args.get('action')
        user_filter = request.args.get('user')
        max_entries = request.args.get('max_entries', '1000', type=int)
        
        entries = audit.read_audit_logs(
            start_date=start_date,
            end_date=end_date,
            action_filter=action_filter,
            user_filter=user_filter,
            max_entries=max_entries
        )
        
        return jsonify({
            'success': True,
            'entries': entries,
            'total_entries': len(entries),
            'filters': {
                'start_date': start_date,
                'end_date': end_date,
                'action': action_filter,
                'user': user_filter
            }
        })
    except Exception as e:
        logger.error(f"Error fetching audit logs: {e}")
        return error_response(e)

@app.route('/audit/statistics')
@require_oauth
def get_audit_statistics():
    """Get audit log statistics."""
    try:
        stats = audit.get_audit_statistics()
        return jsonify({
            'success': True,
            'statistics': stats
        })
    except Exception as e:
        logger.error(f"Error fetching audit statistics: {e}")
        return error_response(e)

@app.route('/dashboard')
@require_oauth
def get_dashboard_data():
    """Get dashboard data including statistics and system health."""
    ensure_sf_conn()
    try:
        # Get user statistics
        users = sfc.client.list_users_with_keys_optimized()
        total_users = len(users)
        active_users = sum(1 for u in users if not u.get('disabled') and not u.get('snowflake_lock'))
        locked_users = sum(1 for u in users if u.get('snowflake_lock'))
        users_with_keys = sum(1 for u in users if u.get('has_rsa_public_key'))
        
        # Get role statistics
        roles = sfc.client.list_roles_detailed()
        total_roles = len(roles)
        system_roles = sum(1 for r in roles if r.get('type') == 'SYSTEM' or r.get('name') in ['ACCOUNTADMIN', 'SECURITYADMIN', 'SYSADMIN', 'PUBLIC', 'USERADMIN', 'ORGADMIN'])
        custom_roles = total_roles - system_roles
        
        # Get audit statistics
        audit_stats = audit.get_audit_statistics()
        
        # System health
        connection_status = 'connected' if sfc.client._conn else 'disconnected'
        last_sync = datetime.datetime.now().isoformat()
        
        return jsonify({
            'success': True,
            'data': {
                'users': {
                    'total': total_users,
                    'active': active_users,
                    'locked': locked_users,
                    'with_keys': users_with_keys,
                    'without_keys': total_users - users_with_keys
                },
                'roles': {
                    'total': total_roles,
                    'system': system_roles,
                    'custom': custom_roles
                },
                'audit': audit_stats,
                'system_health': {
                    'connection_status': connection_status,
                    'last_sync': last_sync
                }
            }
        })
    except Exception as e:
        return error_response(e)

@app.route('/keys/generate-and-rotate', methods=['POST'])
@require_oauth
def generate_and_rotate_key():
    """Generate encrypted RSA key pair and optionally set in Snowflake with enhanced options."""
    try:
        payload = request.json or {}
        username = payload.get('username')
        passphrase = payload.get('passphrase')
        set_in_snowflake = payload.get('set_in_snowflake', False)
        unset_password = payload.get('unset_password', False)
        new_type = payload.get('new_type')
        
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
            'snowflake_error': None,
            'actions_performed': {
                'rsa_key_set': False,
                'password_unset': False,
                'type_changed': False
            }
        }
        
        # Optionally set in Snowflake using enhanced stored procedure
        if set_in_snowflake:
            try:
                print(f"Attempting to set key in Snowflake for user: {username}")
                print(f"Additional options - unset_password: {unset_password}, new_type: {new_type}")
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
                        
                        # Use the enhanced stored procedure
                        print(f"Calling update_user_rsa_key for {username}")
                        sf_result = sfc.client.update_user_rsa_key(
                            username, 
                            public_key_content, 
                            unset_password, 
                            new_type if new_type and new_type != 'NULL' else None
                        )
                        print(f"Snowflake update_user_rsa_key result: {sf_result}")
                        
                        if sf_result.get('success'):
                            response_data['snowflake_success'] = True
                            response_data['actions_performed'] = sf_result.get('actions_performed', {})
                            print("✓ Successfully updated RSA key in Snowflake with enhanced options")
                        else:
                            # Generate manual command for fallback - ensure key content is stripped
                            lines = public_key_content.strip().split('\n')
                            if len(lines) > 2 and lines[0].startswith('-----BEGIN') and lines[-1].startswith('-----END'):
                                key_content = ''.join(lines[1:-1])
                            else:
                                key_content = public_key_content.replace('\n', '')
                            
                            # Build manual SQL commands
                            cmd_parts = []
                            cmd_parts.append(f"ALTER USER {username} SET RSA_PUBLIC_KEY='{key_content}'")
                            if unset_password:
                                cmd_parts.append(f"ALTER USER {username} SET PASSWORD = NULL")
                            if new_type and new_type.upper() != 'NULL':
                                cmd_parts.append(f"ALTER USER {username} SET TYPE = {new_type}")
                            
                            response_data['snowflake_command'] = ';\n'.join(cmd_parts) + ';'
                            # Extract error from either 'error' or 'message' field
                            error_msg = sf_result.get('error') or sf_result.get('message', 'Unknown error')
                            response_data['snowflake_error'] = error_msg
                            print(f"✗ Failed to update RSA key in Snowflake: {error_msg}")
                    else:
                        # Still provide a fallback command even if file not found
                        response_data['snowflake_command'] = f"-- Could not find generated public key file: {public_key_filename}\n-- Please download the public key file and run the enhanced stored procedure manually"
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
                
                # Try to get clean key content for fallback command
                clean_key_content = "-- Replace with actual public key content (stripped of headers) --"
                try:
                    lines = public_key_content.strip().split('\n')
                    if len(lines) > 2 and lines[0].startswith('-----BEGIN') and lines[-1].startswith('-----END'):
                        clean_key_content = ''.join(lines[1:-1])
                    else:
                        clean_key_content = public_key_content.replace('\n', '')
                except:
                    pass
                
                response_data['snowflake_command'] = f"-- Call the stored procedure manually:\nCALL UPLAND_MAINTENANCE.SECURITY.sp_update_user_rsa_key('{username}', '{clean_key_content}', {str(unset_password).lower()}, {repr(new_type)});"
                response_data['snowflake_error'] = str(sf_error)
                print("✗ Generated fallback command due to exception")
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in generate_and_rotate_key: {str(e)}")
        return error_response(e)

# Helper to get current user identity for audit logging
def get_audit_identity():
    """Get current user identity for audit logging."""
    ident = oauth.current_identity()
    if ident:
        return ident.get('user', 'unknown'), ident.get('role', 'unknown')
    return 'unknown', 'unknown'

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

def kill_port_processes(port):
    """Kill all processes using the specified port, excluding current and parent processes."""
    try:
        # Skip if we're in the Flask reloader child process
        # WERKZEUG_RUN_MAIN is set to 'true' in the reloader child process
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            # We're in the reloader, don't kill anything
            return
        
        # Get current process and parent process IDs to exclude
        current_pid = str(os.getpid())
        parent_pid = str(os.getppid())
        exclude_pids = {current_pid, parent_pid}
        
        # Use lsof to find processes using the port and kill them
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            killed_any = False
            for pid in pids:
                if pid and pid not in exclude_pids:
                    try:
                        subprocess.run(['kill', '-9', pid], check=False)
                        logger.info(f'Killed process {pid} using port {port}')
                        killed_any = True
                    except Exception as e:
                        logger.warning(f'Failed to kill process {pid}: {e}')
            if not killed_any:
                logger.info(f'No external processes found using port {port} (current processes excluded)')
        else:
            logger.info(f'No processes found using port {port}')
    except FileNotFoundError:
        # lsof might not be available on all systems
        logger.warning('lsof command not found. Skipping port cleanup.')
    except Exception as e:
        logger.warning(f'Error checking/killing processes on port {port}: {e}')

if __name__ == '__main__':
    # Kill any existing processes on port 5001 (only on initial startup, not on reload)
    kill_port_processes(5001)
    
    # Open browser after a short delay (only in main process, not reloader)
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        Timer(1.5, open_browser).start()
    
    # Run on port 5001 to match OAuth redirect URI
    app.run(host='127.0.0.1', port=5001, debug=True) 