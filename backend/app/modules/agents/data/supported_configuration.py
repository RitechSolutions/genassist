DATA_SOURCE_SCHEMAS = {
    "S3": {
        "name": "S3",
        "fields": [
            {
                "name": "access_key",
                "type": "password",
                "label": "Access key",
                "required": True,
                "description": "Enter access key"
            },
            {
                "name": "secret_key",
                "type": "password",
                "label": "Secret key",
                "required": True,
                "description": "Enter secret key"
            },            
            {
                "name": "region",
                "type": "text",
                "label": "Region",
                "required": True,
                "description": "Enter region"
            },            
            {
                "name": "bucket_name",
                "type": "text",
                "label": "Bucket name",
                "required": True,
                "description": "Enter bucket name"
            },            
            {
                "name": "prefix",
                "type": "text",
                "label": "Prefix",
                "required": True,
                "description": "Enter prefix"
            }
        ]
    },
    "Database": {
        "name": "Database",
        "fields": [
            {
                "name": "database_host",
                "type": "text",
                "label": "Database host",
                "required": True,
                "description": "Enter database host"
            },
            {
                "name": "database_port",
                "type": "number",
                "label": "Database port",
                "required": True,
                "description": "Enter database port"
            },
            {
                "name": "database_name",
                "type": "text",
                "label": "Database name",
                "required": True,
                "description": "Enter database name"
            },
            {
                "name": "database_user",
                "type": "text",
                "label": "Database user",
                "required": True,
                "description": "Enter database user"
            },
            {
                "name": "database_password",
                "type": "password",
                "label": "Database password",
                "required": True,
                "description": "Enter database password"
            },
            {
                "name": "ssh_tunnel_host",
                "type": "text",
                "label": "SSH tunnel host",
                "required": False,
                "description": "Enter SSH tunnel host"
            },
            {
                "name": "ssh_tunnel_port",
                "type": "number",
                "label": "SSH tunnel port",
                "required": False,
                "description": "Enter SSH tunnel port"
            },
            {
                "name": "ssh_tunnel_user",
                "type": "text",
                "label": "SSH tunnel user",
                "required": False,
                "description": "Enter SSH tunnel user"
            },
            {
                "name": "ssh_tunnel_private_key",
                "type": "password",
                "label": "SSH tunnel private key",
                "required": False,
                "description": "Enter SSH tunnel private key"
            }
        ]
    }
}