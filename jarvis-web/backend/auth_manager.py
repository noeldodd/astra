# auth_manager.py
"""
JARVIS Authentication Manager

Handles user authentication, JWT tokens, and auth levels.

Auth Levels:
- 0: Guest (read-only, no personal data)
- 1: User (standard access, own data)
- 2: Power User (system stats, debugging info)
- 3: Developer (prompts, config, detailed logs)
- 4: Admin (full access, user management)
"""

import jwt
import bcrypt
import uuid
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pydantic import BaseModel
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# JWT Configuration from environment
JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key-change-this-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', 24))

class User(BaseModel):
    """User model"""
    id: str
    username: str
    password_hash: str
    email: Optional[str] = None
    auth_level: int = 1  # Default: standard user
    created_at: str
    last_login: Optional[str] = None

class AuthManager:
    """Manage user authentication and authorization"""
    
    def __init__(self, users_file: str = "users.json"):
        """
        Initialize auth manager
        
        Args:
            users_file: Path to users database file
        """
        self.users_file = Path(users_file)
        self.users: Dict[str, User] = {}
        self._load_users()
    
    def _load_users(self):
        """Load users from file"""
        if self.users_file.exists():
            try:
                with open(self.users_file, 'r') as f:
                    data = json.load(f)
                    self.users = {
                        user_id: User(**user_data)
                        for user_id, user_data in data.items()
                    }
            except Exception as e:
                print(f"Error loading users: {e}")
                self.users = {}
        else:
            self.users = {}
    
    def _save_users(self):
        """Save users to file"""
        try:
            self.users_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.users_file, 'w') as f:
                data = {
                    user_id: user.dict()
                    for user_id, user in self.users.items()
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving users: {e}")
    
    def _hash_password(self, password: str) -> str:
        """Hash password with bcrypt"""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except:
            return False
    
    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        auth_level: int = 1
    ) -> User:
        """
        Create new user
        
        Args:
            username: Unique username
            password: Password (will be hashed)
            email: Optional email
            auth_level: Authorization level (0-4)
            
        Returns:
            Created user
            
        Raises:
            ValueError: If username exists
        """
        
        # Check if username exists
        if self.get_user_by_username(username):
            raise ValueError(f"Username '{username}' already exists")
        
        # Validate auth level
        if not 0 <= auth_level <= 4:
            raise ValueError("Auth level must be 0-4")
        
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            password_hash=self._hash_password(password),
            email=email,
            auth_level=auth_level,
            created_at=datetime.now().isoformat()
        )
        
        self.users[user.id] = user
        self._save_users()
        
        return user
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate user
        
        Args:
            username: Username
            password: Password
            
        Returns:
            User if authenticated, None otherwise
        """
        
        user = self.get_user_by_username(username)
        
        if not user:
            return None
        
        if not self._verify_password(password, user.password_hash):
            return None
        
        # Update last login
        user.last_login = datetime.now().isoformat()
        self._save_users()
        
        return user
    
    def create_token(self, user: User) -> str:
        """
        Create JWT token for user
        
        Args:
            user: User to create token for
            
        Returns:
            JWT token
        """
        
        payload = {
            "user_id": user.id,
            "username": user.username,
            "auth_level": user.auth_level,
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    def verify_token(self, token: str) -> Optional[User]:
        """
        Verify JWT token and return user
        
        Args:
            token: JWT token
            
        Returns:
            User if token is valid, None otherwise
        """
        
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("user_id")
            
            if not user_id:
                return None
            
            return self.users.get(user_id)
        
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        for user in self.users.values():
            if user.username == username:
                return user
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.users.get(user_id)
    
    def update_user(
        self,
        user_id: str,
        **updates
    ) -> Optional[User]:
        """
        Update user fields
        
        Args:
            user_id: User ID
            **updates: Fields to update
            
        Returns:
            Updated user, or None if not found
        """
        
        user = self.users.get(user_id)
        if not user:
            return None
        
        # Update allowed fields
        allowed_fields = ['email', 'auth_level']
        for field, value in updates.items():
            if field in allowed_fields:
                setattr(user, field, value)
        
        # Handle password separately
        if 'password' in updates:
            user.password_hash = self._hash_password(updates['password'])
        
        self._save_users()
        return user
    
    def delete_user(self, user_id: str) -> bool:
        """
        Delete user
        
        Args:
            user_id: User ID
            
        Returns:
            True if deleted, False if not found
        """
        
        if user_id in self.users:
            del self.users[user_id]
            self._save_users()
            return True
        return False
    
    def list_users(self, min_auth_level: int = 0) -> List[User]:
        """
        List all users with at least the specified auth level
        
        Args:
            min_auth_level: Minimum auth level
            
        Returns:
            List of users
        """
        
        return [
            user for user in self.users.values()
            if user.auth_level >= min_auth_level
        ]
    
    def get_stats(self) -> dict:
        """Get authentication statistics"""
        return {
            "total_users": len(self.users),
            "by_auth_level": {
                level: len([u for u in self.users.values() if u.auth_level == level])
                for level in range(5)
            },
            "last_created": max(
                [u.created_at for u in self.users.values()],
                default=None
            )
        }


# Example usage
if __name__ == "__main__":
    auth = AuthManager()
    
    # Create test users
    try:
        admin = auth.create_user("admin", "admin123", auth_level=4)
        print(f"Created admin: {admin.username}")
    except ValueError:
        print("Admin already exists")
    
    try:
        user = auth.create_user("testuser", "password123", email="test@example.com")
        print(f"Created user: {user.username}")
    except ValueError:
        print("User already exists")
    
    # Test authentication
    authenticated = auth.authenticate("admin", "admin123")
    if authenticated:
        print(f"✓ Authenticated: {authenticated.username}")
        
        # Create token
        token = auth.create_token(authenticated)
        print(f"✓ Token: {token[:50]}...")
        
        # Verify token
        verified = auth.verify_token(token)
        print(f"✓ Verified: {verified.username if verified else 'Failed'}")
    
    # Stats
    stats = auth.get_stats()
    print(f"\nStats: {stats}")