"""
Audit logging module for tracking administrative actions.
"""
import os
import json
import datetime
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger('snowflake-admin-app.audit')

# Audit log directory
AUDIT_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'audit')
os.makedirs(AUDIT_LOG_DIR, exist_ok=True)

# Current audit log file (rotated daily)
def get_audit_log_file():
    """Get the current audit log file path based on date."""
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    return os.path.join(AUDIT_LOG_DIR, f'audit_{today}.jsonl')

def log_action(
    action: str,
    user: str,
    role: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None
):
    """
    Log an administrative action to the audit trail.
    
    Args:
        action: Type of action (e.g., 'user_unlock', 'password_reset', 'permission_grant')
        user: Username of the person performing the action
        role: Role of the person performing the action
        target_type: Type of target (e.g., 'user', 'role', 'permission')
        target_id: Identifier of the target (e.g., username, role name)
        details: Additional details about the action
        success: Whether the action was successful
        error_message: Error message if action failed
    """
    try:
        audit_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'action': action,
            'user': user,
            'role': role,
            'target_type': target_type,
            'target_id': target_id,
            'details': details or {},
            'success': success,
            'error_message': error_message
        }
        
        log_file = get_audit_log_file()
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(audit_entry) + '\n')
        
        logger.info(f"Audit log: {action} by {user} ({role}) - {'SUCCESS' if success else 'FAILED'}")
        
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")

def read_audit_logs(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    action_filter: Optional[str] = None,
    user_filter: Optional[str] = None,
    max_entries: int = 1000
) -> List[Dict[str, Any]]:
    """
    Read audit log entries with optional filtering.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        action_filter: Filter by action type
        user_filter: Filter by user
        max_entries: Maximum number of entries to return
        
    Returns:
        List of audit log entries
    """
    entries = []
    
    try:
        # Determine date range
        if start_date:
            start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start = datetime.datetime.now() - datetime.timedelta(days=30)  # Default to last 30 days
        
        if end_date:
            end = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        else:
            end = datetime.datetime.now()
        
        # Iterate through date range
        current_date = start
        while current_date <= end:
            log_file = os.path.join(AUDIT_LOG_DIR, f'audit_{current_date.strftime("%Y-%m-%d")}.jsonl')
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                entry = json.loads(line)
                                # Apply filters
                                if action_filter and entry.get('action') != action_filter:
                                    continue
                                if user_filter and entry.get('user') != user_filter:
                                    continue
                                entries.append(entry)
                            except json.JSONDecodeError:
                                continue
            current_date += datetime.timedelta(days=1)
        
        # Sort by timestamp (newest first)
        entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Limit results
        return entries[:max_entries]
        
    except Exception as e:
        logger.error(f"Failed to read audit logs: {e}")
        return []

def get_audit_statistics() -> Dict[str, Any]:
    """Get statistics about audit logs."""
    try:
        stats = {
            'total_actions': 0,
            'actions_by_type': {},
            'actions_by_user': {},
            'success_rate': 0,
            'recent_actions': []
        }
        
        # Read last 7 days of logs
        end_date = datetime.datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        entries = read_audit_logs(start_date=start_date, end_date=end_date, max_entries=10000)
        
        stats['total_actions'] = len(entries)
        successful = sum(1 for e in entries if e.get('success', False))
        if entries:
            stats['success_rate'] = (successful / len(entries)) * 100
        
        # Count by action type
        for entry in entries:
            action = entry.get('action', 'unknown')
            stats['actions_by_type'][action] = stats['actions_by_type'].get(action, 0) + 1
            
            user = entry.get('user', 'unknown')
            stats['actions_by_user'][user] = stats['actions_by_user'].get(user, 0) + 1
        
        # Get recent actions (last 10)
        stats['recent_actions'] = entries[:10]
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get audit statistics: {e}")
        return {
            'total_actions': 0,
            'actions_by_type': {},
            'actions_by_user': {},
            'success_rate': 0,
            'recent_actions': []
        }

