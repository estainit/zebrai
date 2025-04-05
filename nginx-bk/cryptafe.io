server {
    server_name cryptafe.io 113.30.150.33;

    location / {
        proxy_pass http://127.0.0.1:3000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;

    }

    # location for WebSocket
    location /ws {
        proxy_pass http://127.0.0.1:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;  # WebSocket timeout
        proxy_send_timeout 86400;  # WebSocket timeout
        proxy_connect_timeout 86400;  # WebSocket timeout
        proxy_buffering off;    
    }

    # --- ADD THIS LOCATION BLOCK FOR THE API ---
    location /api/ {
        # Pass requests for /api/... to the backend server on port 8000
        # Make sure the path passed to the backend includes /api/
        # (adjust if your backend routes don't start with /api/)
        proxy_pass http://127.0.0.1:8000/api/;

        # Standard proxy headers
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade; # Needed for keep-alive
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }

    # pgAdmin configuration
    location /pgadmin/ {
        proxy_set_header X-Script-Name /pgadmin;
        proxy_set_header X-Scheme $scheme;
        proxy_pass http://127.0.0.1:5055;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_redirect off;
    }

    error_page 404 /index.html;

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/ssl/cryptafe.crt;
    ssl_certificate_key /etc/ssl/cryptafe.key;

}
server {
    if ($host = cryptafe.io) {
        return 301 https://$host$request_uri;
    } # managed by Certbot


    listen 80;
    server_name cryptafe.io 113.30.150.33;
    return 404; # managed by Certbot

}
