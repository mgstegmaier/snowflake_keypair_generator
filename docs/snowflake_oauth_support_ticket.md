# Snowflake OAuth Integration Support Ticket

## Issue Description
We are experiencing issues with the OAuth token exchange process in our application. The initial authorization code request works, but the token exchange fails with a 400 error and "invalid_client" message.

## Current Behavior
1. Initial authorization request succeeds and redirects to our callback URL with a valid authorization code
2. Token exchange request fails with:
   ```
   Status Code: 400
   Error: invalid_client
   Message: This is an invalid client.
   ```

## Integration Details
### Snowflake OAuth Configuration
```
property                    property_type    property_value                                                                                property_default
ENABLED                     Boolean          true                                                                                          false
OAUTH_REDIRECT_URI          String           http://localhost:5001/oauth/callback                                                          
OAUTH_CLIENT_TYPE           String           CONFIDENTIAL                                                                                  CONFIDENTIAL
OAUTH_ISSUE_REFRESH_TOKENS  Boolean          true                                                                                          true
OAUTH_REFRESH_TOKEN_VALIDITY Integer         86400                                                                                         7776000
OAUTH_SINGLE_USE_REFRESH_TOKENS_REQUIRED Boolean false                                                                                     false
OAUTH_ENFORCE_PKCE          Boolean          false                                                                                         false
OAUTH_USE_SECONDARY_ROLES   String           NONE                                                                                          NONE
OAUTH_CLIENT_ID             String           WP3jEvdWUFFYkm69qmhsfOgqBcI=                                                                  
OAUTH_AUTHORIZATION_ENDPOINT String          https://nr74328.east-us-2.azure.snowflakecomputing.com/oauth/authorize                        
OAUTH_TOKEN_ENDPOINT        String           https://nr74328.east-us-2.azure.snowflakecomputing.com/oauth/token-request                    
```

### Application Configuration
```python
OAUTH_CLIENT_ID: WP3jEvdWUFFYkm69qmhsfOgqBcI=
OAUTH_CLIENT_SECRET: WP3jEvdWUFFYkm69qmhsfOgqBcI=
OAUTH_AUTH_URL: https://nr74328.east-us-2.azure.snowflakecomputing.com/oauth/authorize
OAUTH_TOKEN_URL: https://nr74328.east-us-2.azure.snowflakecomputing.com/oauth/token-request
OAUTH_REDIRECT_URI: http://localhost:5001/oauth/callback
OAUTH_SCOPE: session:role:SYSADMIN
```

## Attempted Solutions
1. **Basic Authentication**
   - Tried sending client credentials in Basic Auth header
   - Used format: `Authorization: Basic base64(client_id:client_secret)`

2. **Request Body Authentication**
   - Tried sending client credentials in request body
   - Included `client_id` and `client_secret` in form data

3. **URL Encoding**
   - Tried URL encoding the client ID and redirect URI
   - Tried with and without the trailing `=` in client ID

4. **JWT Authentication**
   - Attempted to use JWT token in Authorization header
   - Generated JWT with client ID as issuer and subject

## Request/Response Logs
### Authorization Request
```
Generated authorize URL: https://nr74328.east-us-2.azure.snowflakecomputing.com/oauth/authorize?response_type=code&client_id=WP3jEvdWUFFYkm69qmhsfOgqBcI%3D&redirect_uri=http%3A%2F%2Flocalhost%3A5001%2Foauth%2Fcallback&state=STATE&scope=session:role:SYSADMIN
```

### Token Exchange Request
```
URL: https://nr74328.east-us-2.azure.snowflakecomputing.com/oauth/token-request
Data: {
    "grant_type": "authorization_code",
    "code": "AUTHORIZATION_CODE",
    "redirect_uri": "http://localhost:5001/oauth/callback",
    "client_id": "WP3jEvdWUFFYkm69qmhsfOgqBcI=",
    "client_secret": "WP3jEvdWUFFYkm69qmhsfOgqBcI="
}
Headers: {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json"
}
```

### Token Exchange Response
```
Status Code: 400
Headers: {
    "Date": "Sat, 14 Jun 2025 22:34:16 GMT",
    "Content-Type": "application/json",
    "Server": "SF-LB",
    "X-Envoy-Attempt-Count": "1",
    "X-Envoy-Upstream-Service-Time": "5",
    "X-Content-Type-Options": "nosniff",
    "X-Xss-Protection": "1; mode=block",
    "Expect-Ct": "enforce, max-age=3600",
    "Strict-Transport-Security": "max-age=31536000",
    "X-Snowflake-Fe-Instance": "envoy-ingress-azeastus2prod-2dxkj",
    "X-Snowflake-Fe-Config": "281964bf_1747960657_azeastus2prod_1749940378936_0_0_0",
    "X-Frame-Options": "deny",
    "Content-Encoding": "gzip",
    "Vary": "Accept-Encoding",
    "Transfer-Encoding": "chunked"
}
Body: {
    "data": null,
    "error": "invalid_client",
    "code": null,
    "message": "This is an invalid client.",
    "success": false,
    "headers": null
}
```

## Questions for Support
1. Is the client ID format correct? Should it include the trailing `=`?
2. For a `CONFIDENTIAL` client type, what is the correct way to authenticate the token exchange request?
3. Are there any additional configuration steps needed in Snowflake for the OAuth integration?
4. Should we be using RSA key pair authentication instead of client credentials?

## Files to Attach
1. `backend/oauth.py` - OAuth implementation code
2. `.env` file (with sensitive data redacted) - Environment configuration
3. Any relevant Snowflake SQL commands used to set up the OAuth integration

## Additional Context
- The application is a Flask web application running locally
- We're using the Snowflake OAuth 2.0 implementation
- The application needs to authenticate users and obtain access tokens for Snowflake API access
- We're following the OAuth 2.0 authorization code flow

## Next Steps
1. Await guidance on the correct authentication method for `CONFIDENTIAL` client type
2. Verify if RSA key pair authentication is required
3. Confirm if any additional Snowflake configuration is needed
4. Get clarification on the expected format of client credentials 