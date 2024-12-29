#!/usr/bin/env python3
"""Generate Fernet key and update .env file"""

import os
from cryptography.fernet import Fernet

def generate_key():
    """Generate a new Fernet key"""
    return Fernet.generate_key().decode()

def update_env_file(key):
    """Update .env file with the new key"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    
    # Read existing content
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()
    else:
        lines = []

    # Find FERNET_KEY line if it exists
    key_line = f'FERNET_KEY={key}\n'
    fernet_key_found = False
    
    for i, line in enumerate(lines):
        if line.startswith('FERNET_KEY='):
            lines[i] = key_line
            fernet_key_found = True
            break
    
    # If FERNET_KEY not found, add it with a section header
    if not fernet_key_found:
        # Add a blank line if file doesn't end with one
        if lines and not lines[-1].isspace():
            lines.append('\n')
        
        # Add security section if not present
        if not any(line.strip() == '# Security' for line in lines):
            lines.extend(['\n# Security\n'])
        
        lines.append(key_line)

    # Write back to file
    with open(env_path, 'w') as f:
        f.writelines(lines)

if __name__ == '__main__':
    key = generate_key()
    update_env_file(key)
    print(f'Generated and added new Fernet key to .env file: {key}')
