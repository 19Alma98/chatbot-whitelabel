# User Authentication System

This document describes the user authentication system implemented for the RAG Chatbot application.

## Features

- **JWT-based Authentication**: Secure token-based authentication using JSON Web Tokens
- **User Registration**: Self-service user registration with email and username
- **Login/Logout**: Standard authentication flow with access and refresh tokens
- **Password Security**: Passwords are hashed using bcrypt
- **Token Refresh**: Long-lived refresh tokens for seamless user experience
- **Optional Authentication**: Endpoints support both authenticated and anonymous access
- **Row-Level Security**: PostgreSQL RLS ensures users can only access their own conversations

## Architecture

### Components

1. **User Model** (`postgres_models.py`): SQLAlchemy model for user storage
2. **Authentication Utils** (`auth_utils.py`): Password hashing and JWT token generation
3. **Auth Dependencies** (`auth_dependencies.py`): FastAPI dependencies for authentication
4. **Auth Routes** (`routes/auth_routes.py`): API endpoints for authentication
5. **Database Migration**: Alembic migration to add users table and RLS policies

### Security Features

- **bcrypt Password Hashing**: Industry-standard password hashing
- **JWT Tokens**: Short-lived access tokens (30 minutes) and long-lived refresh tokens (7 days)
- **Row-Level Security**: Database-level security ensuring data isolation
- **Optional Authentication**: Backwards compatibility with anonymous usage

## Environment Variables

Add these to your `.env` file:

```bash
# JWT Authentication
JWT_SECRET_KEY=your-super-secret-key-change-in-production-min-32-chars
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**Important**: Use a strong, random secret key in production. Generate one with:

```bash
openssl rand -hex 32
```

## Database Setup

### 1. Run the Migration

```bash
# Apply the authentication migration
alembic upgrade head
```

This will:
- Create the `users` table
- Add `user_id` column to `conversation_memory`
- Enable Row-Level Security (RLS) on both tables
- Create RLS policies for data isolation

### 2. Create Initial Admin User

Use the helper script to create your first admin user:

```bash
python scripts/create_admin_user.py
```

Or manually via SQL:

```sql
INSERT INTO users (email, username, hashed_password, full_name, is_superuser, is_active)
VALUES (
    'admin@example.com',
    'admin',
    '$2b$12$... (use bcrypt to hash your password)',
    'Admin User',
    TRUE,
    TRUE
);
```

## API Endpoints

### Register a New User

```http
POST /auth/register
Content-Type: application/json

{
    "email": "user@example.com",
    "username": "johndoe",
    "password": "SecurePassword123!",
    "full_name": "John Doe"
}
```

**Response**:
```json
{
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "username": "johndoe",
    "full_name": "John Doe",
    "is_active": true,
    "is_superuser": false,
    "created_at": "2025-11-24T10:00:00Z",
    "updated_at": "2025-11-24T10:00:00Z"
}
```

### Login

```http
POST /auth/login
Content-Type: application/json

{
    "username": "johndoe",  # Can be username or email
    "password": "SecurePassword123!"
}
```

**Response**:
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
}
```

### Get Current User

```http
GET /auth/me
Authorization: Bearer {access_token}
```

**Response**:
```json
{
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "username": "johndoe",
    "full_name": "John Doe",
    "is_active": true,
    "is_superuser": false,
    "created_at": "2025-11-24T10:00:00Z",
    "updated_at": "2025-11-24T10:00:00Z"
}
```

### Refresh Token

```http
POST /auth/refresh
Content-Type: application/json

{
    "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response**:
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
}
```

### Update Profile

```http
PATCH /auth/me
Authorization: Bearer {access_token}
Content-Type: application/json

{
    "full_name": "John D. Doe",
    "email": "newemail@example.com"
}
```

### Change Password

```http
POST /auth/change-password
Authorization: Bearer {access_token}
Content-Type: application/json

{
    "current_password": "OldPassword123!",
    "new_password": "NewSecurePassword456!"
}
```

## Using Authentication in Frontend

### Example: Login Flow

```javascript
// 1. Login
const loginResponse = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        username: 'johndoe',
        password: 'SecurePassword123!'
    })
});

const { access_token, refresh_token } = await loginResponse.json();

// Store tokens securely
localStorage.setItem('access_token', access_token);
localStorage.setItem('refresh_token', refresh_token);

// 2. Use authenticated endpoints
const chatResponse = await fetch('/chat', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    },
    body: JSON.stringify({
        messages: [{ role: 'user', content: 'Hello!' }]
    })
});

// 3. Refresh token when expired
if (chatResponse.status === 401) {
    const refreshResponse = await fetch('/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token })
    });
    
    const { access_token: newToken } = await refreshResponse.json();
    localStorage.setItem('access_token', newToken);
    
    // Retry original request with new token
    // ...
}
```

### Token Storage Best Practices

- **Development**: localStorage is acceptable
- **Production**: Consider:
  - httpOnly cookies for refresh tokens
  - Memory storage for access tokens
  - Secure token rotation

## Protected vs. Optional Authentication

### Current Implementation

All conversation-related endpoints support **optional authentication**:

- **With Token**: User can only see their own conversations
- **Without Token**: User can access all conversations (legacy behavior)

### Making Endpoints Require Authentication

To require authentication, change the dependency in `api_routes.py`:

```python
# Optional (current)
current_user: Optional[User] = Depends(get_optional_user)

# Required (strict)
from fastapi_app.auth_dependencies import CurrentUser
current_user: CurrentUser
```

## Row-Level Security (RLS)

PostgreSQL RLS policies automatically filter data:

```sql
-- Users can only see conversations where:
-- 1. user_id matches their ID, OR
-- 2. user_id is NULL (legacy conversations)
CREATE POLICY user_conversations_policy ON conversation_memory
    FOR ALL
    USING (
        user_id IS NULL OR 
        user_id::text = current_setting('app.current_user_id', TRUE)
    );
```

**Note**: Current implementation uses application-level filtering instead of setting `app.current_user_id` session variable. To use RLS fully, update the database session to set this variable on connection.

## Security Considerations

### Production Checklist

- [ ] Generate strong `JWT_SECRET_KEY` (min 32 characters)
- [ ] Use HTTPS for all API calls
- [ ] Set appropriate token expiration times
- [ ] Implement rate limiting on auth endpoints
- [ ] Add email verification for registration
- [ ] Implement password reset flow
- [ ] Add multi-factor authentication (MFA)
- [ ] Monitor failed login attempts
- [ ] Implement account lockout after N failed attempts
- [ ] Use httpOnly cookies for refresh tokens in production
- [ ] Enable RLS session variable setting
- [ ] Regular security audits

### Password Requirements

Current minimum: 8 characters

Recommended production requirements:
- Minimum 12 characters
- Mix of uppercase, lowercase, numbers, symbols
- Check against common password lists
- Implement password history

## Troubleshooting

### Token Validation Errors

```
Could not validate credentials
```

**Causes**:
- Expired token
- Invalid JWT_SECRET_KEY
- Token tampered with
- Token format incorrect

**Solution**: Request new token via `/auth/login` or `/auth/refresh`

### User Not Found

```
User not found
```

**Causes**:
- User deleted after token issued
- Wrong database
- RLS policy blocking access

**Solution**: User must re-register

### Permission Denied

```
Not enough permissions
```

**Causes**:
- Endpoint requires superuser
- User account is inactive

**Solution**: Contact administrator

## Migration Guide

### For Existing Deployments

1. **Backup database**:
   ```bash
   pg_dump chatbot > backup_before_auth.sql
   ```

2. **Run migration**:
   ```bash
   alembic upgrade head
   ```

3. **Create admin user**:
   ```bash
   python scripts/create_admin_user.py
   ```

4. **Update environment variables**:
   ```bash
   JWT_SECRET_KEY=$(openssl rand -hex 32)
   echo "JWT_SECRET_KEY=$JWT_SECRET_KEY" >> .env
   ```

5. **Test authentication**:
   ```bash
   curl -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"your-password"}'
   ```

6. **Update frontend** to include Authorization headers

### Rollback Plan

If issues occur:

```bash
# Rollback migration
alembic downgrade -1

# Restore database
psql chatbot < backup_before_auth.sql
```

## Future Enhancements

- [ ] OAuth2 integration (Google, Microsoft, GitHub)
- [ ] Multi-factor authentication (TOTP, SMS)
- [ ] Email verification
- [ ] Password reset via email
- [ ] Account lockout after failed attempts
- [ ] Audit logging for authentication events
- [ ] Session management (active sessions, logout all devices)
- [ ] API key authentication for programmatic access
- [ ] Role-based access control (RBAC) beyond superuser
- [ ] Organization/tenant management for multi-tenancy

## References

- [FastAPI Security Tutorial](https://fastapi.tiangolo.com/tutorial/security/)
- [JWT.io - JSON Web Tokens](https://jwt.io/)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [PostgreSQL Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-24  
**Author**: Development Team

