import os
import streamlit as st
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class UserInfo:
    """User information extracted from authentication headers"""
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    roles: list = None
    groups: list = None
    is_authenticated: bool = True
    
    def __post_init__(self):
        if self.roles is None:
            self.roles = []
        if self.groups is None:
            self.groups = []


class AuthConfig:
    """Authentication configuration and user session management"""
    
    def __init__(self):
        self.enabled = self._is_auth_enabled()
        self.keycloak_realm = os.getenv('KEYCLOAK_REALM', 'master')
        self.keycloak_client_id = os.getenv('KEYCLOAK_CLIENT_ID', 'demobuilder')
        
    def _is_auth_enabled(self) -> bool:
        """Check if authentication is enabled via environment variable"""
        return os.getenv('KEYCLOAK_ENABLED', 'false').lower() in ['true', '1', 'yes']
    
    def get_current_user(self) -> Optional[UserInfo]:
        """Get current authenticated user using official Streamlit patterns"""
        if not self.enabled:
            return None
            
        # Check if user info is already cached in session state
        if 'auth_user' in st.session_state:
            cached_user = st.session_state.auth_user
            if os.getenv('AUTH_DEBUG', 'false').lower() == 'true':
                st.write(f"Debug: Using cached user: {cached_user.username}")
            return cached_user
            
        # Try to extract user from headers
        try:
            user_info = self._extract_user_from_headers()
            if user_info:
                # Cache the user info in session state
                st.session_state.auth_user = user_info
                if os.getenv('AUTH_DEBUG', 'false').lower() == 'true':
                    st.write(f"Debug: Cached new user: {user_info.username}")
                return user_info
        except Exception as e:
            if os.getenv('AUTH_DEBUG', 'false').lower() == 'true':
                st.error(f"Debug: get_current_user failed: {e}")
                
        return None
    
    def _extract_user_from_headers(self) -> Optional[UserInfo]:
        """Extract user information from OAuth2 Proxy headers using official st.context.headers"""
        try:
            # Use official Streamlit context API (as shown in docs)
            headers = st.context.headers
            
            # Debug logging if enabled
            if os.getenv('AUTH_DEBUG', 'false').lower() == 'true':
                st.write(f"Debug: Attempting to extract user from {len(headers)} headers")
            
            # OAuth2 Proxy sets these headers after successful authentication
            # Try common OAuth2 Proxy header formats
            username = (headers.get('X-Auth-Request-User') or 
                       headers.get('x-auth-request-user') or
                       headers.get('X-Forwarded-User') or
                       headers.get('x-forwarded-user'))
            
            email = (headers.get('X-Auth-Request-Email') or 
                    headers.get('x-auth-request-email') or
                    headers.get('X-Forwarded-Email') or
                    headers.get('x-forwarded-email'))
            
            display_name = (headers.get('X-Auth-Request-Preferred-Username') or 
                           headers.get('x-auth-request-preferred-username') or
                           headers.get('X-Auth-Request-Name') or
                           headers.get('x-auth-request-name'))
            
            # For development/testing, allow override via environment
            if not username and os.getenv('AUTH_DEV_MODE', 'false').lower() == 'true':
                username = os.getenv('AUTH_DEV_USER', 'dev-user')
                email = os.getenv('AUTH_DEV_EMAIL', 'dev@example.com')
                display_name = os.getenv('AUTH_DEV_DISPLAY_NAME', 'Development User')
                
                if os.getenv('AUTH_DEBUG', 'false').lower() == 'true':
                    st.write(f"Debug: Using dev mode user: {username}")
            
            if username:
                # Parse roles and groups from headers if available
                roles_header = (headers.get('X-Auth-Request-Groups', '') or 
                               headers.get('x-auth-request-groups', '') or
                               headers.get('X-Forwarded-Groups', '') or
                               headers.get('x-forwarded-groups', ''))
                roles = [role.strip() for role in roles_header.split(',') if role.strip()] if roles_header else []
                
                if os.getenv('AUTH_DEBUG', 'false').lower() == 'true':
                    st.write(f"Debug: Extracted user - username: {username}, email: {email}, roles: {roles}")
                
                return UserInfo(
                    username=username,
                    email=email,
                    display_name=display_name or username,
                    roles=roles,
                    groups=roles,  # Using roles as groups for simplicity
                    is_authenticated=True
                )
            else:
                if os.getenv('AUTH_DEBUG', 'false').lower() == 'true':
                    st.write("Debug: No username found in headers")
                    
        except Exception as e:
            # Enhanced error logging for debugging
            if os.getenv('AUTH_DEBUG', 'false').lower() == 'true':
                st.error(f"Debug: Error extracting user info: {e}")
                st.error(f"Debug: Exception type: {type(e).__name__}")
            
        return None
    
    def is_authenticated(self) -> bool:
        """Check if current user is authenticated"""
        if not self.enabled:
            return True  # If auth is disabled, consider everyone authenticated
            
        user = self.get_current_user()
        return user is not None and user.is_authenticated
    
    def has_role(self, role: str) -> bool:
        """Check if current user has a specific role"""
        if not self.enabled:
            return True  # If auth is disabled, grant all roles
            
        user = self.get_current_user()
        return user is not None and role in user.roles
    
    def has_any_role(self, roles: list) -> bool:
        """Check if current user has any of the specified roles"""
        if not self.enabled:
            return True  # If auth is disabled, grant all roles
            
        user = self.get_current_user()
        return user is not None and any(role in user.roles for role in roles)
    
    def logout_url(self) -> str:
        """Get logout URL for Keycloak"""
        if not self.enabled:
            return "#"
            
        # OAuth2 Proxy logout endpoint
        return "/oauth2/sign_out"
    
    def clear_session(self):
        """Clear authentication session state and optionally all session data"""
        if 'auth_user' in st.session_state:
            del st.session_state.auth_user
        # Also clear auth config to force re-initialization
        if 'auth_config' in st.session_state:
            del st.session_state.auth_config


def get_auth_config() -> AuthConfig:
    """Get authentication configuration singleton"""
    if 'auth_config' not in st.session_state:
        st.session_state.auth_config = AuthConfig()
    return st.session_state.auth_config


def require_auth(func):
    """Decorator to require authentication for a function"""
    def wrapper(*args, **kwargs):
        auth_config = get_auth_config()
        if not auth_config.is_authenticated():
            st.error("Authentication required to access this feature.")
            st.stop()
        return func(*args, **kwargs)
    return wrapper


def show_auth_info():
    """Display current authentication status in sidebar"""
    auth_config = get_auth_config()
    
    # Don't show anything if authentication is disabled
    if not auth_config.enabled:
        return
    
    user = auth_config.get_current_user()
    if user:
        with st.sidebar.expander("👤 User Info", expanded=False):
            st.write(f"**User:** {user.display_name}")
            st.write(f"**Email:** {user.email or 'N/A'}")
            if user.roles:
                st.write(f"**Roles:** {', '.join(user.roles)}")
            
            # Logout button
            if st.button("🚪 Logout", key="auth_logout"):
                # Clear session state
                auth_config.clear_session()
                # Use JavaScript redirect for better reliability
                logout_url = auth_config.logout_url()
                st.markdown(f"""
                <script>
                window.location.href = "{logout_url}";
                </script>
                """, unsafe_allow_html=True)
                st.stop()
    else:
        st.sidebar.error("🔒 Not authenticated")


def get_user_preferences() -> Dict[str, Any]:
    """Get user-specific preferences (for future use)"""
    auth_config = get_auth_config()
    user = auth_config.get_current_user()
    
    if not user:
        return {}
    
    # For now, return empty dict. In future, this could load from database
    # based on user.username
    return {}


def is_admin_user() -> bool:
    """Check if current user is an admin"""
    auth_config = get_auth_config()
    return auth_config.has_role('admin') or auth_config.has_role('demobuilder-admin')


def get_display_username() -> Optional[str]:
    """Get the username to display in the top right corner"""
    auth_config = get_auth_config()
    
    if not auth_config.enabled:
        return None
        
    user = auth_config.get_current_user()
    if user:
        return user.display_name or user.username
    
    return None


def is_power_user() -> bool:
    """Check if current user is a power user with extended features"""
    auth_config = get_auth_config()
    return (auth_config.has_any_role(['admin', 'power-user', 'demobuilder-admin', 'demobuilder-power']) 
            or is_admin_user())